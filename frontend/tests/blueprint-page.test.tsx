import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { BlueprintPage } from "@/features/open-book/BlueprintPage";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  window.history.pushState(null, "", "/");
});

test("renders running blueprint state and polls while in progress", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json({ blueprint: blueprintPayload({ status: "running" }) }))
    .mockResolvedValueOnce(
      Response.json({
        blueprint: blueprintPayload({
          status: "succeeded",
          content: { title_options: ["长夜档案"] },
        }),
      }),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<BlueprintPage blueprintId={3} />);

  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("蓝图生成中"));
  await waitFor(() => expect(screen.getByText("长夜档案")).toBeInTheDocument(), {
    timeout: 3000,
  });
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

test("renders failed blueprint details and retries", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        blueprint: blueprintPayload({
          status: "failed",
          parseError: "invalid json",
          errorMessage: "模型没有返回 JSON",
        }),
      }),
    )
    .mockResolvedValueOnce(Response.json({ blueprintId: 3, redirectTo: "/blueprints/3" }, { status: 202 }));
  vi.stubGlobal("fetch", fetchMock);

  render(<BlueprintPage blueprintId={3} />);

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("模型没有返回 JSON"));
  expect(screen.getByText("invalid json")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "重试生成" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/blueprints/3/retry", expect.anything()));
});

test("renders succeeded blueprint title selection and accept action", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        blueprint: blueprintPayload({
          status: "succeeded",
          content: {
            title_options: ["长夜档案", "禁书回声"],
            premise: "档案员追查禁书真相。",
          },
        }),
      }),
    )
    .mockResolvedValueOnce(Response.json({ bookId: 12, redirectTo: "/books/12" }));
  vi.stubGlobal("fetch", fetchMock);

  render(<BlueprintPage blueprintId={3} />);

  await waitFor(() => expect(screen.getByLabelText("长夜档案")).toBeChecked());
  expect(screen.getByText("档案员追查禁书真相。")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "接受并进入项目页" }));

  await waitFor(() => expect(window.location.pathname).toBe("/books/12"));
});

test("accept action is disabled while request is pending", async () => {
  let resolveAccept: (response: Response) => void = () => {};
  const acceptResponse = new Promise<Response>((resolve) => {
    resolveAccept = resolve;
  });
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        blueprint: blueprintPayload({
          status: "succeeded",
          content: { title_options: ["长夜档案"] },
        }),
      }),
    )
    .mockReturnValue(acceptResponse);
  vi.stubGlobal("fetch", fetchMock);

  render(<BlueprintPage blueprintId={3} />);

  const acceptButton = await screen.findByRole("button", { name: "接受并进入项目页" });
  fireEvent.click(acceptButton);
  fireEvent.click(acceptButton);

  await waitFor(() => expect(acceptButton).toBeDisabled());
  expect(fetchMock.mock.calls.filter(([path]) => path === "/api/blueprints/3/accept")).toHaveLength(1);

  resolveAccept(Response.json({ bookId: 12, redirectTo: "/books/12" }));
  await waitFor(() => expect(window.location.pathname).toBe("/books/12"));
});

test("blueprint id changes reset title selection revision notes and action error", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path === "/api/blueprints/3") {
      return Response.json({
        blueprint: blueprintPayload({
          id: 3,
          status: "succeeded",
          content: {
            title_options: ["长夜档案", "禁书回声"],
            premise: "第一版。",
          },
        }),
      });
    }
    if (path === "/api/blueprints/4") {
      return Response.json({
        blueprint: blueprintPayload({
          id: 4,
          status: "succeeded",
          content: {
            title_options: ["新蓝图"],
            premise: "第二版。",
          },
        }),
      });
    }
    if (path === "/api/blueprints/3/revise") {
      return Response.json(
        { error: { code: "revision_required", message: "请填写修订方向。", details: {} } },
        { status: 400 },
      );
    }
    return Response.json({}, { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);

  const { rerender } = render(<BlueprintPage blueprintId={3} />);

  await waitFor(() => expect(screen.getByLabelText("长夜档案")).toBeChecked());
  fireEvent.click(screen.getByLabelText("禁书回声"));
  fireEvent.change(screen.getByLabelText("修订意见"), {
    target: { value: "旧修订意见" },
  });
  fireEvent.click(screen.getByRole("button", { name: "提交修订" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("请填写修订方向。"));

  rerender(<BlueprintPage blueprintId={4} />);

  await waitFor(() => expect(screen.getByLabelText("新蓝图")).toBeChecked());
  expect(screen.getByLabelText("修订意见")).toHaveValue("");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

function blueprintPayload(overrides: Record<string, unknown> = {}) {
  return {
    id: 3,
    parentId: null,
    idea: "一座图书馆",
    version: 1,
    status: "pending",
    instruction: null,
    content: {},
    parseError: null,
    errorMessage: null,
    ...overrides,
  };
}
