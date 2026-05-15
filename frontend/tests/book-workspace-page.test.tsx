import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { BookWorkspacePage } from "@/features/books/BookWorkspacePage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("renders book workspace details", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ includeTrace: true, includeVolumePlan: true })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByText("科幻 · 成人 · 草稿")).toBeInTheDocument();
  expect(screen.getByText("领航员追查失落星港的真相。")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "当前任务" })).toBeInTheDocument();
  expect(screen.getAllByText("第 1 章 · 失落灯塔")).toHaveLength(2);
  expect(screen.getByRole("heading", { name: "章节队列" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "可信设定摘要" })).toBeInTheDocument();
  expect(screen.getByText("灯塔会记录航线")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "最近 AI 进度" })).toBeInTheDocument();
  expect(screen.getByText("chapter_draft")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "打开当前章节" })).toHaveAttribute("href", "/chapters/8");
  expect(screen.getByRole("link", { name: "第 1 章 · 失落灯塔" })).toHaveAttribute("href", "/chapters/8");
  expect(screen.getByRole("link", { name: "质量中心" })).toHaveAttribute("href", "/books/42/quality");
  expect(screen.getByRole("link", { name: "导出 Markdown" })).toHaveAttribute("href", "/api/books/42/export.md");
  expect(screen.getByRole("link", { name: "导出 JSON" })).toHaveAttribute("href", "/api/books/42/export.json");
});

test("does not treat accepted chapters as the current task", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ chapterStatus: "accepted", chapterTitle: "已完成灯塔", chapterSummary: "这一章已经接受。" })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByText("暂无待推进章节。可以先检查可信设定，再创建章节生产任务。")).toBeInTheDocument();
  expect(screen.getByText("已接受 · 1200 字")).toBeInTheDocument();
});

test("workspace runs planned chapters and batch production through api actions", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload({ bookStatus: "canon_locked", chapterStatus: "planned" })))
    .mockResolvedValueOnce(Response.json({ chapterId: 8, redirectTo: "/chapters/8" }, { status: 202 }))
    .mockResolvedValueOnce(Response.json({ chapterId: 9, redirectTo: "/chapters/9" }, { status: 202 }));
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "运行当前章节" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "运行当前章节" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chapters/8/run",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(window.location.pathname).toBe("/chapters/8");

  window.history.pushState(null, "", "/books/42");
  fireEvent.change(screen.getByLabelText("批量章节数"), { target: { value: "3" } });
  fireEvent.click(screen.getByRole("button", { name: "批量生产" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/chapters/run-batch",
      expect.objectContaining({
        method: "POST",
        body: "{\"limit\":3}",
      }),
    ),
  );
  expect(window.location.pathname).toBe("/chapters/9");
});

test("workspace hides production actions before trusted state is locked", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ chapterStatus: "planned", includeLatestCanon: false })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "运行当前章节" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "批量生产" })).not.toBeInTheDocument();
  expect(screen.getByText("可信设定锁定后才能批量生产章节。")).toBeInTheDocument();
});

test("workspace saves word targets through json api", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload()))
    .mockResolvedValueOnce(
      Response.json(bookPayload({ targetWordCount: 300000, chapterWordCount: 3200 })),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByLabelText("全书目标字数")).toHaveValue(120000));
  fireEvent.change(screen.getByLabelText("全书目标字数"), { target: { value: "300000" } });
  fireEvent.change(screen.getByLabelText("单章目标字数"), { target: { value: "3200" } });
  fireEvent.click(screen.getByLabelText("同步更新已有章节计划"));
  fireEvent.click(screen.getByRole("button", { name: "保存目标字数" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/word-targets",
      expect.objectContaining({
        method: "POST",
        body: "{\"targetWordCount\":300000,\"chapterWordCount\":3200,\"updateExistingChapters\":true}",
      }),
    ),
  );
  expect(screen.getByRole("status")).toHaveTextContent("目标字数已保存。");
});

test("aborts in-flight book fetch on unmount", () => {
  let signal: AbortSignal | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      signal = init?.signal ?? undefined;
      return new Promise<Response>(() => {});
    }),
  );

  const { unmount } = render(<BookWorkspacePage bookId={42} />);

  expect(signal?.aborted).toBe(false);
  unmount();
  expect(signal?.aborted).toBe(true);
});

function bookPayload({
  bookStatus = "draft",
  chapterStatus = "running",
  chapterTitle = "失落灯塔",
  chapterSummary = "领航员发现星港残影。",
  targetWordCount = 120000,
  chapterWordCount = 2800,
  includeLatestCanon = true,
  includeTrace = false,
  includeVolumePlan = false,
}: {
  bookStatus?: string;
  chapterStatus?: string;
  chapterTitle?: string;
  chapterSummary?: string;
  targetWordCount?: number;
  chapterWordCount?: number;
  includeLatestCanon?: boolean;
  includeTrace?: boolean;
  includeVolumePlan?: boolean;
} = {}) {
  return {
    book: {
      id: 42,
      title: "星港遗梦",
      genre: "科幻",
      audience: "成人",
      status: bookStatus,
      premise: "领航员追查失落星港的真相。",
    },
    wordTargets: {
      targetWordCount,
      chapterWordCount,
    },
    chapters: [
      {
        id: 8,
        bookId: 42,
        number: 1,
        title: chapterTitle,
        status: chapterStatus,
        summary: chapterSummary,
        wordCount: 1200,
        reviewerNote: null,
        updatedAt: "2026-05-16T00:00:00+00:00",
      },
    ],
    latestCanon: includeLatestCanon
      ? {
          id: 3,
          bookId: 42,
          version: 2,
          content: {
            world_rules: [{ rule: "灯塔会记录航线" }],
            characters: [{ name: "岑星" }],
            chapter_summaries: [],
          },
          createdAt: "2026-05-16T00:00:00+00:00",
        }
      : null,
    runTraces: includeTrace
      ? [
          {
            id: 5,
            bookId: 42,
            stage: "chapter_draft",
            promptId: "chapter_draft",
            promptVersion: "1",
            model: "gpt-test",
            cost: { tokens: 1200 },
            metadata: { chapter: 1 },
            createdAt: "2026-05-16T00:00:00+00:00",
          },
        ]
      : [],
    volumePlans: includeVolumePlan
      ? [
          {
            id: 2,
            bookId: 42,
            volumeNumber: 1,
            title: "星港卷",
            coreConflict: "寻找失落星港。",
            pacingCurve: ["悬疑", "突破"],
            payoffDistribution: ["灯塔真相"],
            keyTurns: ["发现灯塔", "进入星港"],
            commitments: ["不背离星港谜题"],
          },
        ]
      : [],
  };
}
