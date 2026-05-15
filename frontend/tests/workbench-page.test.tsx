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
