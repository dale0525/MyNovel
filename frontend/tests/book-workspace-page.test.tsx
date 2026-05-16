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
      Response.json(bookPayload({ bookStatus: "canon_locked", includeTrace: true, includeVolumePlan: true })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByText("科幻")).toBeInTheDocument();
  expect(screen.getByText("成人")).toBeInTheDocument();
  expect(screen.getByText("可信设定已锁定")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "继续推进项目" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "查看生成进度" })).toHaveAttribute("href", "/chapters/8");
  expect(screen.getByRole("heading", { name: "可信设定摘要" })).toBeInTheDocument();
  expect(screen.getByText("灯塔会记录航线")).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "章节队列" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "项目工具" }));
  expect(screen.getByRole("heading", { name: "章节队列" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "第 1 章 · 失落灯塔" })).toHaveAttribute("href", "/chapters/8");
  expect(screen.getByRole("heading", { name: "最近 AI 进度" })).toBeInTheDocument();
  expect(screen.getByText("chapter_draft")).toBeInTheDocument();
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
  expect(screen.getByRole("link", { name: "调整可信设定" })).toHaveAttribute("href", "/books/42/state");
  fireEvent.click(screen.getByRole("button", { name: "项目工具" }));
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
  fireEvent.click(screen.getByRole("button", { name: "项目工具" }));
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

test("workspace renders animated AI waiting state while current chapter run is pending", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload({ bookStatus: "canon_locked", chapterStatus: "planned" })))
    .mockImplementationOnce(
      () =>
        new Promise<Response>(() => {
          // Keep the chapter run request pending so the waiting state stays visible.
        }),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "运行当前章节" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "运行当前章节" }));

  await waitFor(() => expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("提交章节中..."));
  expect(screen.getByRole("button", { name: /提交章节中/ })).toBeDisabled();
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
  fireEvent.click(screen.getByRole("button", { name: "项目工具" }));
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

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "项目工具" }));
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

test("workspace surfaces a single review action when a chapter awaits review", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ bookStatus: "canon_locked", chapterStatus: "awaiting_review" })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByRole("heading", { name: "继续推进项目" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "打开章节审核" })).toHaveAttribute("href", "/chapters/8");
  expect(screen.getByRole("region", { name: "影响预览" })).toHaveTextContent("审核后才会写入");
  expect(screen.queryByRole("button", { name: "批量生产" })).not.toBeInTheDocument();
});

test("workspace points blocked draft projects to trusted state instead of production", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ chapterStatus: "planned", includeLatestCanon: false })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByRole("link", { name: "调整可信设定" })).toHaveAttribute("href", "/books/42/state");
  expect(screen.getByRole("region", { name: "影响预览" })).toHaveTextContent("不会启动章节生产");
  expect(screen.queryByRole("button", { name: "运行当前章节" })).not.toBeInTheDocument();
});

test("workspace keeps project tools collapsed until requested", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ bookStatus: "canon_locked", chapterStatus: "planned", includeTrace: true, includeVolumePlan: true })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "批量生产" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("全书目标字数")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "项目工具" }));

  expect(screen.getByRole("button", { name: "批量生产" })).toBeInTheDocument();
  expect(screen.getByLabelText("全书目标字数")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "导出 Markdown" })).toHaveAttribute("href", "/api/books/42/export.md");
});

test("workspace checks trusted state when production-ready projects have no current task", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ bookStatus: "canon_locked", chapterStatus: "accepted" })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByRole("link", { name: "检查可信设定" })).toHaveAttribute("href", "/books/42/state");
  expect(screen.queryByRole("button", { name: "运行当前章节" })).not.toBeInTheDocument();
});

test("workspace runs needs-revision chapters through the primary action", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ bookStatus: "canon_locked", chapterStatus: "needs_revision" })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByRole("button", { name: "运行当前章节" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "影响预览" })).toHaveTextContent("生成候选正文");
  expect(screen.getByRole("region", { name: "影响预览" })).toHaveTextContent("不会直接写入");
  expect(screen.getByRole("region", { name: "影响预览" })).toHaveTextContent("进入章节审核");
});

test("workspace avoids unsafe chapter actions when the current task has no id", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ bookStatus: "canon_locked", chapterId: null, chapterStatus: "planned" })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByRole("link", { name: "检查可信设定" })).toHaveAttribute("href", "/books/42/state");
  expect(screen.queryAllByRole("link").map((link) => link.getAttribute("href"))).not.toContain("/chapters/0");
  expect(screen.queryByRole("button", { name: "运行当前章节" })).not.toBeInTheDocument();
  expect(screen.getByRole("region", { name: "影响预览" })).toHaveTextContent("章节条目不完整");
});

test("workspace shows primary action errors without opening project tools", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload({ bookStatus: "canon_locked", chapterStatus: "planned" })))
    .mockResolvedValueOnce(Response.json({ error: { message: "章节运行失败。" } }, { status: 500 }));
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "运行当前章节" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "运行当前章节" }));

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("章节运行失败。"));
  expect(screen.queryByRole("heading", { name: "章节队列" })).not.toBeInTheDocument();
});

function bookPayload({
  bookStatus = "draft",
  chapterId = 8,
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
