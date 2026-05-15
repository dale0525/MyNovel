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
  const fetchMock = vi.fn(async () =>
    Response.json({ blueprintId: 9, redirectTo: "/blueprints/9" }, { status: 202 }),
  );
  vi.stubGlobal("fetch", fetchMock);
  window.history.pushState(null, "", "/books/new");

  render(<OpenBookPage />);

  fireEvent.change(screen.getByLabelText("故事灵感"), {
    target: { value: "失意档案员重建禁书图书馆" },
  });
  fireEvent.change(screen.getByLabelText("题材"), { target: { value: "奇幻" } });
  fireEvent.click(screen.getByRole("button", { name: "生成蓝图" }));

  await waitFor(() => expect(window.location.pathname).toBe("/blueprints/9"));
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/open-book",
    expect.objectContaining({
      method: "POST",
      body: expect.stringContaining("失意档案员重建禁书图书馆"),
    }),
  );
});

test("renders API error message when open book submit fails", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(
        { error: { code: "idea_required", message: "请先写下故事灵感。", details: {} } },
        { status: 400 },
      ),
    ),
  );

  render(<OpenBookPage />);

  fireEvent.change(screen.getByLabelText("故事灵感"), { target: { value: " " } });
  fireEvent.click(screen.getByRole("button", { name: "生成蓝图" }));

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("请先写下故事灵感。"));
});
