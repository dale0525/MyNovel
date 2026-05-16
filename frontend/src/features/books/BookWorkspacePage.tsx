import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import { AiWaitingIndicator } from "@/components/feedback/AiWaitingIndicator";
import {
  AdvancedDisclosure,
  ImpactPanel,
  type ImpactItem,
  PrimaryActionPanel,
  ProjectIdentityBar,
} from "@/components/guidance/GuidedPanels";
import { ApiError, getJson, isAbortError, postJson } from "@/lib/api";
import { navigateTo } from "@/lib/navigation";
import type { BookPayload, BookResponse, ChapterPayload, RunTracePayload, WordTargetsPayload } from "@/lib/types";

type BookWorkspaceState =
  | { status: "loading"; data: null; error: null }
  | { status: "ready"; data: BookResponse; error: null }
  | { status: "error"; data: null; error: string };

type BookWorkspacePageProps = {
  bookId: number;
};

type WorkspaceAction = "run-current" | "run-batch" | "word-targets";

type ActionRedirectResponse = {
  redirectTo: string;
};

type WorkspacePrimaryActionModel = {
  title: string;
  summary: string;
  action: ReactNode;
  impactItems: ImpactItem[];
};

type WorkspacePrimaryActionParams = {
  bookId: number;
  currentTask: ChapterPayload | null;
  productionReady: boolean;
  actionBusy: WorkspaceAction | null;
  runCurrentChapter: (chapter: ChapterPayload) => void;
};

