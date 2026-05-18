import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { routeForPath } from "@/app/AppRoutes";
import { BookWorkspacePage } from "@/features/books/BookWorkspacePage";
import { ChapterPage } from "@/features/chapters/ChapterPage";

const APPROVE_NEXT_LABEL = "确定，下一章";
const REPAIR_LABEL = "一键让 AI 修正";

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

test("routes project chapter path as a third-level editor", () => {
  const match = routeForPath("/books/42/chapters/12");

  expect(match.activePath).toBe("/books/:id/chapters/:chapterId");
  expect(match.element).toEqual(<BookWorkspacePage bookId={42} chapterId={12} view="chapters" />);
});

test("renders the simplified chapter operation structure without extra sections", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ emptyReview: true }))));

  render(<ChapterPage bookId={42} chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  expect(screen.getByRole("link", { name: "返回章节" })).toHaveAttribute("href", "/books/42/chapters");
  const operationSection = screen.getByRole("region", { name: "章节操作" });
  const operation = within(operationSection).getByRole("heading", { name: "章节操作" });
  const text = screen.getByRole("heading", { name: "章节正文" });
  const revision = within(operationSection).getByRole("heading", { name: "修正意见" });
  expect(operation.compareDocumentPosition(text) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(revision.compareDocumentPosition(text) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(within(operationSection).getByText("暂无修正意见。")).toBeInTheDocument();
  expect(within(operationSection).queryByRole("region", { name: "重要变动" })).not.toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "将写入可信设定" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "设定变动" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "高级审核工具" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "生产阶段" })).not.toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "章节结果" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "相邻章节" })).not.toBeInTheDocument();
});

test("chapter review header keeps the summary with the title before project metadata", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload())));

  const { container } = render(<ChapterPage bookId={42} chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const header = container.querySelector(".guided-identity");
  expect(header).toBeInTheDocument();

  const headerScope = within(header as HTMLElement);
  const title = headerScope.getByRole("heading", { name: "静默港湾" });
  const summary = headerScope.getByText("岑星抵达港湾。");
  const projectMeta = headerScope.getByText("项目");

  expect(title.compareDocumentPosition(summary) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(summary.compareDocumentPosition(projectMeta) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

test("chapter review shows trusted-state impact before approval", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload())));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const operationSection = screen.getByRole("region", { name: "章节操作" });
  expect(within(operationSection).getByRole("region", { name: "重要变动" })).toHaveTextContent("港湾");
  expect(screen.queryByRole("region", { name: "将写入可信设定" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: APPROVE_NEXT_LABEL })).toBeInTheDocument();
  expect(screen.queryByLabelText("章节正文手动编辑")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("决策说明")).not.toBeInTheDocument();
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
  const operationSection = screen.getByRole("region", { name: "章节操作" });
  const operation = within(operationSection).getByRole("heading", { name: "章节操作" });
  const text = screen.getByRole("heading", { name: "章节正文" });
  const revision = within(operationSection).getByRole("heading", { name: "修正意见" });
  const stateChanges = within(operationSection).getByRole("heading", { name: "重要变动" });

  expect(operation.compareDocumentPosition(text) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(revision.compareDocumentPosition(text) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(stateChanges.compareDocumentPosition(text) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  const issueTag = within(operationSection).getByText("结尾动力不足");
  expect(issueTag).toHaveClass("chapter-issue-tag--unmet");
  expect(operationSection).not.toHaveTextContent("medium");
  expect(operationSection).not.toHaveTextContent("未解决");
  const stateChangeSection = within(operationSection).getByRole("region", { name: "重要变动" });
  expect(within(stateChangeSection).getByText("港湾")).toBeInTheDocument();
  expect(within(stateChangeSection).getByText("首次出现")).toBeInTheDocument();
});

test("chapter review prioritizes AI revision when audit risk is high", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ riskLevel: "high" }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  expect(screen.getByLabelText("人工意见")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: REPAIR_LABEL })).toHaveClass("workbench-action-button");
  expect(screen.queryByLabelText("修订意图")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: APPROVE_NEXT_LABEL })).not.toBeInTheDocument();
});

