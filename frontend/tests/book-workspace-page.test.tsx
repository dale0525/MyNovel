import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { BookWorkspacePage } from "@/features/books/BookWorkspacePage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("renders the simplified project workspace sections", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ bookStatus: "canon_locked", includeTrace: true, includeVolumePlan: true })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByRole("heading", { name: "基本信息" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "项目设定" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "设定" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "卷纲列表" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "章节列表" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "批量操作" })).toBeInTheDocument();
  expect(screen.getByText("科幻")).toBeInTheDocument();
  expect(screen.getByText("成人")).toBeInTheDocument();
  expect(screen.getByText("可信设定已锁定")).toBeInTheDocument();
  expect(screen.getByText("灯塔会记录航线")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "打开设定" })).toHaveAttribute("href", "/books/42/state");
  expect(screen.getByRole("link", { name: "第 1 章 · 失落灯塔" })).toHaveAttribute("href", "/chapters/8");
  expect(screen.queryByRole("heading", { name: "继续推进项目" })).not.toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "影响预览" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "最近 AI 进度" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "质量中心" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "导出 Markdown" })).not.toBeInTheDocument();
});

test("keeps accepted chapters in their volume list without a current-task panel", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ chapterStatus: "accepted", chapterTitle: "已完成灯塔", chapterSummary: "这一章已经接受。" })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByRole("link", { name: "第 1 章 · 已完成灯塔" })).toHaveAttribute("href", "/chapters/8");
  expect(screen.getByText("已接受 · 1200 字")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "运行当前章节" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "调整可信设定" })).not.toBeInTheDocument();
});

test("runs batch production through the project batch action", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload({ bookStatus: "canon_locked", chapterStatus: "planned" })))
    .mockResolvedValueOnce(
      streamResponse([{ type: "chunk", text: "正在批量推进章节" }, { type: "done", chapterId: 9, redirectTo: "/chapters/9" }]),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "批量生成" })).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("生成章节数"), { target: { value: "3" } });
  fireEvent.click(screen.getByRole("button", { name: "批量生成" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/chapters/run-batch-stream",
      expect.objectContaining({
        method: "POST",
        body: "{\"limit\":3}",
      }),
    ),
  );
  expect(screen.getByRole("status")).toHaveTextContent("正在批量推进章节");
  expect(window.location.pathname).toBe("/chapters/9");
});

test("shows animated waiting state while batch production is pending", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload({ bookStatus: "canon_locked", chapterStatus: "planned" })))
    .mockImplementationOnce(
      () =>
        new Promise<Response>(() => {
          // Keep the batch request pending so the waiting state stays visible.
        }),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "批量生成" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "批量生成" }));

  await waitFor(() => expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("提交批量中..."));
  expect(screen.getByRole("button", { name: /提交批量中/ })).toBeDisabled();
});

test("hides batch production before trusted state is locked", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ chapterStatus: "planned", includeLatestCanon: false })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "批量生成" })).not.toBeInTheDocument();
  expect(screen.getByText("可信设定锁定后才能批量生成章节。")).toBeInTheDocument();
});

test("saves word targets through the project settings form", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload()))
    .mockResolvedValueOnce(
      Response.json(bookPayload({ targetWordCount: 300000, chapterWordCount: 3200 })),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByLabelText("全书目标字数")).toHaveValue(120000);
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
  expect(screen.getByText("目标字数已保存。")).toBeInTheDocument();
});

test("generates volume outline through streaming api and refreshes volume chapters", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload({ bookStatus: "canon_locked", includeVolumePlan: false })))
    .mockResolvedValueOnce(
      streamResponse([
        { type: "chunk", text: "正在规划卷纲" },
        { type: "done", book: bookPayload({ bookStatus: "canon_locked", includeVolumePlan: true, chapterTitle: "灯塔回声" }) },
      ]),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "让 AI 生成卷纲" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "让 AI 生成卷纲" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/volume-outline/generate-stream",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(screen.getAllByRole("status").some((item) => item.textContent?.includes("正在规划卷纲"))).toBe(true);
  await waitFor(() => expect(screen.getByText("第 1 卷 · 星港卷")).toBeInTheDocument());
  expect(screen.getByRole("link", { name: "第 1 章 · 灯塔回声" })).toHaveAttribute("href", "/chapters/8");
});

test("groups chapters under the volume recorded in their chapter plan", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(
        bookPayload({
          bookStatus: "canon_locked",
          chapterNumber: 12,
          chapterVolumeNumber: 1,
          includeVolumePlan: true,
        }),
      ),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByText("第 1 卷 · 星港卷")).toBeInTheDocument());
  expect(screen.getByRole("link", { name: "第 12 章 · 失落灯塔" })).toHaveAttribute("href", "/chapters/8");
});

test("shows animated waiting state while volume outline generation is pending", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload({ bookStatus: "canon_locked", includeVolumePlan: false })))
    .mockImplementationOnce(
      () =>
        new Promise<Response>(() => {
          // Keep the volume outline request pending so the waiting state stays visible.
        }),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "让 AI 生成卷纲" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "让 AI 生成卷纲" }));

  await waitFor(() => expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("生成卷纲中..."));
  expect(screen.getByRole("button", { name: /生成卷纲中/ })).toBeDisabled();
});

test("keeps project sections visible when batch action fails", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload({ bookStatus: "canon_locked", chapterStatus: "planned" })))
    .mockResolvedValueOnce(Response.json({ error: { message: "批量生成失败。" } }, { status: 500 }));
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "批量生成" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "批量生成" }));

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("批量生成失败。"));
  expect(screen.getByRole("heading", { name: "章节列表" })).toBeInTheDocument();
});

test("avoids unsafe chapter links when planned chapters have no id", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ bookStatus: "canon_locked", chapterId: null, chapterStatus: "planned" })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByText("第 1 章 · 失落灯塔")).toBeInTheDocument();
  expect(screen.queryAllByRole("link").map((link) => link.getAttribute("href"))).not.toContain("/chapters/0");
  expect(screen.queryByRole("button", { name: "运行当前章节" })).not.toBeInTheDocument();
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
  chapterId = 8,
  chapterNumber = 1,
  chapterVolumeNumber,
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
  chapterId?: number | null;
  chapterNumber?: number;
  chapterVolumeNumber?: number | null;
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
        id: chapterId,
        bookId: 42,
        number: chapterNumber,
        title: chapterTitle,
        status: chapterStatus,
        summary: chapterSummary,
        wordCount: 1200,
        reviewerNote: null,
        updatedAt: "2026-05-16T00:00:00+00:00",
        ...(chapterVolumeNumber !== undefined ? { volumeNumber: chapterVolumeNumber } : {}),
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

function streamResponse(events: Array<Record<string, unknown>>): Response {
  return new Response(events.map((event) => JSON.stringify(event)).join("\n"));
}
