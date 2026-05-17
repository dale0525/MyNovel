import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { BookWorkspacePage } from "@/features/books/BookWorkspacePage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("renders a compact project overview with second-level navigation", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ bookStatus: "canon_locked", includeTrace: true, includeVolumePlan: true })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByRole("heading", { name: "项目概括" })).toBeInTheDocument();
  expect(screen.getByText("科幻")).toBeInTheDocument();
  expect(screen.getByText("成人")).toBeInTheDocument();
  expect(screen.getAllByText("可信设定已锁定").length).toBeGreaterThan(0);
  expect(screen.getByText("领航员追查失落星港的真相。")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /项目设置/ })).toHaveAttribute("href", "/books/42/settings");
  expect(screen.getByRole("link", { name: /可信设定/ })).toHaveAttribute("href", "/books/42/state");
  expect(screen.getAllByRole("link", { name: /卷纲/ }).some((link) => link.getAttribute("href") === "/books/42/volumes")).toBe(true);
  expect(screen.getAllByRole("link", { name: /章节/ }).some((link) => link.getAttribute("href") === "/books/42/chapters")).toBe(true);
  expect(screen.queryByRole("heading", { name: "项目设定" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "卷纲列表" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "卷纲" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "批量操作" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "第 1 章 · 失落灯塔" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "继续推进项目" })).not.toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "影响预览" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "最近 AI 进度" })).not.toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: /质量/ }).some((link) => link.getAttribute("href") === "/books/42/quality")).toBe(true);
  expect(screen.queryByRole("link", { name: "导出文稿" })).not.toBeInTheDocument();
});

test("renders trusted state as content inside the project tab frame", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload({ bookStatus: "canon_locked" })))
    .mockResolvedValueOnce(Response.json(trustedStatePayload()));
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} view="state" />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByRole("link", { name: "设定" })).toHaveAttribute("aria-current", "page");
  await waitFor(() => expect(screen.getByRole("textbox", { name: "全部设定修改意见" })).toBeInTheDocument());
  expect(screen.getByText("世界规则")).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "设定" })).not.toBeInTheDocument();
});

test("renders quality center as content inside the project tab frame", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload({ bookStatus: "producing" })))
    .mockResolvedValueOnce(Response.json(qualityPayload()));
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} view="quality" />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByRole("link", { name: "质量" })).toHaveAttribute("aria-current", "page");
  await waitFor(() => expect(screen.getByRole("heading", { name: "长期质量分析" })).toBeInTheDocument());
  expect(screen.getByRole("link", { name: "导出文稿" })).toHaveAttribute("href", "/api/books/42/export.md");
  expect(screen.queryByRole("heading", { name: "质量中心" })).not.toBeInTheDocument();
});

test("volume outline tab expands one volume row before showing its chapters", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(multiVolumeBookPayload())),
  );

  render(<BookWorkspacePage bookId={42} view="volumes" />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "卷纲" })).toBeInTheDocument());
  expect(screen.getByRole("textbox", { name: "所有卷修改意见" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /第一卷 · 星港卷/ })).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("link", { name: "第 1 章 · 失落灯塔" })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /第一卷 · 星港卷/ }));

  expect(screen.getByRole("button", { name: /第一卷 · 星港卷/ })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("button", { name: "收起全部" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "第 1 章 · 失落灯塔" })).toHaveAttribute(
    "href",
    "/books/42/chapters/8",
  );
  expect(screen.queryByRole("link", { name: "第 11 章 · 深空裂缝" })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "收起全部" }));

  expect(screen.getByRole("button", { name: /第一卷 · 星港卷/ })).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("button", { name: "收起全部" })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /第二卷 · 深空卷/ }));

  expect(screen.getByRole("button", { name: /第一卷 · 星港卷/ })).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByRole("button", { name: /第二卷 · 深空卷/ })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("link", { name: "第 11 章 · 深空裂缝" })).toHaveAttribute(
    "href",
    "/books/42/chapters/9",
  );
  expect(screen.queryByRole("link", { name: "第 1 章 · 失落灯塔" })).not.toBeInTheDocument();
});