test("chapter review treats high risk values case-insensitively", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ riskLevel: "HIGH" }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  expect(screen.getByLabelText("人工意见")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "修复" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: APPROVE_NEXT_LABEL })).not.toBeInTheDocument();
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
  expect(screen.getByLabelText("人工意见")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: REPAIR_LABEL })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: APPROVE_NEXT_LABEL })).not.toBeInTheDocument();
});

test("chapter review shows audit issues and all state changes without hiding them", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(
        chapterPayload({
          auditIssues: [
            { title: "时间线冲突", severity: "medium", resolved: false },
            { title: "空间取物动作已补足掩饰", severity: "low", resolved: true },
          ],
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
  const operationSection = screen.getByRole("region", { name: "章节操作" });
  expect(within(operationSection).getByText("时间线冲突")).toHaveClass("chapter-issue-tag--unmet");
  expect(within(operationSection).getByText("空间取物动作已补足掩饰（已修正）")).toHaveClass("chapter-issue-tag--resolved");
  expect(operationSection).not.toHaveTextContent("medium");
  expect(operationSection).not.toHaveTextContent("low");
  expect(operationSection).not.toHaveTextContent("未解决");
  expect(operationSection).not.toHaveTextContent("已解决");
  const stateChangeSection = screen.getByRole("region", { name: "重要变动" });
  expect(within(stateChangeSection).getByText("旧航道协会")).toBeInTheDocument();
  expect(within(stateChangeSection).getByText("留下新线索")).toBeInTheDocument();
});

test("chapter review deduplicates resolved word-count issues with positive copy", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(
        chapterPayload({
          auditIssues: [
            { title: "字数不在目标区间", severity: "medium", resolved: true },
            { title: "反杀过程的体能逻辑支撑略显不足", severity: "medium", resolved: true },
            { title: "字数不在目标区间", severity: "low", resolved: true },
          ],
        }),
      ),
    ),
  );

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const operationSection = screen.getByRole("region", { name: "章节操作" });

  const wordCountTag = within(operationSection).getByText("字数已在目标区间（已修正）");
  expect(wordCountTag).toHaveClass("chapter-issue-tag--resolved");
  expect(within(operationSection).getAllByText("字数已在目标区间（已修正）")).toHaveLength(1);
  expect(operationSection).not.toHaveTextContent("字数不在目标区间");
  expect(operationSection).not.toHaveTextContent("medium");
  expect(operationSection).not.toHaveTextContent("low");
});

test("chapter review keeps an unmet duplicate issue red when any duplicate is unresolved", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(
        chapterPayload({
          auditIssues: [
            { title: "字数不在目标区间", severity: "medium", resolved: true },
            { title: "字数不在目标区间", severity: "high", resolved: false },
          ],
        }),
      ),
    ),
  );

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const operationSection = screen.getByRole("region", { name: "章节操作" });

  const wordCountTag = within(operationSection).getByText("字数不在目标区间");
  expect(wordCountTag).toHaveClass("chapter-issue-tag--unmet");
  expect(within(operationSection).getAllByText("字数不在目标区间")).toHaveLength(1);
  expect(operationSection).not.toHaveTextContent("high");
});

test("chapter state changes hide section-key-only labels and show a clear fallback", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(
        chapterPayload({
          stateDelta: {
            chapter: 2,
            changes: [
              { type: "状态变化", target: "待确认", change: "characters", risk: "low" },
              { type: "状态变化", target: "待确认", change: "relationships", risk: "low" },
            ],
          },
        }),
      ),
    ),
  );

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const operationSection = screen.getByRole("region", { name: "章节操作" });

  expect(within(operationSection).queryByRole("region", { name: "重要变动" })).not.toBeInTheDocument();
  expect(screen.queryByText("AI 只返回了设定分区标签，未提取到可写入的具体变动。")).not.toBeInTheDocument();
  expect(document.body).not.toHaveTextContent("characters");
  expect(document.body).not.toHaveTextContent("relationships");
});

