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

test("renders the simplified chapter operation structure without extra sections", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ emptyReview: true }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const operation = screen.getByRole("heading", { name: "章节操作" });
  const text = screen.getByRole("heading", { name: "章节正文" });
  const revision = screen.getByRole("heading", { name: "修正意见" });
  const stateChanges = screen.getByRole("heading", { name: "设定变动" });
  expect(operation.compareDocumentPosition(text) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(text.compareDocumentPosition(revision) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(revision.compareDocumentPosition(stateChanges) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(screen.getByText("暂无修正意见。")).toBeInTheDocument();
  expect(screen.getByText("暂无设定变动。")).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "生产阶段" })).not.toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "章节结果" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "相邻章节" })).not.toBeInTheDocument();
});

test("chapter review shows trusted-state impact before approval", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload())));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  expect(screen.getByRole("region", { name: "将写入可信设定" })).toHaveTextContent("港湾");
  expect(screen.getByRole("button", { name: "批准并写入可信设定" })).toBeInTheDocument();
  expect(screen.queryByLabelText("手动修正文")).not.toBeInTheDocument();
});

test("chapter page orders operation, text, revision notes, and state changes", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(
        chapterPayload({
          auditIssues: [{ title: "结尾动力不足", severity: "medium", resolved: false }],
        }),
      ),
    ),
  );

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const operation = screen.getByRole("heading", { name: "章节操作" });
  const text = screen.getByRole("heading", { name: "章节正文" });
  const revision = screen.getByRole("heading", { name: "修正意见" });
  const stateChanges = screen.getByRole("heading", { name: "设定变动" });

  expect(operation.compareDocumentPosition(text) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(text.compareDocumentPosition(revision) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(revision.compareDocumentPosition(stateChanges) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(screen.getByText("结尾动力不足 · medium · 未解决")).toBeInTheDocument();
  expect(screen.getByText("港湾：首次出现")).toBeInTheDocument();
});

test("chapter review prioritizes AI revision when audit risk is high", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ riskLevel: "high" }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  expect(screen.getByRole("button", { name: "让 AI 修订" })).toHaveClass("workbench-action-button");
  expect(screen.queryByRole("button", { name: "批准并写入可信设定" })).not.toBeInTheDocument();
});

test("chapter review treats high risk values case-insensitively", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ riskLevel: "HIGH" }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  expect(screen.getByRole("button", { name: "让 AI 修订" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "批准并写入可信设定" })).not.toBeInTheDocument();
});

test("chapter review treats high severity issues case-insensitively", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(
        chapterPayload({
          auditIssues: [{ title: "设定冲突", severity: "High", resolved: false }],
        }),
      ),
    ),
  );

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  expect(screen.getByRole("button", { name: "让 AI 修订" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "批准并写入可信设定" })).not.toBeInTheDocument();
});

test("chapter review shows audit issues and all state changes without hiding them", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(
        chapterPayload({
          auditIssues: [{ title: "时间线冲突", severity: "medium", resolved: false }],
          stateDelta: {
            chapter: 2,
            changes: [
              { target: "港湾", change: "首次出现" },
              { target: "灯塔记录", change: "推进伏笔" },
              { target: "岑星", change: "更加警觉" },
              { target: "罗文", change: "提出警告" },
              { target: "旧航道协会", change: "留下新线索" },
            ],
          },
        }),
      ),
    ),
  );

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "审核明细" })).not.toBeInTheDocument();
  expect(screen.getByText("时间线冲突 · medium · 未解决")).toBeInTheDocument();
  expect(screen.getByText("旧航道协会：留下新线索")).toBeInTheDocument();
});

test("major state changes require confirmation before approval", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ majorChange: true }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const approveButton = screen.getByRole("button", { name: "批准并写入可信设定" });
  expect(approveButton).toBeDisabled();

  fireEvent.click(screen.getByLabelText("确认写入重大变化"));

  expect(approveButton).toBeEnabled();
});

test.each([
  ["impact major", { impact: "major" }],
  ["impact high", { impact: "high" }],
  ["death change text", { change: "角色死亡" }],
])("major state changes require confirmation for %s", async (_caseName, changePatch) => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(
        chapterPayload({
          stateDelta: {
            chapter: 2,
            changes: [{ target: "岑星", change: "命运改写", ...changePatch }],
          },
        }),
      ),
    ),
  );

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const approveButton = screen.getByRole("button", { name: "批准并写入可信设定" });
  expect(screen.getByLabelText("确认写入重大变化")).toBeInTheDocument();
  expect(approveButton).toBeDisabled();
});

