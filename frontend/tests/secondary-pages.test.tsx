import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { routeForPath } from "@/app/AppRoutes";
import { BookWorkspacePage } from "@/features/books/BookWorkspacePage";
import { ImportBookPage } from "@/features/books/ImportBookPage";
import { QualityPage } from "@/features/quality/QualityPage";
import { UpdatesPage } from "@/features/updates/UpdatesPage";
import { WorkbenchPage } from "@/features/workbench/WorkbenchPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.pushState(null, "", "/");
});

test("routes secondary product pages", () => {
  expect(routeForPath("/books")).toEqual({ activePath: "/books", element: <WorkbenchPage /> });
  expect(routeForPath("/books/import").element).toEqual(<ImportBookPage />);
  expect(routeForPath("/books/42/settings").element).toEqual(<BookWorkspacePage bookId={42} view="settings" />);
  expect(routeForPath("/books/42/state").element).toEqual(<BookWorkspacePage bookId={42} view="state" />);
  expect(routeForPath("/books/42/volumes")).toEqual({
    activePath: "/books/:id/chapters",
    element: <BookWorkspacePage bookId={42} view="chapters" />,
  });
  expect(routeForPath("/books/42/chapters").element).toEqual(<BookWorkspacePage bookId={42} view="chapters" />);
  expect(routeForPath("/books/42/chapters/8").element).toEqual(
    <BookWorkspacePage bookId={42} chapterId={8} view="chapters" />,
  );
  expect(routeForPath("/books/42/quality").element).toEqual(<BookWorkspacePage bookId={42} view="quality" />);
  expect(routeForPath("/updates").element).toEqual(<UpdatesPage />);
});

test("legacy review path falls back to the workbench instead of a placeholder", () => {
  expect(routeForPath("/review")).toEqual({ activePath: "/", element: <WorkbenchPage /> });
});

test("import page posts project json and navigates to imported book", async () => {
  const fetchMock = vi.fn(async () =>
    Response.json({
      book: {
        id: 42,
        title: "星港遗梦",
        genre: "科幻",
        audience: "成人",
        status: "producing",
        premise: null,
      },
      redirectTo: "/books/42",
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<ImportBookPage />);

  fireEvent.change(screen.getByLabelText("项目数据"), {
    target: { value: "{\"book\":{\"title\":\"星港遗梦\"}}" },
  });
  fireEvent.click(screen.getByRole("button", { name: "导入项目" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/import",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(window.location.pathname).toBe("/books/42");
});

test("import page rejects malformed success payloads", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({ book: { id: 42 }, redirectTo: "https://evil.test" })),
  );

  render(<ImportBookPage />);

  fireEvent.change(screen.getByLabelText("项目数据"), {
    target: { value: "{\"book\":{\"title\":\"星港遗梦\"}}" },
  });
  fireEvent.click(screen.getByRole("button", { name: "导入项目" }));

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("导入结果格式无效。"));
  expect(window.location.pathname).not.toBe("/books/42");
});

test("quality page renders assets and creates a quality snapshot", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(qualityPayload()))
    .mockResolvedValueOnce(Response.json(qualityPayload({ score: 91 })));
  vi.stubGlobal("fetch", fetchMock);

  render(<QualityPage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "质量中心" })).toBeInTheDocument());
  expect(screen.getByText("雾谷悬疑节奏")).toBeInTheDocument();
  expect(screen.getByText("参考章节")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "刷新质量分析" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/quality/snapshots",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(screen.getByText("91")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "导出文稿" })).toHaveAttribute("href", "/api/books/42/export.md");
  expect(screen.getByRole("link", { name: "导出数据" })).toHaveAttribute("href", "/api/books/42/export.json");
});

test("quality page renders animated AI waiting state while snapshot request is pending", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(qualityPayload()))
    .mockImplementationOnce(
      () =>
        new Promise<Response>(() => {
          // Keep the snapshot request pending so the waiting state stays visible.
        }),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<QualityPage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "质量中心" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "刷新质量分析" }));

  await waitFor(() => expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("刷新分析中..."));
  expect(screen.getByRole("button", { name: /刷新分析中/ })).toBeDisabled();
});

test("quality page rejects malformed payloads", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        ...qualityPayload(),
        latestSnapshot: { id: 4, metrics: null, recommendations: "bad" },
      }),
    ),
  );

  render(<QualityPage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("质量数据格式无效。"));
});