test("major state changes require confirmation before approval", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ majorChange: true }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const approveButton = screen.getByRole("button", { name: APPROVE_NEXT_LABEL });
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
  const approveButton = screen.getByRole("button", { name: APPROVE_NEXT_LABEL });
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
  const approveButton = screen.getByRole("button", { name: APPROVE_NEXT_LABEL });
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
          revisedText: "更新后的正文。",
        }),
      ),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const approveButton = screen.getByRole("button", { name: APPROVE_NEXT_LABEL });
  fireEvent.click(screen.getByLabelText("确认写入重大变化"));
  expect(approveButton).toBeEnabled();

  const textSection = screen.getByRole("region", { name: "章节正文" });
  fireEvent.click(within(textSection).getByRole("button", { name: "编辑" }));
  fireEvent.change(within(textSection).getByLabelText("章节正文手动编辑"), { target: { value: "更新后的正文。" } });
  fireEvent.click(within(textSection).getByRole("button", { name: "保存" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/chapters/12/edit", expect.any(Object)));
  await waitFor(() => expect(screen.getByRole("button", { name: APPROVE_NEXT_LABEL })).toBeDisabled());
});

test("running chapters hide approval decisions", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ status: "running" }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("章节生成中");
  expect(screen.queryByRole("button", { name: APPROVE_NEXT_LABEL })).not.toBeInTheDocument();
});

test("running chapters hide manual edit and repair tools", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ status: "running", riskLevel: "high" }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());

  expect(screen.queryByRole("button", { name: "编辑" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("章节正文手动编辑")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("人工意见")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: REPAIR_LABEL })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: APPROVE_NEXT_LABEL })).not.toBeInTheDocument();
});

test("accepted chapters hide manual edit and repair tools but keep export", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ status: "accepted" }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());

  expect(screen.queryByRole("button", { name: "编辑" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("章节正文手动编辑")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("人工意见")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: REPAIR_LABEL })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "导出正文" })).toHaveAttribute("href", "/api/chapters/12/export.txt");
});

test("planned chapters only allow the run primary action", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ status: "planned" }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "生成本章" })).toBeInTheDocument());

  expect(screen.queryByRole("button", { name: "编辑" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("章节正文手动编辑")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("人工意见")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: REPAIR_LABEL })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: APPROVE_NEXT_LABEL })).not.toBeInTheDocument();
});

test("chapter review hides export link when chapter id is missing", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ chapterId: null }))));
  render(<ChapterPage chapterId={12} />);
  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
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

test("chapter text card toggles manual edit and saves the revised body", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload()))
    .mockResolvedValueOnce(Response.json(chapterPayload({ revisedText: "人工修正文。" })));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const textSection = screen.getByRole("region", { name: "章节正文" });
  expect(screen.queryByRole("button", { name: "高级审核工具" })).not.toBeInTheDocument();
  expect(within(textSection).getByText("岑星抵达静默港湾。")).toBeInTheDocument();

  fireEvent.click(within(textSection).getByRole("button", { name: "编辑" }));

  const editor = within(textSection).getByLabelText("章节正文手动编辑");
  expect(editor).toHaveValue("岑星抵达静默港湾。");
  expect(within(textSection).getByRole("button", { name: "保存" })).toBeInTheDocument();

  fireEvent.change(editor, { target: { value: "人工修正文。" } });
  fireEvent.click(within(textSection).getByRole("button", { name: "保存" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chapters/12/edit",
      expect.objectContaining({
        body: JSON.stringify({ revisedText: "人工修正文。" }),
        method: "POST",
      }),
    ),
  );
});