export function BookWorkspacePage({ bookId }: BookWorkspacePageProps) {
  const [state, setState] = useState<BookWorkspaceState>({
    status: "loading",
    data: null,
    error: null,
  });
  const [actionBusy, setActionBusy] = useState<WorkspaceAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [batchLimit, setBatchLimit] = useState(1);
  const [targetWordCount, setTargetWordCount] = useState(120000);
  const [chapterWordCount, setChapterWordCount] = useState(2800);
  const [updateExistingChapters, setUpdateExistingChapters] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    setState({ status: "loading", data: null, error: null });

    getJson<unknown>(`/api/books/${bookId}`, { signal: controller.signal })
      .then((payload) => {
        const parsed = parseBookResponse(payload);
        if (!cancelled) {
          if (parsed) {
            setState({ status: "ready", data: parsed, error: null });
            setTargetWordCount(parsed.wordTargets.targetWordCount);
            setChapterWordCount(parsed.wordTargets.chapterWordCount);
          } else {
            setState({ status: "error", data: null, error: "项目数据格式无效。" });
          }
        }
      })
      .catch((error: unknown) => {
        if (isAbortError(error)) {
          return;
        }
        if (!cancelled) {
          setState({
            status: "error",
            data: null,
            error: error instanceof Error ? error.message : "项目加载失败。",
          });
        }
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [bookId]);

  async function runCurrentChapter(chapter: ChapterPayload) {
    const chapterId = chapter.id;
    if (chapterId === null || chapterId === undefined) {
      setActionError("章节条目不完整，无法运行。");
      setActionStatus(null);
      return;
    }
    await runAction("run-current", async () => {
      const payload = await postJson<unknown>(`/api/chapters/${chapterId}/run`, {});
      const response = parseActionRedirectResponse(payload);
      if (!response) {
        throw new Error("运行结果格式无效。");
      }
      navigateTo(response.redirectTo);
    });
  }

  async function runBatchProduction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runAction("run-batch", async () => {
      const payload = await postJson<unknown>(`/api/books/${bookId}/chapters/run-batch`, {
        limit: batchLimit,
      });
      const response = parseActionRedirectResponse(payload);
      if (!response) {
        throw new Error("批量生产结果格式无效。");
      }
      navigateTo(response.redirectTo);
    });
  }

  async function saveWordTargets(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runAction("word-targets", async () => {
      const payload = await postJson<unknown>(`/api/books/${bookId}/word-targets`, {
        targetWordCount,
        chapterWordCount,
        updateExistingChapters,
      });
      const response = parseBookResponse(payload);
      if (!response) {
        throw new Error("目标字数保存结果格式无效。");
      }
      setState({ status: "ready", data: response, error: null });
      setTargetWordCount(response.wordTargets.targetWordCount);
      setChapterWordCount(response.wordTargets.chapterWordCount);
      setActionStatus("目标字数已保存。");
    });
  }

  async function runAction(action: WorkspaceAction, callback: () => Promise<void>) {
    setActionBusy(action);
    setActionError(null);
    setActionStatus(null);
    try {
      await callback();
    } catch (error) {
      setActionError(errorMessage(error, "操作失败。"));
    } finally {
      setActionBusy(null);
    }
  }

  if (state.status === "loading") {
    return (
      <section className="workbench-page" aria-labelledby="book-workspace-title">
        <div className="workbench-panel" role="status">
          正在加载项目...
        </div>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="workbench-page" aria-labelledby="book-workspace-title">
        <div className="workbench-panel workbench-panel--alert" role="alert">
          <h1 id="book-workspace-title">项目加载失败</h1>
          <p>{state.error}</p>
          <a className="workbench-action-button" href="/">
            返回工作台
          </a>
        </div>
      </section>
    );
  }

  const { book, chapters, latestCanon, runTraces, volumePlans } = state.data;
  const currentTask = currentChapterTask(chapters);
  const productionReady = latestCanon !== null && book.status !== "draft";
  const recentTraces = [...runTraces].reverse().slice(0, 4);
  const primaryAction = workspacePrimaryAction({
    bookId,
    currentTask,
    productionReady,
    actionBusy,
    runCurrentChapter: (chapter) => void runCurrentChapter(chapter),
  });

  return (
    <section className="workbench-page book-workspace-page" aria-label={book.title}>
      <ProjectIdentityBar
        eyebrow="Project"
        title={book.title}
        meta={[
          { label: "题材", value: book.genre },
          { label: "读者", value: book.audience },
          { label: "状态", value: statusLabel(book.status) },
          { label: "Canon", value: latestCanon ? `v${latestCanon.version}` : "尚未定盘" },
        ]}
        actions={
          <div className="book-workspace-identity-note">
            <p className="book-workspace-meta">
              {book.genre} · {book.audience} · {statusLabel(book.status)}
            </p>
            <p className="lede">{book.premise ?? "这个项目还没有记录核心承诺，下一步可以先补齐故事前提。"}</p>
          </div>
        }
      />

      <PrimaryActionPanel
        eyebrow="Current"
        title={primaryAction.title}
        summary={<p>{primaryAction.summary}</p>}
        action={primaryAction.action}
        impact={<ImpactPanel embedded title="影响预览" items={primaryAction.impactItems} />}
      />

      {actionError ? (
        <section className="workspace-result-section workspace-result-section--alert" role="alert">
          {actionError}
        </section>
      ) : null}
      {actionStatus ? (
        <section className="workspace-result-section workspace-result-section--success" role="status">
          {actionStatus}
        </section>
      ) : null}

      <section className="guided-status-strip" aria-labelledby="canon-summary-title">
        <div className="workspace-section-head">
          <div>
            <p className="eyebrow">Trusted State</p>
            <h2 id="canon-summary-title">可信设定摘要</h2>
          </div>
          <a className="workbench-secondary-link" href={`/books/${bookId}/state`}>
            查看可信设定
          </a>
        </div>
        <div className="workspace-foundation-grid">
          {canonSummaryCards(latestCanon?.content ?? {}).map((item) => (
            <a className="workspace-snapshot-card" href={`/books/${bookId}/state`} key={item.label}>
              <strong>{item.label}</strong>
              <p>{item.value}</p>
            </a>
          ))}
        </div>
      </section>

      <AdvancedDisclosure title="项目工具">
        <div className="guided-tools-grid">
          <section className="workspace-result-section" aria-labelledby="chapter-queue-title">
            <div className="workspace-section-head">
              <div>
                <p className="eyebrow">Chapter Queue</p>
                <h2 id="chapter-queue-title">章节队列</h2>
              </div>
              <span>{chapters.length} 个章节</span>
            </div>
            <ol className="workspace-mini-list">
              {chapters.slice(0, 8).map((chapter) => (
                <li key={chapter.id ?? chapter.number}>
                  {chapter.id === null || chapter.id === undefined ? (
                    <strong>第 {chapter.number} 章 · {chapter.title}</strong>
                  ) : (
                    <a className="workspace-mini-list-link" href={`/chapters/${chapter.id}`}>
                      第 {chapter.number} 章 · {chapter.title}
                    </a>
                  )}
                  <span>{chapterStatusLabel(chapter.status)} · {chapter.wordCount} 字</span>
                </li>
              ))}
            </ol>
          </section>

          <section className="workspace-result-section" aria-labelledby="workspace-actions-title">
            <p className="eyebrow">Controls</p>
            <h2 id="workspace-actions-title">工作台操作</h2>
            <div className="book-workspace-actions">
              <a className="workbench-action-button" href={`/books/${bookId}/quality`}>
                质量中心
              </a>
              <a className="workbench-secondary-link" href={`/api/books/${bookId}/export.md`}>
                导出 Markdown
              </a>
              <a className="workbench-secondary-link" href={`/api/books/${bookId}/export.json`}>
                导出 JSON
              </a>
            </div>
          </section>

          <section className="workspace-result-section" aria-labelledby="batch-production-title">
            <p className="eyebrow">Production</p>
            <h2 id="batch-production-title">批量生产</h2>
            {productionReady ? (
              <form className="chapter-action-form" onSubmit={(event) => void runBatchProduction(event)}>
                <label>
                  批量章节数
                  <input
                    max={10}
                    min={1}
                    type="number"
                    value={batchLimit}
                    onChange={(event) => setBatchLimit(clampedPositiveInt(event.target.value, 1, 10))}
                  />
                </label>
                <button className="workbench-action-button" disabled={actionBusy !== null} type="submit">
                  {actionBusy === "run-batch" ? (
                    <AiWaitingIndicator label="提交批量中..." variant="inline" />
                  ) : (
                    "批量生产"
                  )}
                </button>
              </form>
            ) : (
              <p>可信设定锁定后才能批量生产章节。</p>
            )}
          </section>

          <section className="workspace-result-section" aria-labelledby="word-target-title">
            <p className="eyebrow">Word Targets</p>
            <h2 id="word-target-title">目标字数</h2>
            <form className="chapter-action-form" onSubmit={(event) => void saveWordTargets(event)}>
              <label>
                全书目标字数
                <input
                  min={1}
                  type="number"
                  value={targetWordCount}
                  onChange={(event) => setTargetWordCount(clampedPositiveInt(event.target.value, 1))}
                />
              </label>
              <label>
                单章目标字数
                <input
                  min={1}
                  type="number"
                  value={chapterWordCount}
                  onChange={(event) => setChapterWordCount(clampedPositiveInt(event.target.value, 1))}
                />
              </label>
              <label className="chapter-major-change-toggle">
                <input
                  checked={updateExistingChapters}
                  type="checkbox"
                  onChange={(event) => setUpdateExistingChapters(event.target.checked)}
                />
                同步更新已有章节计划
              </label>
              <button className="workbench-action-button" disabled={actionBusy !== null} type="submit">
                {actionBusy === "word-targets" ? "保存中..." : "保存目标字数"}
              </button>
            </form>
          </section>

          <section className="workspace-result-section" aria-labelledby="ai-progress-title">
            <p className="eyebrow">AI Progress</p>
            <h2 id="ai-progress-title">最近 AI 进度</h2>
            {recentTraces.length ? (
              <div className="timeline-stack">
                {recentTraces.map((trace) => (
                  <article className="workspace-trace-row" key={trace.id ?? trace.createdAt ?? trace.stage}>
                    <span>{trace.model ?? "local"}</span>
                    <div>
                      <strong>{trace.stage}</strong>
                      <span>{trace.promptId ?? "未记录 prompt"} · {formatTraceCost(trace)}</span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p>还没有 AI 运行记录。</p>
            )}
          </section>

          <section className="workspace-result-section">
            <p className="eyebrow">Volume Plan</p>
            <h2>卷纲</h2>
            {volumePlans.length ? (
              volumePlans.slice(0, 3).map((plan) => (
                <article className="workspace-volume-plan" key={plan.id ?? plan.volumeNumber}>
                  <strong>
                    第 {plan.volumeNumber} 卷 · {plan.title}
                  </strong>
                  <p>{plan.coreConflict}</p>
                </article>
              ))
            ) : (
              <p>还没有卷纲。</p>
            )}
          </section>
        </div>
      </AdvancedDisclosure>
    </section>
  );
}

function workspacePrimaryAction({
  bookId,
  currentTask,
  productionReady,
  actionBusy,
  runCurrentChapter,
}: WorkspacePrimaryActionParams): WorkspacePrimaryActionModel {
  if (!productionReady) {
    return {
      title: "继续推进项目",
      summary: "可信设定还没有达到生产就绪状态，下一步应先调整并锁定可信设定。",
      action: (
        <a className="workbench-action-button" href={`/books/${bookId}/state`}>
          调整可信设定
        </a>
      ),
      impactItems: [
        { label: "生产", value: "不会启动章节生产", tone: "warning" },
        { label: "可信设定", value: "先补齐项目基础", tone: "neutral" },
      ],
    };
  }

  if (!currentTask) {
    return {
      title: "继续推进项目",
      summary: "当前没有待推进章节，可以检查可信设定并准备下一批章节任务。",
      action: (
        <a className="workbench-action-button" href={`/books/${bookId}/state`}>
          检查可信设定
        </a>
      ),
      impactItems: [
        { label: "章节", value: "没有待处理章节", tone: "neutral" },
        { label: "生产", value: "不会启动章节生产", tone: "neutral" },
      ],
    };
  }

  const chapterTitle = `第 ${currentTask.number} 章 · ${currentTask.title}`;

  if (currentTask.id === null || currentTask.id === undefined) {
    return {
      title: "继续推进项目",
      summary: `${chapterTitle} 的章节条目不完整，先检查可信设定并修正项目数据。`,
      action: (
        <a className="workbench-action-button" href={`/books/${bookId}/state`}>
          检查可信设定
        </a>
      ),
      impactItems: [
        { label: "章节", value: "章节条目不完整", tone: "danger" },
        { label: "生产", value: "不会启动章节生产", tone: "warning" },
      ],
    };
  }

  const chapterId = currentTask.id;

  if (currentTask.status === "awaiting_review") {
    return {
      title: "继续推进项目",
      summary: `${chapterTitle} 正在等待审阅，审核后才会写入可信设定。`,
      action: (
        <a className="workbench-action-button" href={`/chapters/${chapterId}`}>
          打开章节审核
        </a>
      ),
      impactItems: [
        { label: "可信设定", value: "审核后才会写入", tone: "good" },
        { label: "章节", value: chapterTitle, tone: "neutral" },
      ],
    };
  }

  if (currentTask.status === "running") {
    return {
      title: "继续推进项目",
      summary: `${chapterTitle} 正在生成中，AI 正在处理候选正文。`,
      action: (
        <a className="workbench-action-button" href={`/chapters/${chapterId}`}>
          查看生成进度
        </a>
      ),
      impactItems: [
        { label: "AI", value: "正在处理章节", tone: "neutral" },
        { label: "可信设定", value: "暂不写入可信设定", tone: "warning" },
      ],
    };
  }

  if (canRunChapter(currentTask)) {
    return {
      title: "继续推进项目",
      summary: `${chapterTitle} 已准备好生成候选正文。`,
      action: (
        <button
          className="workbench-action-button"
          disabled={actionBusy !== null}
          type="button"
          onClick={() => runCurrentChapter(currentTask)}
        >
          {actionBusy === "run-current" ? (
            <AiWaitingIndicator label="提交章节中..." variant="inline" />
          ) : (
            "运行当前章节"
          )}
        </button>
      ),
      impactItems: [
        { label: "正文", value: "生成候选正文", tone: "good" },
        { label: "可信设定", value: "不会直接写入", tone: "warning" },
        { label: "下一步", value: "进入章节审核", tone: "neutral" },
      ],
    };
  }

  return {
    title: "继续推进项目",
    summary: `${chapterTitle} 需要先回到章节页处理当前状态。`,
    action: (
      <a className="workbench-action-button" href={`/chapters/${chapterId}`}>
        打开当前章节
      </a>
    ),
    impactItems: [
      { label: "章节", value: chapterStatusLabel(currentTask.status), tone: "neutral" },
      { label: "可信设定", value: "等待章节完成后更新", tone: "neutral" },
    ],
  };
}

function parseBookResponse(payload: unknown): BookResponse | null {
  if (!isRecord(payload) || !isBookPayload(payload.book)) {
    return null;
  }
  const bookOnlyResponse = {
    book: payload.book,
    wordTargets: defaultWordTargets(),
    chapters: [],
    latestCanon: null,
    runTraces: [],
    volumePlans: [],
  };
  if (
    payload.chapters === undefined &&
    payload.latestCanon === undefined &&
    payload.runTraces === undefined &&
    payload.volumePlans === undefined &&
    payload.wordTargets === undefined
  ) {
    return bookOnlyResponse;
  }
  if (
    !Array.isArray(payload.chapters) ||
    !Array.isArray(payload.runTraces) ||
    !Array.isArray(payload.volumePlans) ||
    (payload.latestCanon !== null && !isRecord(payload.latestCanon)) ||
    !isWordTargetsPayload(payload.wordTargets)
  ) {
    return null;
  }
  return {
    book: payload.book,
    wordTargets: payload.wordTargets,
    chapters: payload.chapters as BookResponse["chapters"],
    latestCanon: payload.latestCanon as BookResponse["latestCanon"],
    runTraces: payload.runTraces as BookResponse["runTraces"],
    volumePlans: payload.volumePlans as BookResponse["volumePlans"],
  };
}

function isBookPayload(value: unknown): value is BookPayload {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "number" &&
    typeof value.title === "string" &&
    typeof value.genre === "string" &&
    typeof value.audience === "string" &&
    typeof value.status === "string" &&
    (typeof value.premise === "string" || value.premise === null)
  );
}

function isWordTargetsPayload(value: unknown): value is WordTargetsPayload {
  return (
    isRecord(value) &&
    typeof value.targetWordCount === "number" &&
    typeof value.chapterWordCount === "number"
  );
}

function defaultWordTargets(): WordTargetsPayload {
  return {
    targetWordCount: 120000,
    chapterWordCount: 2800,
  };
}

function parseActionRedirectResponse(payload: unknown): ActionRedirectResponse | null {
  if (!isRecord(payload) || !isSafeAppPath(payload.redirectTo)) {
    return null;
  }
  return { redirectTo: payload.redirectTo };
}

function isSafeAppPath(value: unknown): value is string {
  return typeof value === "string" && value.startsWith("/") && !value.startsWith("//");
}

function currentChapterTask(chapters: ChapterPayload[]): ChapterPayload | null {
  const activeTask = chapters.find((chapter) =>
    ["running", "awaiting_review", "needs_revision"].includes(chapter.status),
  );
  if (activeTask) {
    return activeTask;
  }
  return (
    chapters.find((chapter) => chapter.status === "planned") ??
    null
  );
}

function canRunChapter(chapter: ChapterPayload): boolean {
  return ["planned", "needs_revision"].includes(chapter.status);
}

function canonSummaryCards(content: Record<string, unknown>) {
  return [
    { label: "世界规则", value: summarizeCanonValue(content.world_rules) },
    { label: "人物", value: summarizeCanonValue(content.characters) },
    { label: "章节摘要", value: summarizeCanonValue(content.chapter_summaries) },
    { label: "伏笔账本", value: summarizeCanonValue(content.foreshadowing) },
  ];
}

function summarizeCanonValue(value: unknown): string {
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return "暂无记录";
    }
    return value.slice(0, 2).map(shortValue).join("；");
  }
  return shortValue(value);
}

function shortValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (isRecord(value)) {
    const first = Object.values(value).find((item) => item !== null && item !== "");
    return shortValue(first);
  }
  if (value === null || value === undefined) {
    return "暂无记录";
  }
  return String(value);
}

function formatTraceCost(trace: RunTracePayload): string {
  const tokens = trace.cost.tokens;
  return typeof tokens === "number" ? `${tokens} tokens` : "成本未记录";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

function clampedPositiveInt(value: string, min: number, max?: number): number {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return min;
  }
  const withMin = Math.max(min, parsed);
  return max === undefined ? withMin : Math.min(withMin, max);
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: "草稿",
    canon_locked: "可信设定已锁定",
    producing: "生产中",
    paused: "暂停",
  };
  return labels[status] ?? status;
}

function chapterStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    planned: "待生产",
    running: "生成中",
    awaiting_review: "待审阅",
    needs_revision: "需修订",
    accepted: "已接受",
  };
  return labels[status] ?? status;
}