test("renders a selected chapter workspace inside the chapter tab", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload({ bookStatus: "producing", includeVolumePlan: true })))
    .mockResolvedValueOnce(Response.json(chapterPayload()));
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} chapterId={8} view="chapters" />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByRole("link", { name: "章节" })).toHaveAttribute("aria-current", "page");
  await waitFor(() => expect(screen.getByRole("heading", { name: "失落灯塔" })).toBeInTheDocument());
  expect(screen.getByRole("link", { name: "返回章节" })).toHaveAttribute("href", "/books/42/chapters");
});

test("chapter tab lists accepted chapters without a current-task panel", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ chapterStatus: "accepted", chapterTitle: "已完成灯塔", chapterSummary: "这一章已经接受。" })),
    ),
  );

  render(<BookWorkspacePage bookId={42} view="chapters" />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByRole("heading", { name: "章节" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "第 1 章 · 已完成灯塔" })).toHaveAttribute(
    "href",
    "/books/42/chapters/8",
  );
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

  render(<BookWorkspacePage bookId={42} view="chapters" />);

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
  expect(window.location.pathname).toBe("/books/42/chapters/9");
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

  render(<BookWorkspacePage bookId={42} view="chapters" />);

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

  render(<BookWorkspacePage bookId={42} view="chapters" />);

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

  render(<BookWorkspacePage bookId={42} view="settings" />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByLabelText("全书目标字数")).toHaveValue(120000);
  fireEvent.change(screen.getByLabelText("全书目标字数"), { target: { value: "300000" } });
  fireEvent.change(screen.getByLabelText("单章目标字数"), { target: { value: "3200" } });
  fireEvent.click(screen.getByLabelText("同步更新待生产章节计划"));
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
        {
          type: "done",
          book: bookPayload({
            bookStatus: "canon_locked",
            chapterTitle: "灯塔回声",
            chapterVolumeNumber: 1,
            includeVolumePlan: true,
          }),
        },
      ]),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} view="volumes" />);

  await waitFor(() => expect(screen.getByRole("button", { name: "补全卷纲" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "补全卷纲" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/volume-outline/generate-stream",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(screen.getAllByRole("status").some((item) => item.textContent?.includes("正在规划卷纲"))).toBe(true);
  await waitFor(() => expect(screen.getAllByText("第一卷 · 星港卷").length).toBeGreaterThan(0));
  fireEvent.click(screen.getByRole("button", { name: /第一卷 · 星港卷/ }));
  expect(screen.getByRole("link", { name: "第 1 章 · 灯塔回声" })).toHaveAttribute(
    "href",
    "/books/42/chapters/8",
  );
});

test("hides volume completion button when chapter planning already covers the target", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(
        bookPayload({
          bookStatus: "canon_locked",
          chapterVolumeNumber: 1,
          includeVolumePlan: true,
          targetWordCount: 2800,
          chapterWordCount: 2800,
        }),
      ),
    ),
  );

  render(<BookWorkspacePage bookId={42} view="volumes" />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "卷纲" })).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "补全卷纲" })).not.toBeInTheDocument();
  expect(screen.getByText("规划缺口")).toBeInTheDocument();
  expect(screen.getByText("0 章")).toBeInTheDocument();
});

test("expanded volume row submits chapter notes and refreshes chapters", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json(
        bookPayload({
          bookStatus: "canon_locked",
          chapterVolumeNumber: 1,
          includeVolumePlan: true,
        }),
      ),
    )
    .mockResolvedValueOnce(
      streamResponse([
        { type: "chunk", text: "正在修订本卷章节" },
        {
          type: "done",
          book: bookPayload({
            bookStatus: "canon_locked",
            chapterTitle: "灯塔追击",
            chapterVolumeNumber: 1,
            includeVolumePlan: true,
          }),
        },
      ]),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} view="volumes" />);

  await waitFor(() => expect(screen.getByRole("button", { name: /第一卷 · 星港卷/ })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: /第一卷 · 星港卷/ }));
  await waitFor(() => expect(screen.getByRole("textbox", { name: "这一卷修改意见" })).toBeInTheDocument());
  expect(screen.getByRole("button", { name: "章节" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "概括" })).toHaveAttribute("aria-pressed", "false");

  fireEvent.change(screen.getByLabelText("这一卷修改意见"), {
    target: { value: "第二章提前进入灯塔追击。" },
  });
  fireEvent.click(screen.getByRole("button", { name: "让 AI 修改这一卷" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/volume-outline/revise-stream",
      expect.objectContaining({
        method: "POST",
        body: "{\"scope\":\"volume_chapters\",\"volumeNumber\":1,\"revisionNotes\":\"第二章提前进入灯塔追击。\"}",
      }),
    ),
  );
  expect(screen.getAllByRole("status").some((item) => item.textContent?.includes("正在修订本卷章节"))).toBe(true);
  await waitFor(() => expect(screen.getByRole("link", { name: "第 1 章 · 灯塔追击" })).toBeInTheDocument());
});