test("chapter text edit can cancel and discard unsaved changes", async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce(Response.json(chapterPayload()));
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("confirm", vi.fn(() => false));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const textSection = screen.getByRole("region", { name: "章节正文" });
  fireEvent.click(within(textSection).getByRole("button", { name: "编辑" }));
  fireEvent.change(within(textSection).getByLabelText("章节正文手动编辑"), { target: { value: "临时改动。" } });

  fireEvent.click(within(textSection).getByRole("button", { name: "取消" }));

  expect(confirm).toHaveBeenCalledWith("是否保存当前正文修改？");
  expect(within(textSection).queryByLabelText("章节正文手动编辑")).not.toBeInTheDocument();
  expect(within(textSection).getByText("岑星抵达静默港湾。")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test("chapter text cancel can save unsaved changes after confirmation", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload()))
    .mockResolvedValueOnce(Response.json(chapterPayload({ revisedText: "确认保存。" })));
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("confirm", vi.fn(() => true));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const textSection = screen.getByRole("region", { name: "章节正文" });
  fireEvent.click(within(textSection).getByRole("button", { name: "编辑" }));
  fireEvent.change(within(textSection).getByLabelText("章节正文手动编辑"), { target: { value: "确认保存。" } });

  fireEvent.click(within(textSection).getByRole("button", { name: "取消" }));

  expect(confirm).toHaveBeenCalledWith("是否保存当前正文修改？");
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chapters/12/edit",
      expect.objectContaining({
        body: JSON.stringify({ revisedText: "确认保存。" }),
        method: "POST",
      }),
    ),
  );
});

test("chapter review keeps export and approval actions without advanced review tools", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload()))
    .mockResolvedValueOnce(Response.json(chapterPayload({ status: "accepted" })));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "高级审核工具" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "导出正文" })).toHaveAttribute("href", "/api/chapters/12/export.txt");

  fireEvent.click(screen.getByRole("button", { name: APPROVE_NEXT_LABEL }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chapters/12/approve",
      expect.objectContaining({ method: "POST" }),
    ),
  );
});

test("approve action describes trusted-state write while pending", async () => {
  let resolveApprove: ((response: Response) => void) | null = null;
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload()))
    .mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          resolveApprove = resolve;
        }),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: APPROVE_NEXT_LABEL }));

  expect(await screen.findByRole("button", { name: "写入可信设定中..." })).toBeDisabled();

  resolveApprove?.(Response.json(chapterPayload({ status: "accepted" })));
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
  fireEvent.change(screen.getByLabelText("人工意见"), { target: { value: "补强结尾。" } });
  fireEvent.click(screen.getByRole("button", { name: REPAIR_LABEL }));

  await waitFor(() => expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("修复中..."));
  pushStreamEvent(streamController, { type: "stage", message: "正在审计风险。" });
  await waitFor(() => expect(screen.getByRole("button", { name: /正在审计风险/ })).toBeDisabled());
  expect(screen.queryByText("正在补强结尾冲突")).not.toBeInTheDocument();
});

test("high-risk AI revision can use a trimmed manual note", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload({ riskLevel: "high" })))
    .mockResolvedValueOnce(streamResponse([{ type: "done", chapter: chapterPayload({ status: "running" }) }]));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const revisionButton = screen.getByRole("button", { name: REPAIR_LABEL });
  expect(revisionButton).toBeEnabled();
  fireEvent.change(screen.getByLabelText("人工意见"), { target: { value: "  补强结尾。  " } });
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
  const revisionButton = screen.getByRole("button", { name: REPAIR_LABEL });
  expect(screen.queryByRole("button", { name: "退回修订" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: APPROVE_NEXT_LABEL })).not.toBeInTheDocument();
  expect(revisionButton).toBeEnabled();
  fireEvent.change(screen.getByLabelText("人工意见"), { target: { value: "  重写冲突段落。  " } });
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

