import { useEffect, useState } from "react";

import { getJson, isAbortError } from "@/lib/api";
import type { BookPayload, BookResponse, ChapterPayload, RunTracePayload } from "@/lib/types";

type BookWorkspaceState =
  | { status: "loading"; data: null; error: null }
  | { status: "ready"; data: BookResponse; error: null }
  | { status: "error"; data: null; error: string };

type BookWorkspacePageProps = {
  bookId: number;
};

export function BookWorkspacePage({ bookId }: BookWorkspacePageProps) {
  const [state, setState] = useState<BookWorkspaceState>({
    status: "loading",
    data: null,
    error: null,
  });

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
  const recentTraces = [...runTraces].reverse().slice(0, 4);

  return (
    <section className="workbench-page book-workspace-page" aria-labelledby="book-workspace-title">
      <div className="workbench-hero book-workspace-hero">
        <p className="eyebrow">Project Workspace</p>
        <h1 id="book-workspace-title">{book.title}</h1>
        <p className="book-workspace-meta">
          {book.genre} · {book.audience} · {statusLabel(book.status)}
        </p>
        <p className="lede">{book.premise ?? "这个项目还没有记录核心承诺，下一步可以先补齐故事前提。"}</p>
      </div>

      <div className="content-grid workspace-focus-layout">
        <aside className="workbench-panel">
          <p className="eyebrow">Project Pulse</p>
          <h2>项目状态</h2>
          <dl className="book-workspace-facts">
            <div>
              <dt>章节</dt>
              <dd>{chapters.length}</dd>
            </div>
            <div>
              <dt>卷纲</dt>
              <dd>{volumePlans.length}</dd>
            </div>
            <div>
              <dt>定盘版本</dt>
              <dd>{latestCanon ? `v${latestCanon.version}` : "未生成"}</dd>
            </div>
          </dl>
        </aside>

        <main className="workspace-focus-card workbench-panel">
          <section className="workspace-current-task" aria-labelledby="current-task-title">
            <div>
              <p className="eyebrow">Current Focus</p>
              <h2 id="current-task-title">当前任务</h2>
              {currentTask ? (
                <>
                  <strong>
                    第 {currentTask.number} 章 · {currentTask.title}
                  </strong>
                  <p>{chapterStatusLabel(currentTask.status)}：{currentTask.summary || "等待补齐章节摘要。"}</p>
                </>
              ) : (
                <p>暂无待推进章节。可以先检查可信设定，再创建章节生产任务。</p>
              )}
            </div>
            <div className="workspace-primary-action">
              <a className="workbench-action-button" href={`/books/${bookId}/state`}>
                查看可信设定
              </a>
            </div>
          </section>

          <section className="workspace-foundation-panel" aria-labelledby="canon-summary-title">
            <div className="workspace-section-head">
              <div>
                <p className="eyebrow">Trusted State</p>
                <h2 id="canon-summary-title">可信设定摘要</h2>
              </div>
              <span>{latestCanon ? `Canon v${latestCanon.version}` : "尚未定盘"}</span>
            </div>
            <div className="workspace-foundation-grid">
              {canonSummaryCards(latestCanon?.content ?? {}).map((item) => (
                <article className="workspace-snapshot-card" key={item.label}>
                  <strong>{item.label}</strong>
                  <p>{item.value}</p>
                </article>
              ))}
            </div>
          </section>

          <section aria-labelledby="chapter-queue-title">
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
                  <strong>
                    第 {chapter.number} 章 · {chapter.title}
                  </strong>
                  <span>{chapterStatusLabel(chapter.status)} · {chapter.wordCount} 字</span>
                </li>
              ))}
            </ol>
          </section>
        </main>

        <aside className="workspace-result-sidebar">
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
            {volumePlans.slice(0, 3).map((plan) => (
              <article className="workspace-volume-plan" key={plan.id ?? plan.volumeNumber}>
                <strong>
                  第 {plan.volumeNumber} 卷 · {plan.title}
                </strong>
                <p>{plan.coreConflict}</p>
              </article>
            ))}
          </section>
        </aside>
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
    chapters: [],
    latestCanon: null,
    runTraces: [],
    volumePlans: [],
  };
  if (
    payload.chapters === undefined &&
    payload.latestCanon === undefined &&
    payload.runTraces === undefined &&
    payload.volumePlans === undefined
  ) {
    return bookOnlyResponse;
  }
  if (
    !Array.isArray(payload.chapters) ||
    !Array.isArray(payload.runTraces) ||
    !Array.isArray(payload.volumePlans) ||
    (payload.latestCanon !== null && !isRecord(payload.latestCanon))
  ) {
    return null;
  }
  return {
    book: payload.book,
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

function currentChapterTask(chapters: ChapterPayload[]): ChapterPayload | null {
  return (
    chapters.find((chapter) => ["running", "awaiting_review", "needs_revision"].includes(chapter.status)) ??
    chapters.find((chapter) => chapter.status === "planned") ??
    chapters[0] ??
    null
  );
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