test("expanded volume row can submit summary notes", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json(
        bookPayload({
          bookStatus: "canon_locked",
          chapterVolumeNumber: 1,
          includeVolumePlan: true,
        }),
      ),
    )
    .mockResolvedValueOnce(
      streamResponse([
        {
          type: "done",
          book: bookPayload({
            bookStatus: "canon_locked",
            chapterVolumeNumber: 1,
            includeVolumePlan: true,
          }),
        },
      ]),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} view="volumes" />);

  await waitFor(() => expect(screen.getByRole("button", { name: /第一卷 · 星港卷/ })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: /第一卷 · 星港卷/ }));
  await waitFor(() => expect(screen.getByRole("textbox", { name: "这一卷修改意见" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "概括" }));
  fireEvent.change(screen.getByLabelText("这一卷修改意见"), {
    target: { value: "这一卷核心冲突更明确。" },
  });
  fireEvent.click(screen.getByRole("button", { name: "让 AI 修改这一卷" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/volume-outline/revise-stream",
      expect.objectContaining({
        method: "POST",
        body: "{\"scope\":\"volume_summary\",\"volumeNumber\":1,\"revisionNotes\":\"这一卷核心冲突更明确。\"}",
      }),
    ),
  );
});

test("global volume revision form can revise all volume summaries", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json(
        bookPayload({
          bookStatus: "canon_locked",
          chapterVolumeNumber: 1,
          includeVolumePlan: true,
        }),
      ),
    )
    .mockResolvedValueOnce(
      streamResponse([
        {
          type: "done",
          book: {
            ...bookPayload({
              bookStatus: "canon_locked",
              chapterVolumeNumber: 1,
              includeVolumePlan: true,
            }),
            volumePlans: [
              {
                ...bookPayload({ includeVolumePlan: true }).volumePlans[0],
                title: "重写后的星港卷",
              },
            ],
          },
        },
      ]),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} view="volumes" />);

  await waitFor(() => expect(screen.getByRole("textbox", { name: "所有卷修改意见" })).toBeInTheDocument());
  fireEvent.change(screen.getByRole("textbox", { name: "所有卷修改意见" }), {
    target: { value: "全书卷名更偏悬疑。" },
  });
  fireEvent.click(screen.getByRole("button", { name: "根据已生产章节修改所有卷" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/volume-outline/revise-stream",
      expect.objectContaining({
        method: "POST",
        body: "{\"scope\":\"all_volumes\",\"revisionNotes\":\"全书卷名更偏悬疑。\"}",
      }),
    ),
  );
  await waitFor(() => expect(screen.getAllByText("第一卷 · 重写后的星港卷").length).toBeGreaterThan(0));
});

test("global volume revision applies done event without waiting for stream close", async () => {
  let streamController: ReadableStreamDefaultController<Uint8Array> | null = null;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      streamController = controller;
    },
  });
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json(
        bookPayload({
          bookStatus: "canon_locked",
          chapterVolumeNumber: 1,
          includeVolumePlan: true,
        }),
      ),
    )
    .mockResolvedValueOnce(
      new Response(stream, {
        headers: { "Content-Type": "application/x-ndjson; charset=utf-8" },
      }),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} view="volumes" />);

  await waitFor(() => expect(screen.getByRole("textbox", { name: "所有卷修改意见" })).toBeInTheDocument());
  fireEvent.change(screen.getByRole("textbox", { name: "所有卷修改意见" }), {
    target: { value: "全书卷名更偏悬疑。" },
  });
  fireEvent.click(screen.getByRole("button", { name: "根据已生产章节修改所有卷" }));

  await waitFor(() => expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("修订卷纲中..."));
  pushStreamEvent(streamController, {
    type: "done",
    message: "卷纲已修订。",
    book: {
      ...bookPayload({
        bookStatus: "canon_locked",
        chapterVolumeNumber: 1,
        includeVolumePlan: true,
      }),
      volumePlans: [
        {
          ...bookPayload({ includeVolumePlan: true }).volumePlans[0],
          title: "重写后的星港卷",
        },
      ],
    },
  });

  try {
    await waitFor(() => expect(screen.getAllByText("第一卷 · 重写后的星港卷").length).toBeGreaterThan(0), {
      timeout: 300,
    });
    expect(screen.getByRole("button", { name: "根据已生产章节修改所有卷" })).not.toBeDisabled();
  } finally {
    closeStream(streamController);
  }
});

