import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { WorkbenchPage } from "@/features/workbench/WorkbenchPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test.each([{}, { books: null }, { books: { id: 1 } }])(
  "malformed books payload renders an error state instead of crashing",
  async (payload) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json(payload)),
    );

    render(<WorkbenchPage />);

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByRole("alert")).toHaveTextContent("作品列表加载失败");
  },
);

test("malformed book fields render an error state instead of partial content", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({ books: [{ id: 1, title: "Broken" }] })),
  );

  render(<WorkbenchPage />);

  await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  expect(screen.getByRole("alert")).toHaveTextContent("作品列表加载失败");
});

test("recent books render title status premise and project CTAs", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        books: [
          {
            id: 7,
            title: "星港遗梦",
            genre: "科幻",
            audience: "成人",
            status: "draft",
            premise: "一名领航员追查失落星港的真相。",
          },
        ],
      }),
    ),
  );

  render(<WorkbenchPage />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByText("科幻 · 成人 · 草稿")).toBeInTheDocument();
  expect(screen.getByText("一名领航员追查失落星港的真相。")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "继续推进" })).toHaveAttribute("href", "/books/7");
  expect(screen.getByRole("link", { name: "打开最近作品" })).toHaveAttribute("href", "/books/7");
});
