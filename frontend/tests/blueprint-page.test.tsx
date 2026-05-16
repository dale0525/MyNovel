import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { BlueprintPage } from "@/features/open-book/BlueprintPage";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  window.history.pushState(null, "", "/");
});

test("renders running blueprint state and polls while in progress", async () => {
  vi.useFakeTimers();
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

  await act(async () => {
    await Promise.resolve();
  });
  expect(screen.getByRole("status")).toHaveClass("ai-waiting--hero");
  expect(screen.getByRole("status")).toHaveTextContent("蓝图生成中");
  expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("蓝图生成中");
  await act(async () => {
    vi.advanceTimersByTime(1500);
    await Promise.resolve();
  });
  expect(screen.getByRole("tab", { name: /长夜档案/ })).toHaveAttribute("aria-selected", "true");
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

test("aborts in-flight blueprint fetch on unmount", () => {
  let signal: AbortSignal | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      signal = init?.signal ?? undefined;
      return new Promise<Response>(() => {});
    }),
  );

  const { unmount } = render(<BlueprintPage blueprintId={3} />);

  expect(signal?.aborted).toBe(false);
  unmount();
  expect(signal?.aborted).toBe(true);
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

test("renders succeeded blueprint candidate workspace and accept action", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        blueprint: blueprintPayload({
          status: "succeeded",
          content: {
            title_options: ["长夜档案", "禁书回声"],
            genre: "都市奇幻",
            audience: "喜欢图书馆悬疑的读者",
            selling_points: ["禁书谜团", "记忆代价"],
            reader_promises: ["每章都有新线索"],
            protagonist: "林既明",
            world: "所有禁书都会留下回声",
            central_conflict: "核心冲突：档案员必须在禁书失控前找出幕后人。",
            chapter_directions: ["禁书初现", "追查失踪读者"],
            candidates: [
              {
                title: "长夜档案",
                genre: "都市奇幻",
                audience: "喜欢图书馆悬疑的读者",
                selling_points: ["禁书谜团", "记忆代价"],
                reader_promises: ["每章都有新线索"],
                protagonist: "林既明",
                world: "所有禁书都会留下回声",
                central_conflict: "核心冲突：档案员必须在禁书失控前找出幕后人。",
                chapter_directions: ["禁书初现", "追查失踪读者"],
              },
              {
                title: "禁书回声",
                genre: "回声悬疑",
                audience: "喜欢修复师成长线的读者",
                selling_points: ["回声追凶线", "旧案反转"],
                reader_promises: ["旧案反转会由回声线索推动"],
                protagonist: "沈回声",
                world: "回声会复写读过禁书的人生",
                central_conflict: "修复师冲突：沈回声必须修复禁书留下的时间裂缝。",
                chapter_directions: ["进入无声室", "第三章发现旧案"],
              },
            ],
          },
        }),
      }),
    )
    .mockResolvedValueOnce(Response.json({ bookId: 12, redirectTo: "/books/12" }));
  vi.stubGlobal("fetch", fetchMock);

  render(<BlueprintPage blueprintId={3} />);

  const defaultTab = await screen.findByRole("tab", { name: /长夜档案/ });
  expect(defaultTab).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tab", { name: /禁书回声/ })).toBeInTheDocument();

  const comparison = within(screen.getByRole("table", { name: "候选方向对比" }));
  expect(comparison.getByText("题材")).toBeInTheDocument();
  expect(comparison.getByText("目标读者")).toBeInTheDocument();
  expect(comparison.getByText("核心冲突")).toBeInTheDocument();
  expect(comparison.getByText("主角定位")).toBeInTheDocument();
  expect(comparison.getByText("前三章钩子")).toBeInTheDocument();
  expect(comparison.getByText("主要卖点")).toBeInTheDocument();
  expect(comparison.getByText("都市奇幻")).toBeInTheDocument();
  expect(comparison.getByText(/喜欢图书馆悬疑/)).toBeInTheDocument();
  expect(comparison.getByText(/林既明/)).toBeInTheDocument();

  expectVisibleText(/核心冲突/);
  expectVisibleText("林既明");
  expectVisibleText("禁书初现");

  fireEvent.click(screen.getByRole("tab", { name: /禁书回声/ }));
  expectVisibleText(/修复师冲突/);
  expectVisibleText("沈回声");
  expectVisibleText("回声追凶线");
  expectVisibleText("进入无声室");
  expectVisibleText("第三章发现旧案");
  expect(screen.getByText("当前选择")).toBeInTheDocument();
  expect(screen.getByText("接受前预览")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "选定这个方向，进入项目页" }));

  await waitFor(() => expect(window.location.pathname).toBe("/books/12"));
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/blueprints/3/accept",
    expect.objectContaining({
      body: JSON.stringify({ selectedTitle: "禁书回声" }),
    }),
  );
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

  const acceptButton = await screen.findByRole("button", { name: "选定这个方向，进入项目页" });
  fireEvent.click(acceptButton);
  fireEvent.click(acceptButton);

  await waitFor(() => expect(acceptButton).toBeDisabled());
  expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("进入项目中...");
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

  await screen.findByRole("tab", { name: /长夜档案/ });
  fireEvent.click(screen.getByRole("tab", { name: /禁书回声/ }));
  fireEvent.change(screen.getByLabelText("想让这一批怎么改"), {
    target: { value: "旧修订意见" },
  });
  fireEvent.click(screen.getByRole("button", { name: "按意见重生成一版" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("请填写修订方向。"));

  rerender(<BlueprintPage blueprintId={4} />);

  await waitFor(() => expect(screen.getByRole("tab", { name: /新蓝图/ })).toHaveAttribute("aria-selected", "true"));
  expect(screen.getByLabelText("想让这一批怎么改")).toHaveValue("");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("revision action sends selected candidate context", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        blueprint: blueprintPayload({
          status: "succeeded",
          content: {
            title_options: ["长夜档案", "禁书回声"],
            candidates: [
              {
                title: "长夜档案",
                protagonist: "林既明",
                central_conflict: "档案员追查禁书真相。",
                chapter_directions: ["禁书初现"],
              },
              {
                title: "禁书回声",
                protagonist: "沈回声",
                central_conflict: "修复师冲突。",
                chapter_directions: ["回声"],
              },
            ],
          },
        }),
      }),
    )
    .mockResolvedValueOnce(Response.json({ blueprintId: 4, redirectTo: "/blueprints/4" }, { status: 202 }));
  vi.stubGlobal("fetch", fetchMock);

  render(<BlueprintPage blueprintId={3} />);

  fireEvent.click(await screen.findByRole("tab", { name: /禁书回声/ }));
  fireEvent.change(screen.getByLabelText("想让这一批怎么改"), {
    target: { value: "保留回声设定，但前三章冲突更强" },
  });
  fireEvent.click(screen.getByRole("button", { name: "按意见重生成一版" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/blueprints/3/revise",
      expect.objectContaining({
        body: JSON.stringify({
          revisionNotes: "保留回声设定，但前三章冲突更强",
          selectedTitle: "禁书回声",
          selectedCandidateIndex: 1,
        }),
      }),
    ),
  );
});

