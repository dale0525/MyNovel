import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { BookWorkspacePage } from "@/features/books/BookWorkspacePage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("shows animated waiting state while batch production is pending", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload()))
    .mockImplementationOnce(
      () =>
        new Promise<Response>(() => {
          // Keep the batch request pending so the waiting state stays visible.
        }),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} view="chapters" />);

  await waitFor(() => expect(screen.getByRole("button", { name: "选择章节后生成" })).toBeInTheDocument());
  fireEvent.click(screen.getByLabelText("选择第 1 章 · 失落灯塔"));
  fireEvent.click(screen.getByRole("button", { name: "生成选中的 1 章" }));

  await waitFor(() => expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("提交批量中..."));
  expect(screen.getByRole("button", { name: /提交批量中/ })).toBeDisabled();
});

test("moves batch production stage progress into the submit button", async () => {
  let streamController: ReadableStreamDefaultController<Uint8Array> | null = null;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      streamController = controller;
    },
  });
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload()))
    .mockResolvedValueOnce(
      new Response(stream, {
        headers: { "Content-Type": "application/x-ndjson; charset=utf-8" },
      }),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} view="chapters" />);

  await waitFor(() => expect(screen.getByRole("button", { name: "选择章节后生成" })).toBeInTheDocument());
  fireEvent.click(screen.getByLabelText("选择第 1 章 · 失落灯塔"));
  fireEvent.click(screen.getByRole("button", { name: "生成选中的 1 章" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/books/42/chapters/run-batch-stream", expect.any(Object)));
  pushStreamEvent(streamController, { type: "stage", stage: "audit", message: "正在审计风险。" });
  pushStreamEvent(streamController, { type: "chunk", stage: "audit", text: "正文模型片段" });

  try {
    await waitFor(() => expect(screen.getByRole("button", { name: /正在审计风险/ })).toBeDisabled());
    await waitFor(() =>
      expect(screen.getAllByRole("status").some((item) => item.textContent?.includes("正文模型片段"))).toBe(true),
    );
    expect(screen.getAllByRole("status").some((item) => item.textContent?.includes("正在审计风险"))).toBe(false);
  } finally {
    closeStream(streamController);
  }
});

test("counts each batch production stage as one progress step", async () => {
  let streamController: ReadableStreamDefaultController<Uint8Array> | null = null;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      streamController = controller;
    },
  });
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(bookPayload()))
    .mockResolvedValueOnce(
      new Response(stream, {
        headers: { "Content-Type": "application/x-ndjson; charset=utf-8" },
      }),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BookWorkspacePage bookId={42} view="chapters" />);

  await waitFor(() => expect(screen.getByRole("button", { name: "选择章节后生成" })).toBeInTheDocument());
  fireEvent.click(screen.getByLabelText("选择第 1 章 · 失落灯塔"));
  fireEvent.click(screen.getByRole("button", { name: "生成选中的 1 章" }));

  try {
    await waitFor(() => expect(screen.getByRole("progressbar", { name: "批量生成进度" })).toHaveAttribute("aria-valuemax", "5"));
    expect(screen.getByRole("progressbar", { name: "批量生成进度" })).toHaveAttribute("aria-valuenow", "0");

    pushStreamEvent(streamController, { type: "stage", stage: "plan", message: "正在规划本章。" });
    pushStreamEvent(streamController, { type: "stage", stage: "draft", message: "正在生成草稿。" });

    await waitFor(() => expect(screen.getByRole("progressbar", { name: "批量生成进度" })).toHaveAttribute("aria-valuenow", "2"));
    expect(screen.getByText("2/5 步")).toBeInTheDocument();
  } finally {
    closeStream(streamController);
  }
});

test("batch production controls avoid the chapter action divider style", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(bookPayload())));

  render(<BookWorkspacePage bookId={42} view="chapters" />);

  await waitFor(() => expect(screen.getByRole("form", { name: "批量生成控制" })).toBeInTheDocument());
  expect(screen.getByRole("form", { name: "批量生成控制" })).not.toHaveClass("chapter-action-form");
});

function bookPayload() {
  return {
    book: {
      id: 42,
      title: "星港遗梦",
      genre: "科幻",
      audience: "成人",
      status: "canon_locked",
      premise: "领航员追查失落星港的真相。",
    },
    wordTargets: {
      targetWordCount: 120000,
      chapterWordCount: 2800,
    },
    chapters: [
      {
        id: 8,
        bookId: 42,
        number: 1,
        title: "失落灯塔",
        status: "planned",
        summary: "领航员发现星港残影。",
        wordCount: 1200,
        reviewerNote: null,
        updatedAt: "2026-05-16T00:00:00+00:00",
      },
    ],
    latestCanon: {
      id: 3,
      bookId: 42,
      version: 2,
      content: {
        world_rules: [{ rule: "灯塔会记录航线" }],
        characters: [{ name: "岑星" }],
        chapter_summaries: [],
      },
      createdAt: "2026-05-16T00:00:00+00:00",
    },
    runTraces: [],
    volumePlans: [],
  };
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