test("volume revision shows animated waiting state while request is pending", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json(
        bookPayload({
          bookStatus: "canon_locked",
          chapterVolumeNumber: 1,
          includeVolumePlan: true,
        }),
      ),
    )
    .mockImplementationOnce(
      () =>
        new Promise<Response>(() => {
          // Keep the volume revision request pending so the waiting state stays visible.
        }),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} view="volumes" />);

  await waitFor(() => expect(screen.getByRole("button", { name: /第一卷 · 星港卷/ })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: /第一卷 · 星港卷/ }));
  await waitFor(() => expect(screen.getByRole("textbox", { name: "这一卷修改意见" })).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("这一卷修改意见"), {
    target: { value: "第二章提前进入灯塔追击。" },
  });
  fireEvent.click(screen.getByRole("button", { name: "让 AI 修改这一卷" }));

  await waitFor(() => expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("修订卷纲中..."));
  expect(screen.getByRole("button", { name: /修订卷纲中/ })).toBeDisabled();
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

  render(<BookWorkspacePage bookId={42} view="volumes" />);

  await waitFor(() => expect(screen.getAllByText("第一卷 · 星港卷").length).toBeGreaterThan(0));
  fireEvent.click(screen.getByRole("button", { name: /第一卷 · 星港卷/ }));
  expect(screen.getByRole("link", { name: "第 12 章 · 失落灯塔" })).toHaveAttribute(
    "href",
    "/books/42/chapters/8",
  );
});

test("treats unmarked first ten blueprint chapters as the first volume", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(
        bookPayload({
          bookStatus: "canon_locked",
          chapterNumber: 10,
          includeVolumePlan: true,
        }),
      ),
    ),
  );

  render(<BookWorkspacePage bookId={42} view="volumes" />);

  await waitFor(() => expect(screen.getAllByText("第一卷 · 星港卷").length).toBeGreaterThan(0));
  fireEvent.click(screen.getByRole("button", { name: /第一卷 · 星港卷/ }));
  expect(screen.getByRole("link", { name: "第 10 章 · 失落灯塔" })).toHaveAttribute(
    "href",
    "/books/42/chapters/8",
  );
  expect(screen.queryByText("未分卷章节")).not.toBeInTheDocument();
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

  render(<BookWorkspacePage bookId={42} view="volumes" />);

  await waitFor(() => expect(screen.getByRole("button", { name: "补全卷纲" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "补全卷纲" }));

  await waitFor(() => expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("补全卷纲中..."));
  expect(screen.getByRole("button", { name: /补全卷纲中/ })).toBeDisabled();
});

test("keeps project sections visible when batch action fails", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload({ bookStatus: "canon_locked", chapterStatus: "planned" })))
    .mockResolvedValueOnce(Response.json({ error: { message: "批量生成失败。" } }, { status: 500 }));
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} view="chapters" />);

  await waitFor(() => expect(screen.getByRole("button", { name: "批量生成" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "批量生成" }));

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("批量生成失败。"));
  expect(screen.getByRole("heading", { name: "章节" })).toBeInTheDocument();
});

test("avoids unsafe chapter links when planned chapters have no id", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ bookStatus: "canon_locked", chapterId: null, chapterStatus: "planned" })),
    ),
  );

  render(<BookWorkspacePage bookId={42} view="chapters" />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByText("第 1 章 · 失落灯塔")).toBeInTheDocument();
  expect(screen.queryAllByRole("link").map((link) => link.getAttribute("href"))).not.toContain("/books/42/chapters/0");
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