test("major state changes include death terms in change type", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(
        chapterPayload({
          stateDelta: {
            chapter: 2,
            changes: [{ type: "角色死亡", target: "罗文", change: "保护主角" }],
          },
        }),
      ),
    ),
  );

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const approveButton = screen.getByRole("button", { name: "批准并写入可信设定" });
  expect(screen.getByLabelText("确认写入重大变化")).toBeInTheDocument();
  expect(approveButton).toBeDisabled();

  fireEvent.click(screen.getByLabelText("确认写入重大变化"));

  expect(approveButton).toBeEnabled();
});

test("major change confirmation resets when chapter content changes", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json(
        chapterPayload({
          majorChange: true,
          updatedAt: "2026-05-16T00:00:00+00:00",
        }),
      ),
    )
    .mockResolvedValueOnce(
      Response.json(
        chapterPayload({
          majorChange: true,
          updatedAt: "2026-05-16T00:05:00+00:00",
        }),
      ),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const approveButton = screen.getByRole("button", { name: "批准并写入可信设定" });
  fireEvent.click(screen.getByLabelText("确认写入重大变化"));
  expect(approveButton).toBeEnabled();

  fireEvent.click(screen.getByRole("button", { name: "退回修订" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/chapters/12/request-revision", expect.any(Object)));
  await waitFor(() => expect(screen.getByRole("button", { name: "批准并写入可信设定" })).toBeDisabled());
});

test("running chapters hide approval decisions", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ status: "running" }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("章节生成中");
  expect(screen.queryByRole("button", { name: "批准并写入可信设定" })).not.toBeInTheDocument();
});

test("running chapters hide advanced edit and repair tools", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ status: "running", riskLevel: "high" }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "高级审核工具" }));

  expect(screen.queryByLabelText("手动修正文")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "让 AI 修订" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "批准并写入可信设定" })).not.toBeInTheDocument();
});

test("accepted chapters hide advanced edit and repair tools but keep export", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ status: "accepted" }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "高级审核工具" }));

  expect(screen.queryByLabelText("手动修正文")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "让 AI 修复" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "导出正文" })).toHaveAttribute("href", "/api/chapters/12/export.txt");
});

test("planned chapters only allow the run primary action", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ status: "planned" }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "运行本章" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "高级审核工具" }));

  expect(screen.queryByLabelText("手动修正文")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "让 AI 修复" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "批准并写入可信设定" })).not.toBeInTheDocument();
});

test("chapter review hides export link when chapter id is missing", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ chapterId: null }))));
  render(<ChapterPage chapterId={12} />);
  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "高级审核工具" }));
  expect(screen.queryByRole("link", { name: "导出正文" })).not.toBeInTheDocument();
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
    .mockResolvedValueOnce(streamResponse([{ type: "done", chapter: chapterPayload({ revisedText: "人工修正文。" }) }]))
    .mockResolvedValueOnce(Response.json(chapterPayload({ status: "accepted" })));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "高级审核工具" }));
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
      "/api/chapters/12/repair-stream",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(screen.getByRole("link", { name: "导出正文" })).toHaveAttribute("href", "/api/chapters/12/export.txt");

  fireEvent.click(screen.getByRole("button", { name: "批准并写入可信设定" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chapters/12/approve",
      expect.objectContaining({ method: "POST" }),
    ),
  );
});

test("renders animated AI waiting state while repair request is pending", async () => {
  let streamController: ReadableStreamDefaultController<Uint8Array> | null = null;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      streamController = controller;
    },
  });
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload({ riskLevel: "high" })))
    .mockResolvedValueOnce(new Response(stream));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("修订意图"), { target: { value: "补强结尾。" } });
  fireEvent.click(screen.getByRole("button", { name: "让 AI 修订" }));

  await waitFor(() => expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("提交修复中..."));
  pushStreamEvent(streamController, { type: "chunk", text: "正在补强结尾冲突" });
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("正在补强结尾冲突"));
  expect(screen.getByRole("button", { name: /提交修复中/ })).toBeDisabled();
});