test("renders old global-only blueprint fields as one candidate", async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce(
    Response.json({
      blueprint: blueprintPayload({
        status: "succeeded",
        content: {
          title_options: ["长夜档案"],
          genre: "都市奇幻",
          audience: "喜欢图书馆悬疑的读者",
          selling_points: ["前三章钩子"],
          reader_promises: ["每章都有新线索"],
          protagonist: "林既明",
          world: "所有禁书都会留下回声",
          central_conflict: "核心冲突：档案员必须在禁书失控前找出幕后人。",
          chapter_directions: ["禁书初现"],
        },
      }),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<BlueprintPage blueprintId={3} />);

  const tab = await screen.findByRole("tab", { name: /长夜档案/ });
  expect(tab).toHaveAttribute("aria-selected", "true");
  expectVisibleText("都市奇幻");
  expectVisibleText("喜欢图书馆悬疑的读者");
  expectVisibleText("前三章钩子");
  expectVisibleText("每章都有新线索");
  expectVisibleText("林既明");
  expectVisibleText("所有禁书都会留下回声");
  expectVisibleText(/核心冲突/);
  expectVisibleText("禁书初现");
});

test("renders structured entity extras and raw content disclosure", async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce(
    Response.json({
      blueprint: blueprintPayload({
        status: "succeeded",
        content: {
          title_options: ["长夜档案"],
          protagonist: {
            name: "林既明",
            identity: "禁书档案员",
            hidden_cost: "每次借书都会忘记一人",
          },
          world: {
            summary: "禁书会吞噬记忆",
            taboo: "不能翻到第七页",
          },
        },
      }),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<BlueprintPage blueprintId={3} />);

  expect(await screen.findByRole("tab", { name: /长夜档案/ })).toHaveAttribute("aria-selected", "true");
  expectVisibleText("林既明");
  expectVisibleText("禁书档案员");
  expectVisibleText("每次借书都会忘记一人");
  expectVisibleText("不能翻到第七页");
  fireEvent.click(screen.getByText("模型原始信息"));
  expectVisibleText("模型返回");
  expectVisibleText(/title_options/);
});

test("renders raw content disclosure when blueprint has no selectable candidate", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValueOnce(
      Response.json({
        blueprint: blueprintPayload({
          status: "succeeded",
          content: {},
        }),
      }),
    ),
  );

  render(<BlueprintPage blueprintId={3} />);

  expect(await screen.findByRole("alert")).toHaveTextContent("当前蓝图没有可用候选方向");
  fireEvent.click(screen.getByText("模型原始信息"));
  expectVisibleText("模型返回");
  expectVisibleText("{}");
});

function expectVisibleText(text: string | RegExp) {
  expect(screen.getAllByText(text).length).toBeGreaterThan(0);
}

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