test("updates page checks manifest and renders json result", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        currentVersion: "0.1.0",
        platform: "macos-arm64",
        manifestUrl: "https://github.com/dale0525/MyNovel/releases/latest/download/update-macos-arm64.json",
      }),
    )
    .mockResolvedValueOnce(Response.json({
      result: {
        available: true,
        version: "0.2.0",
        notes: "修复章节恢复。",
        sizeLabel: "120.6 KB",
        publishedAt: "2026-05-11T00:00:00Z",
        sha256: "abc123",
        url: "https://example.test/MyNovel.dmg",
      },
    }));
  vi.stubGlobal("fetch", fetchMock);

  render(<UpdatesPage />);

  await waitFor(() => expect(screen.getByText("当前版本 0.1.0")).toBeInTheDocument());
  expect(screen.queryByLabelText("更新元数据地址")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "检查更新" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/updates/check",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          manifestUrl: "https://github.com/dale0525/MyNovel/releases/latest/download/update-macos-arm64.json",
        }),
      }),
    ),
  );
  expect(screen.getByText("发现新版本 0.2.0")).toBeInTheDocument();
  expect(screen.getByText("修复章节恢复。")).toBeInTheDocument();
});

test("updates page rejects malformed result payloads", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({
          currentVersion: "0.1.0",
          platform: "windows-x64",
          manifestUrl: "https://github.com/dale0525/MyNovel/releases/latest/download/update-windows-x64.json",
        }),
      )
      .mockResolvedValueOnce(Response.json({ result: { available: true } })),
  );

  render(<UpdatesPage />);

  await waitFor(() => expect(screen.getByText("当前版本 0.1.0")).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "检查更新" }));

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("更新结果格式无效。"));
});

test("updates page stages an installer and opens its location", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        currentVersion: "0.1.0",
        platform: "macos-arm64",
        manifestUrl: "https://github.com/dale0525/MyNovel/releases/latest/download/update-macos-arm64.json",
      }),
    )
    .mockResolvedValueOnce(
      Response.json({
        result: updateResultPayload(),
      }),
    )
    .mockResolvedValueOnce(
      Response.json({
        result: updateResultPayload(),
        stagedInstall: {
          planPath: "/Users/me/.mynovel/updates/staged/0.2.0/install-plan.json",
          payload: {
            artifact_path: "/Users/me/.mynovel/updates/staged/0.2.0/MyNovel.dmg",
            db_backup_path: "/Users/me/.mynovel/updates/backups/desktop.backup.sqlite",
          },
        },
      }),
    )
    .mockResolvedValueOnce(Response.json({ openedPath: "/Users/me/.mynovel/updates/staged/0.2.0" }));
  vi.stubGlobal("fetch", fetchMock);

  render(<UpdatesPage />);

  await waitFor(() => expect(screen.getByText("当前版本 0.1.0")).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "检查更新" }));
  await waitFor(() => expect(screen.getByText("发现新版本 0.2.0")).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "下载并准备安装" }));
  await waitFor(() => expect(screen.getByText("更新已准备")).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "打开安装包位置" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/updates/reveal",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          planPath: "/Users/me/.mynovel/updates/staged/0.2.0/install-plan.json",
        }),
      }),
    ),
  );
});

function updateResultPayload() {
  return {
    available: true,
    version: "0.2.0",
    notes: "修复章节恢复。",
    sizeLabel: "120.6 KB",
    publishedAt: "2026-05-11T00:00:00Z",
    sha256: "abc123",
    url: "https://example.test/MyNovel.dmg",
  };
}

function qualityPayload({ score = 73 }: { score?: number } = {}) {
  return {
    book: {
      id: 42,
      title: "星港遗梦",
      genre: "科幻",
      audience: "成人",
      status: "producing",
      premise: "领航员追查失落星港的真相。",
    },
    styleAssets: [
      {
        id: 2,
        bookId: 42,
        name: "雾谷悬疑节奏",
        sourceTitle: "雾谷",
        sourceExcerpt: "雾贴着石阶流动。",
        fingerprint: { average_sentence_chars: 14.2 },
        guidance: { style_rules: ["保持短句推进。"] },
        createdAt: "2026-05-16T00:00:00+00:00",
      },
    ],
    deconstructionStudies: [
      {
        id: 3,
        bookId: 42,
        sourceTitle: "参考章节",
        sourceExcerpt: "莉拉离开村庄。",
        beatMap: [{ beat: "开局钩子", summary: "莉拉离开村庄。" }],
        craftNotes: { reusable_moves: ["先给人物动作，再揭示异常信号。"] },
        createdAt: "2026-05-16T00:00:00+00:00",
      },
    ],
    latestSnapshot: {
      id: 4,
      bookId: 42,
      score,
      metrics: {
        accepted_chapters: 3,
        review_backlog: 1,
        high_risk_issues: 0,
        estimated_chars: 12000,
      },
      recommendations: ["质量状态稳定，可以继续按当前节奏生产。"],
      createdAt: "2026-05-16T00:00:00+00:00",
    },
    costStrategy: {
      mode: "balanced",
      batch_limit: 5,
      context_policy: "保留关键人物、伏笔和最近章节摘要。",
    },
  };
}
