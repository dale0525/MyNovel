import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { routeForPath } from "@/app/AppRoutes";
import { ChapterPage } from "@/features/chapters/ChapterPage";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("routes chapter path to chapter review page", () => {
  const match = routeForPath("/chapters/12");

  expect(match.activePath).toBe("/chapters/:id");
  expect(match.element).toEqual(<ChapterPage chapterId={12} />);
});

test("renders result report before chapter text and empty review states", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ emptyReview: true }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const report = screen.getByRole("heading", { name: "结果报告" });
  const text = screen.getByRole("heading", { name: "章节正文" });
  expect(report.compareDocumentPosition(text) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(screen.getByText("还没有状态变化。")).toBeInTheDocument();
  expect(screen.getByText("还没有审计报告。")).toBeInTheDocument();
});

test("polls chapter every three seconds while it is running", async () => {
  const realSetTimeout = globalThis.setTimeout;
  const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout").mockImplementation(
    (handler: TimerHandler, timeout?: number, ...args: unknown[]) => {
      if (timeout === 3000 && typeof handler === "function") {
        queueMicrotask(handler);
        return 1 as unknown as ReturnType<typeof setTimeout>;
      }
      return realSetTimeout(handler, timeout, ...args);
    },
  );
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload({ status: "running" })))
    .mockResolvedValueOnce(Response.json(chapterPayload({ status: "awaiting_review" })));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 3000);
  expect(fetchMock).toHaveBeenLastCalledWith("/api/chapters/12", expect.objectContaining({ signal: expect.any(AbortSignal) }));
});

test("renders animated AI waiting state while chapter is running", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ status: "running" }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("章节生成中");
});

test("chapter review actions call edit repair approve and export endpoints", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload()))
    .mockResolvedValueOnce(Response.json(chapterPayload({ revisedText: "人工修正文。" })))
    .mockResolvedValueOnce(Response.json(chapterPayload({ status: "running" }), { status: 202 }))
    .mockResolvedValueOnce(Response.json(chapterPayload({ status: "accepted" })));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("手动修正文"), { target: { value: "人工修正文。" } });
  fireEvent.click(screen.getByRole("button", { name: "保存手动修正" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chapters/12/edit",
      expect.objectContaining({ method: "POST" }),
    ),
  );

  fireEvent.change(screen.getByLabelText("修复要求"), { target: { value: "补强结尾。" } });
  fireEvent.click(screen.getByRole("button", { name: "让 AI 修复" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chapters/12/repair",
      expect.objectContaining({ method: "POST" }),
    ),
  );

  fireEvent.click(screen.getByRole("button", { name: "批准章节" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chapters/12/approve",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(screen.getByRole("link", { name: "导出正文" })).toHaveAttribute("href", "/api/chapters/12/export.txt");
});

test("renders animated AI waiting state while repair request is pending", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload()))
    .mockImplementationOnce(
      () =>
        new Promise<Response>(() => {
          // Keep the repair request pending so the waiting state stays visible.
        }),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("修复要求"), { target: { value: "补强结尾。" } });
  fireEvent.click(screen.getByRole("button", { name: "让 AI 修复" }));

  await waitFor(() => expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("提交修复中..."));
  expect(screen.getByRole("button", { name: /提交修复中/ })).toBeDisabled();
});

test("rejects action responses without chapter payload", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload()))
    .mockResolvedValueOnce(Response.json({ chapterId: 12, redirectTo: "/chapters/12" }, { status: 202 }));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("修复要求"), { target: { value: "补强结尾。" } });
  fireEvent.click(screen.getByRole("button", { name: "让 AI 修复" }));

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("章节数据格式无效。"));
  expect(screen.queryByText("任务已提交，页面会自动刷新。")).not.toBeInTheDocument();
});

test("run action enters running state from the action response", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload({ status: "planned" })))
    .mockResolvedValueOnce(Response.json(chapterPayload({ status: "running" })));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "运行本章" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "运行本章" }));

  await waitFor(() => expect(screen.getByText("星港遗梦 · 第 2 章 · 运行中")).toBeInTheDocument());
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/chapters/12/run",
    expect.objectContaining({ method: "POST" }),
  );
});

function chapterPayload({
  status = "awaiting_review",
  emptyReview = false,
  revisedText = "岑星抵达静默港湾。",
}: {
  status?: string;
  emptyReview?: boolean;
  revisedText?: string;
} = {}) {
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
      id: 12,
      bookId: 42,
      number: 2,
      title: "静默港湾",
      status,
      summary: "岑星抵达港湾。",
      wordCount: 10,
      reviewerNote: null,
      updatedAt: "2026-05-16T00:00:00+00:00",
      plan: { goal: "进入港湾" },
      contextPackage: { trusted_state: { version: 2 } },
      draftText: "岑星抵达港湾。",
      revisedText,
      finalText: status === "accepted" ? revisedText : "",
      auditReport: emptyReview ? {} : { risk_level: "low", issues: [] },
      stateDelta: emptyReview ? {} : { chapter: 2, changes: [{ target: "港湾", change: "首次出现" }] },
    },
    siblingChapters: [],
    latestCanon: null,
    traces: [],
    stageSlots: [
      { key: "plan", label: "规划", ready: true, status: "ready", summary: "进入港湾" },
      { key: "context", label: "上下文", ready: true, status: "ready", summary: "可信设定 v2" },
      { key: "draft", label: "草稿", ready: true, status: "ready", summary: "7 字" },
      { key: "delta", label: "状态变化", ready: !emptyReview, status: emptyReview ? "empty" : "ready", summary: "" },
      { key: "audit", label: "审计", ready: !emptyReview, status: emptyReview ? "empty" : "ready", summary: "" },
    ],
  };
}
