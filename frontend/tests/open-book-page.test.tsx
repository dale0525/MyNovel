import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { OpenBookPage } from "@/features/open-book/OpenBookPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.pushState(null, "", "/");
});

test("submits open book idea as JSON and follows API redirect", async () => {
  let streamController: ReadableStreamDefaultController<Uint8Array> | null = null;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      streamController = controller;
    },
  });
  const fetchMock = vi.fn(async () => new Response(stream));
  vi.stubGlobal("fetch", fetchMock);
  window.history.pushState(null, "", "/books/new");

  render(<OpenBookPage />);

  fireEvent.change(screen.getByLabelText("故事灵感"), {
    target: { value: "失意档案员重建禁书图书馆" },
  });
  fireEvent.change(screen.getByLabelText("题材"), { target: { value: "奇幻" } });
  fireEvent.click(screen.getByRole("button", { name: "生成蓝图" }));

  await waitFor(() => expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("生成中..."));
  pushStreamEvent(streamController, { type: "chunk", text: "正在拆解卖点和开篇结构" });
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("正在拆解卖点和开篇结构"));
  pushStreamEvent(streamController, { type: "done", blueprintId: 9, redirectTo: "/blueprints/9" });
  streamController?.close();

  await waitFor(() => expect(window.location.pathname).toBe("/blueprints/9"));
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/open-book/stream",
    expect.objectContaining({
      method: "POST",
      body: expect.stringContaining("失意档案员重建禁书图书馆"),
    }),
  );
});

test("renders animated AI waiting state while open-book submit is pending", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise<Response>(() => {
          // Keep the request pending so the waiting state stays visible.
        }),
    ),
  );

  render(<OpenBookPage />);

  fireEvent.change(screen.getByLabelText("故事灵感"), {
    target: { value: "失意档案员重建禁书图书馆" },
  });
  fireEvent.click(screen.getByRole("button", { name: "生成蓝图" }));

  await waitFor(() => expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("生成中..."));
  expect(screen.getByRole("button", { name: /生成中/ })).toBeDisabled();
});

test("optional open book fields support blank values, presets, and custom text", () => {
  render(<OpenBookPage />);

  expect(screen.getByLabelText("故事灵感")).toBeRequired();
  expect(screen.getByLabelText("题材")).not.toBeRequired();
  expect(screen.getByLabelText("目标读者")).not.toBeRequired();
  expect(screen.getByLabelText("爽点偏好")).not.toBeRequired();
  expect(screen.getByLabelText("写作禁区")).not.toBeRequired();

  fireEvent.click(screen.getByRole("button", { name: "玄幻升级" }));
  expect(screen.getByLabelText("题材")).toHaveValue("玄幻升级");

  fireEvent.change(screen.getByLabelText("题材"), { target: { value: "自定义题材" } });
  expect(screen.getByLabelText("题材")).toHaveValue("自定义题材");

  fireEvent.click(screen.getByRole("button", { name: "男频网文读者" }));
  expect(screen.getByLabelText("目标读者")).toHaveValue("男频网文读者");

  fireEvent.change(screen.getByLabelText("目标读者"), { target: { value: "私人读者" } });
  expect(screen.getByLabelText("目标读者")).toHaveValue("私人读者");

  fireEvent.click(screen.getByRole("button", { name: "逆袭反转" }));
  fireEvent.click(screen.getByRole("button", { name: "智商碾压" }));
  expect(screen.getByLabelText("爽点偏好")).toHaveValue("逆袭反转、智商碾压");

  fireEvent.change(screen.getByLabelText("爽点偏好"), { target: { value: "慢热群像" } });
  expect(screen.getByLabelText("爽点偏好")).toHaveValue("慢热群像");

  fireEvent.click(screen.getByRole("button", { name: "不写虐主" }));
  fireEvent.click(screen.getByRole("button", { name: "不写后宫" }));
  expect(screen.getByLabelText("写作禁区")).toHaveValue("不写虐主、不写后宫");

  fireEvent.change(screen.getByLabelText("写作禁区"), { target: { value: "自定义禁区" } });
  expect(screen.getByLabelText("写作禁区")).toHaveValue("自定义禁区");
});

test("renders API error message when open book submit fails", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => streamResponse([{ type: "failed", message: "请先写下故事灵感。" }])),
  );

  render(<OpenBookPage />);

  fireEvent.change(screen.getByLabelText("故事灵感"), { target: { value: " " } });
  fireEvent.click(screen.getByRole("button", { name: "生成蓝图" }));

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("请先写下故事灵感。"));
});

function pushStreamEvent(
  controller: ReadableStreamDefaultController<Uint8Array> | null,
  event: Record<string, unknown>,
) {
  if (!controller) {
    throw new Error("Stream controller was not initialized.");
  }
  controller.enqueue(new TextEncoder().encode(`${JSON.stringify(event)}\n`));
}

function streamResponse(events: Array<Record<string, unknown>>): Response {
  return new Response(events.map((event) => JSON.stringify(event)).join("\n"));
}
