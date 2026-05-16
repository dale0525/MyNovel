import { type FormEvent, useEffect, useState } from "react";

import { AiStreamFeedback } from "@/components/feedback/AiStreamFeedback";
import { AiWaitingIndicator } from "@/components/feedback/AiWaitingIndicator";
import { ProjectIdentityBar } from "@/components/guidance/GuidedPanels";
import { ApiError, getJson, isAbortError, postJson, postJsonLineStream } from "@/lib/api";
import { navigateTo } from "@/lib/navigation";
import { type LlmStreamEvent, nextStreamSnippets, streamEventPreview } from "@/lib/streaming";
import type { BookPayload, BookResponse, ChapterPayload, WordTargetsPayload } from "@/lib/types";

type BookWorkspaceState =
  | { status: "loading"; data: null; error: null }
  | { status: "ready"; data: BookResponse; error: null }
  | { status: "error"; data: null; error: string };

type BookWorkspacePageProps = {
  bookId: number;
};

type WorkspaceAction = "run-batch" | "word-targets" | "volume-outline";

type ActionRedirectResponse = {
  redirectTo: string;
};

type WorkspaceStreamEvent = LlmStreamEvent<
  ActionRedirectResponse & { book?: unknown } & Record<string, unknown>
>;

type VolumeSection = {
  key: string;
  plan: BookResponse["volumePlans"][number] | null;
  chapters: ChapterPayload[];
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
  const [streamAction, setStreamAction] = useState<WorkspaceAction | null>(null);
  const [streamSnippets, setStreamSnippets] = useState<string[]>([]);
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

  async function runBatchProduction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runAction("run-batch", async () => {
      await runStreamingRedirect(`/api/books/${bookId}/chapters/run-batch-stream`, {
        limit: batchLimit,
      });
    });
  }

  async function generateVolumeOutline() {
    await runAction("volume-outline", async () => {
      let response: BookResponse | null = null;
      await postJsonLineStream<WorkspaceStreamEvent>(
        `/api/books/${bookId}/volume-outline/generate-stream`,
        {},
        (streamEvent) => {
          const snippet = streamEventPreview(streamEvent);
          if (snippet) {
            setStreamSnippets((current) => nextStreamSnippets(current, snippet));
          }
          if (streamEvent.type === "failed") {
            throw new Error(typeof streamEvent.message === "string" ? streamEvent.message : "卷纲生成失败。");
          }
          if (streamEvent.type === "done") {
            response = parseBookResponse(streamEvent.book);
            if (!response) {
              throw new Error("卷纲生成结果格式无效。");
            }
          }
        },
      );
      if (!response) {
        throw new Error("卷纲生成没有返回结果。");
      }
      setState({ status: "ready", data: response, error: null });
      setActionStatus("卷纲已生成。");
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
    setStreamAction(action);
    setStreamSnippets([]);
    try {
      await callback();
    } catch (error) {
      setActionError(errorMessage(error, "操作失败。"));
    } finally {
      setActionBusy(null);
    }
  }

  async function runStreamingRedirect(path: string, body: Record<string, unknown>) {
    let redirectTo: string | null = null;
    await postJsonLineStream<WorkspaceStreamEvent>(path, body, (streamEvent) => {
      const snippet = streamEventPreview(streamEvent);
      if (snippet) {
        setStreamSnippets((current) => nextStreamSnippets(current, snippet));
      }
      if (streamEvent.type === "failed") {
        throw new Error(typeof streamEvent.message === "string" ? streamEvent.message : "操作失败。");
      }
      if (streamEvent.type === "done") {
        const response = parseActionRedirectResponse(streamEvent);
        if (!response) {
          throw new Error("运行结果格式无效。");
        }
        redirectTo = response.redirectTo;
      }
    });
    if (!redirectTo) {
      throw new Error("操作没有返回结果。");
    }
    navigateTo(redirectTo);
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

  const { book, chapters, latestCanon, volumePlans } = state.data;
  const productionReady = latestCanon !== null && book.status !== "draft";
  const batchReady = productionReady && chapters.some(canBatchRunChapter);
  const volumeSections = volumePlanSections(volumePlans, chapters);
  const totalWordCount = chapters.reduce((total, chapter) => total + chapter.wordCount, 0);

  return (
    <section className="workbench-page book-workspace-page" aria-label={book.title}>
      <ProjectIdentityBar
        eyebrow="Project"
        title={book.title}
        meta={[
          { label: "设定", value: latestCanon ? `v${latestCanon.version}` : "尚未定盘" },
        ]}
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

      <div className="book-workspace-sections">
        <section className="workspace-result-section" aria-labelledby="basic-info-title">
          <p className="eyebrow">Basic</p>
          <h2 id="basic-info-title">基本信息</h2>
          <dl className="book-workspace-facts">
            <div>
              <dt>题材</dt>
              <dd>{book.genre || "未填写"}</dd>
            </div>
            <div>
              <dt>目标读者</dt>
              <dd>{book.audience || "未填写"}</dd>
            </div>
            <div>
              <dt>状态</dt>
              <dd>{statusLabel(book.status)}</dd>
            </div>
            <div>
              <dt>已有正文</dt>
              <dd>{totalWordCount} 字</dd>
            </div>
          </dl>
          <p>{book.premise ?? "这个项目还没有记录核心承诺。"}</p>
        </section>

        <section className="workspace-result-section" aria-labelledby="word-target-title">
          <p className="eyebrow">Project Settings</p>
          <h2 id="word-target-title">项目设定</h2>
          <form className="chapter-action-form book-workspace-inline-form" onSubmit={(event) => void saveWordTargets(event)}>
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

        <section className="workspace-result-section" aria-labelledby="canon-summary-title">
          <div className="workspace-section-head">
            <div>
              <p className="eyebrow">Canon</p>
              <h2 id="canon-summary-title">设定</h2>
            </div>
            <a className="workbench-secondary-link" href={`/books/${bookId}/state`}>
              打开设定
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

        <section className="workspace-result-section" aria-labelledby="volume-outline-title">
          <div className="workspace-section-head">
            <div>
              <p className="eyebrow">Outline</p>
              <h2 id="volume-outline-title">卷纲列表</h2>
            </div>
            <button
              className="workbench-action-button"
              disabled={actionBusy !== null}
              type="button"
              onClick={() => void generateVolumeOutline()}
            >
              {actionBusy === "volume-outline" ? (
                <AiWaitingIndicator label="生成卷纲中..." variant="inline" />
              ) : (
                "让 AI 生成卷纲"
              )}
            </button>
          </div>
          <AiStreamFeedback snippets={streamAction === "volume-outline" ? streamSnippets : []} />
          <div className="workspace-volume-list">
            {volumeSections.map((section) => (
              <article className="workspace-volume-plan" key={section.key}>
                {section.plan ? (
                  <>
                    <strong>
                      第 {section.plan.volumeNumber} 卷 · {section.plan.title}
                    </strong>
                    <p>{section.plan.coreConflict}</p>
                  </>
                ) : (
                  <>
                    <strong>未分卷章节</strong>
                    <p>还没有卷纲，先保留当前章节队列。</p>
                  </>
                )}
                <h3>章节列表</h3>
                {section.chapters.length ? (
                  <ol className="workspace-mini-list">
                    {section.chapters.map((chapter) => (
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
                ) : (
                  <p>这一卷还没有章节规划。</p>
                )}
              </article>
            ))}
          </div>
        </section>

        <section className="workspace-result-section" aria-labelledby="batch-production-title">
          <p className="eyebrow">Batch</p>
          <h2 id="batch-production-title">批量操作</h2>
          {batchReady ? (
            <form className="chapter-action-form book-workspace-batch-form" onSubmit={(event) => void runBatchProduction(event)}>
              <label>
                生成章节数
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
                  "批量生成"
                )}
              </button>
              <AiStreamFeedback snippets={streamAction === "run-batch" ? streamSnippets : []} />
            </form>
          ) : productionReady ? (
            <p>没有可批量生成的章节。</p>
          ) : (
            <p>可信设定锁定后才能批量生成章节。</p>
          )}
        </section>
      </div>
    </section>
  );
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

function canBatchRunChapter(chapter: ChapterPayload): boolean {
  return ["planned", "running", "needs_revision"].includes(chapter.status);
}

function volumePlanSections(
  volumePlans: BookResponse["volumePlans"],
  chapters: ChapterPayload[],
): VolumeSection[] {
  const sortedChapters = [...chapters].sort((left, right) => left.number - right.number);
  if (volumePlans.length === 0) {
    return [{ key: "unassigned", plan: null, chapters: sortedChapters }];
  }

  return [...volumePlans]
    .sort((left, right) => left.volumeNumber - right.volumeNumber)
    .map((plan) => {
      const start = (plan.volumeNumber - 1) * 10 + 1;
      const end = plan.volumeNumber * 10;
      const matchedChapters = sortedChapters.filter(
        (chapter) => {
          const volumeNumber = chapterVolumeNumber(chapter);
          if (volumeNumber !== null) {
            return volumeNumber === plan.volumeNumber;
          }
          return chapter.number >= start && chapter.number <= end;
        },
      );
      return {
        key: String(plan.id ?? plan.volumeNumber),
        plan,
        chapters: matchedChapters,
      };
    });
}

function chapterVolumeNumber(chapter: ChapterPayload): number | null {
  if (typeof chapter.volumeNumber === "number" && Number.isFinite(chapter.volumeNumber)) {
    const volumeNumber = Math.trunc(chapter.volumeNumber);
    return volumeNumber > 0 ? volumeNumber : null;
  }
  return null;
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
