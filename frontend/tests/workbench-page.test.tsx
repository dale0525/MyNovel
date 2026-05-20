import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
          {
            id: 8,
            title: "雾谷旧约",
            genre: "悬疑",
            audience: "成人",
            status: "producing",
            premise: "档案员追查被删掉的山城协议。",
          },
        ],
        blueprints: [],
      }),
    ),
  );

  render(<WorkbenchPage />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByText("科幻 · 成人 · 草稿")).toBeInTheDocument();
  expect(screen.getByText("一名领航员追查失落星港的真相。")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "继续推进" })).toHaveAttribute("href", "/books/7");
  expect(screen.getByRole("link", { name: "打开最近作品" })).toHaveAttribute("href", "/books/7");
  expect(screen.getByRole("heading", { name: "雾谷旧约" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "继续《星港遗梦》" })).toHaveAttribute("href", "/books/7");
  expect(screen.getByRole("link", { name: "继续《雾谷旧约》" })).toHaveAttribute("href", "/books/8");
});

test("open book blueprints render as resumable workbench items", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        books: [],
        blueprints: [
          {
            id: 9,
            parentId: null,
            version: 2,
            status: "succeeded",
            title: "长夜档案",
            idea: "一句灵感：失意档案员重建禁书图书馆",
            instruction: "主角更主动",
            createdAt: "2026-05-16T00:00:00+00:00",
          },
        ],
      }),
    ),
  );

  render(<WorkbenchPage />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "继续开书" })).toBeInTheDocument());
  expect(screen.getByText("长夜档案")).toBeInTheDocument();
  expect(screen.getByText("蓝图已生成 · 第 2 版")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "继续开书《长夜档案》" })).toHaveAttribute(
    "href",
    "/blueprints/9",
  );
});

test("open book blueprints can be deleted from the workbench", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path === "/api/books") {
      return Response.json({
        books: [],
        blueprints: [
          {
            id: 9,
            parentId: null,
            version: 1,
            status: "running",
            title: "长夜档案",
            idea: "一句灵感：失意档案员重建禁书图书馆",
            instruction: null,
            createdAt: "2026-05-16T00:00:00+00:00",
          },
        ],
      });
    }
    if (path === "/api/blueprints/9/delete" && init?.method === "POST") {
      return Response.json({ redirectTo: "/" });
    }
    return Response.json({}, { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("confirm", vi.fn(() => true));

  render(<WorkbenchPage />);

  await screen.findByRole("heading", { name: "长夜档案" });
  fireEvent.click(screen.getByRole("button", { name: "删除开书蓝图《长夜档案》" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/blueprints/9/delete",
      expect.objectContaining({
        body: JSON.stringify({}),
        method: "POST",
      }),
    ),
  );
  await waitFor(() => expect(screen.queryByRole("heading", { name: "长夜档案" })).not.toBeInTheDocument());
});