test("unresolved revision tags can trigger one-click AI repair without manual notes", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json(
        chapterPayload({
          auditIssues: [{ title: "结尾动力不足", severity: "medium", resolved: false }],
        }),
      ),
    )
    .mockResolvedValueOnce(streamResponse([{ type: "done", chapter: chapterPayload({ status: "awaiting_review" }) }]));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const repairButton = screen.getByRole("button", { name: "一键让 AI 修正" });
  expect(repairButton).toBeEnabled();
  fireEvent.click(repairButton);

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chapters/12/repair-stream",
      expect.objectContaining({
        body: JSON.stringify({}),
        method: "POST",
      }),
    ),
  );
});

test("rejects action responses without chapter payload", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload({ riskLevel: "high" })))
    .mockResolvedValueOnce(streamResponse([{ type: "done", chapterId: 12, redirectTo: "/chapters/12" }]));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("人工意见"), { target: { value: "补强结尾。" } });
  fireEvent.click(screen.getByRole("button", { name: REPAIR_LABEL }));

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("章节数据格式无效。"));
  expect(screen.queryByText("任务已提交，页面会自动刷新。")).not.toBeInTheDocument();
});

test("run action enters running state from the action response", async () => {
  let streamController: ReadableStreamDefaultController<Uint8Array> | null = null;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      streamController = controller;
    },
  });
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(chapterPayload({ status: "planned" })))
    .mockResolvedValueOnce(new Response(stream));
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "生成本章" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "生成本章" }));

  pushStreamEvent(streamController, { type: "stage", message: "正在生成草稿。" });
  await waitFor(() => expect(screen.getByRole("button", { name: /正在生成草稿/ })).toBeDisabled());
  pushStreamEvent(streamController, { type: "done", chapter: chapterPayload({ status: "running" }) });
  await waitFor(() => expect(screen.getByText("运行中")).toBeInTheDocument());
  expect(screen.queryByText("任务已提交，页面会自动刷新。")).not.toBeInTheDocument();
  expect(screen.queryByRole("status", { name: "正在生成草稿" })).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/chapters/12/run-stream",
    expect.objectContaining({ method: "POST" }),
  );
});

test("approve button writes trusted state and moves to the next chapter workbench", async () => {
  window.history.pushState(null, "", "/books/42/chapters/12");
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json(
        chapterPayload({
          siblingChapters: [
            chapterSummary({ id: 12, number: 2, status: "awaiting_review" }),
            chapterSummary({ id: 13, number: 3, status: "planned", title: "潮汐灯塔" }),
          ],
        }),
      ),
    )
    .mockResolvedValueOnce(
      Response.json(
        chapterPayload({
          status: "accepted",
          siblingChapters: [
            chapterSummary({ id: 12, number: 2, status: "accepted" }),
            chapterSummary({ id: 13, number: 3, status: "planned", title: "潮汐灯塔" }),
          ],
        }),
      ),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<ChapterPage bookId={42} chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: APPROVE_NEXT_LABEL }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chapters/12/approve",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  await waitFor(() => expect(window.location.pathname).toBe("/books/42/chapters/13"));
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
  siblingChapters = [],
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
  siblingChapters?: Array<Record<string, unknown>>;
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
    siblingChapters,
    latestCanon: null,
    traces: [],
    stageSlots: [
      { key: "plan", label: "规划", ready: true, status: "ready", summary: "进入港湾" },
      { key: "context", label: "上下文", ready: true, status: "ready", summary: "可信设定第 2 版" },
      { key: "draft", label: "草稿", ready: true, status: "ready", summary: "7 字" },
      { key: "delta", label: "状态变化", ready: !emptyReview, status: emptyReview ? "empty" : "ready", summary: "" },
      { key: "audit", label: "审计", ready: !emptyReview, status: emptyReview ? "empty" : "ready", summary: "" },
    ],
  };
}

function chapterSummary({
  id,
  number,
  status,
  title = "静默港湾",
}: {
  id: number;
  number: number;
  status: string;
  title?: string;
}) {
  return {
    id,
    bookId: 42,
    number,
    title,
    status,
    summary: "",
    wordCount: 0,
    reviewerNote: null,
    updatedAt: "2026-05-16T00:00:00+00:00",
  };
}