test("high-risk AI revision requires a trimmed instruction", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload({ riskLevel: "high" })))
    .mockResolvedValueOnce(streamResponse([{ type: "done", chapter: chapterPayload({ status: "running" }) }]));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const revisionButton = screen.getByRole("button", { name: "让 AI 修订" });
  expect(revisionButton).toBeDisabled();

  fireEvent.change(screen.getByLabelText("修订意图"), { target: { value: "   " } });
  expect(revisionButton).toBeDisabled();
  expect(fetchMock).toHaveBeenCalledTimes(1);

  fireEvent.change(screen.getByLabelText("修订意图"), { target: { value: "  补强结尾。  " } });
  expect(revisionButton).toBeEnabled();
  fireEvent.click(revisionButton);

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chapters/12/repair-stream",
      expect.objectContaining({
        body: JSON.stringify({ reviewerNote: "补强结尾。" }),
        method: "POST",
      }),
    ),
  );
});

test("needs revision with high risk can submit trimmed AI repair", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload({ status: "needs_revision", riskLevel: "high" })))
    .mockResolvedValueOnce(streamResponse([{ type: "done", chapter: chapterPayload({ status: "running" }) }]));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const revisionButton = screen.getByRole("button", { name: "让 AI 修订" });
  expect(screen.queryByRole("button", { name: "退回修订" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "批准并写入可信设定" })).not.toBeInTheDocument();
  expect(revisionButton).toBeDisabled();

  fireEvent.change(screen.getByLabelText("修订意图"), { target: { value: "   " } });
  expect(revisionButton).toBeDisabled();

  fireEvent.change(screen.getByLabelText("修订意图"), { target: { value: "  重写冲突段落。  " } });
  expect(revisionButton).toBeEnabled();
  fireEvent.click(revisionButton);

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chapters/12/repair-stream",
      expect.objectContaining({
        body: JSON.stringify({ reviewerNote: "重写冲突段落。" }),
        method: "POST",
      }),
    ),
  );
});

test("rejects action responses without chapter payload", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload()))
    .mockResolvedValueOnce(streamResponse([{ type: "done", chapterId: 12, redirectTo: "/chapters/12" }]));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "高级审核工具" }));
  fireEvent.change(screen.getByLabelText("修复要求"), { target: { value: "补强结尾。" } });
  fireEvent.click(screen.getByRole("button", { name: "让 AI 修复" }));

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("章节数据格式无效。"));
  expect(screen.queryByText("任务已提交，页面会自动刷新。")).not.toBeInTheDocument();
});

test("run action enters running state from the action response", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload({ status: "planned" })))
    .mockResolvedValueOnce(
      streamResponse([{ type: "chunk", text: "正在生成草稿" }, { type: "done", chapter: chapterPayload({ status: "running" }) }]),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "运行本章" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "运行本章" }));

  await waitFor(() => expect(screen.getByText("运行中")).toBeInTheDocument());
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/chapters/12/run-stream",
    expect.objectContaining({ method: "POST" }),
  );
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

function chapterPayload({
  status = "awaiting_review",
  emptyReview = false,
  riskLevel = "low",
  auditIssues,
  majorChange = false,
  chapterId = 12,
  stateDelta,
  updatedAt = "2026-05-16T00:00:00+00:00",
  revisedText = "岑星抵达静默港湾。",
}: {
  status?: string;
  emptyReview?: boolean;
  riskLevel?: string;
  auditIssues?: Array<Record<string, unknown>>;
  majorChange?: boolean;
  chapterId?: number | null;
  stateDelta?: Record<string, unknown>;
  updatedAt?: string;
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
      id: chapterId,
      bookId: 42,
      number: 2,
      title: "静默港湾",
      status,
      summary: "岑星抵达港湾。",
      wordCount: 10,
      reviewerNote: null,
      updatedAt,
      plan: { goal: "进入港湾" },
      contextPackage: { trusted_state: { version: 2 } },
      draftText: "岑星抵达港湾。",
      revisedText,
      finalText: status === "accepted" ? revisedText : "",
      auditReport: emptyReview ? {} : {
        risk_level: riskLevel,
        issues: auditIssues ?? (riskLevel === "high" ? [{ title: "设定冲突", severity: "high", resolved: false }] : []),
      },
      stateDelta: emptyReview ? {} : stateDelta ?? { chapter: 2, changes: [{ target: "港湾", change: "首次出现", major: majorChange }] },
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