function multiVolumeBookPayload() {
  const payload = bookPayload({ bookStatus: "canon_locked", includeVolumePlan: true, chapterVolumeNumber: 1 });
  return {
    ...payload,
    chapters: [
      {
        ...payload.chapters[0],
        id: 8,
        number: 1,
        title: "失落灯塔",
        volumeNumber: 1,
      },
      {
        ...payload.chapters[0],
        id: 9,
        number: 11,
        title: "深空裂缝",
        status: "planned",
        volumeNumber: 2,
      },
    ],
    volumePlans: [
      payload.volumePlans[0],
      {
        id: 3,
        bookId: 42,
        volumeNumber: 2,
        title: "深空卷",
        coreConflict: "星港裂缝开始吞没航线。",
        pacingCurve: ["扩张", "反转"],
        payoffDistribution: ["裂缝来源"],
        keyTurns: ["发现裂缝", "失去坐标"],
        commitments: ["保持星港谜题主线"],
      },
    ],
  };
}

function trustedStatePayload() {
  return {
    book: {
      id: 42,
      title: "星港遗梦",
      genre: "科幻",
      audience: "成人",
      status: "canon_locked",
      premise: "领航员追查失落星港的真相。",
    },
    latestCanon: {
      id: 3,
      bookId: 42,
      version: 2,
      content: { world_rules: ["灯塔会记录航线"] },
      createdAt: "2026-05-16T00:00:00+00:00",
    },
    canonSections: [
      {
        key: "world_rules",
        anchor: "world_rules",
        label: "世界规则",
        editable: true,
        locked: false,
        content: ["灯塔会记录航线"],
      },
    ],
    sectionLocks: {},
    readiness: {
      complete: true,
      missingSections: [],
      messages: [],
    },
    pendingRevisions: [],
    selectedRevision: null,
  };
}

function qualityPayload() {
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
        id: 1,
        bookId: 42,
        name: "雾谷悬疑节奏",
        sourceTitle: "参考章节",
        sourceExcerpt: "短句推进，长句收束。",
        fingerprint: {},
        guidance: {},
        createdAt: "2026-05-16T00:00:00+00:00",
      },
    ],
    deconstructionStudies: [],
    latestSnapshot: {
      id: 2,
      bookId: 42,
      score: 88,
      metrics: { accepted_chapters: 3, review_backlog: 1 },
      recommendations: ["补强卷一中段节奏"],
      createdAt: "2026-05-16T00:00:00+00:00",
    },
    costStrategy: {
      mode: "balanced",
      batch_limit: 2,
      context_policy: "recent-first",
    },
  };
}

function chapterPayload() {
  return {
    book: {
      id: 42,
      title: "星港遗梦",
      genre: "科幻",
      audience: "成人",
      status: "producing",
      premise: "领航员追查失落星港的真相。",
    },
    chapter: {
      id: 8,
      bookId: 42,
      number: 1,
      title: "失落灯塔",
      status: "awaiting_review",
      summary: "岑星抵达灯塔。",
      wordCount: 1200,
      reviewerNote: null,
      updatedAt: "2026-05-16T00:00:00+00:00",
      plan: { goal: "进入灯塔" },
      contextPackage: {},
      draftText: "岑星抵达灯塔。",
      revisedText: "岑星抵达灯塔。",
      finalText: "",
      auditReport: {},
      stateDelta: {},
    },
    siblingChapters: [],
    latestCanon: null,
    traces: [],
    stageSlots: [],
  };
}

function streamResponse(events: Array<Record<string, unknown>>): Response {
  return new Response(events.map((event) => JSON.stringify(event)).join("\n"));
}

function pushStreamEvent(
  controller: ReadableStreamDefaultController<Uint8Array> | null,
  event: Record<string, unknown>,
) {
  if (!controller) {
    throw new Error("Stream controller is not ready.");
  }
  controller.enqueue(new TextEncoder().encode(`${JSON.stringify(event)}\n`));
}

function closeStream(controller: ReadableStreamDefaultController<Uint8Array> | null) {
  try {
    controller?.close();
  } catch {
    return;
  }
}
