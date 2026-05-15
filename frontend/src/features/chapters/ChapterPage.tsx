import { useEffect, useState } from "react";

import {
  ChapterReviewActions,
  type ChapterReviewAction,
} from "@/features/chapters/ChapterReviewActions";
import { ChapterStageBoard } from "@/features/chapters/ChapterStageBoard";
import { ApiError, getJson, isAbortError, postJson } from "@/lib/api";
import type { ChapterDetailPayload, ChapterResponse } from "@/lib/types";

type ChapterPageState =
  | { status: "loading"; data: null; error: null }
  | { status: "ready"; data: ChapterResponse; error: null }
  | { status: "error"; data: null; error: string };

type ActionState =
  | { status: "idle"; action: null; message: null }
  | { status: "submitting"; action: ChapterReviewAction; message: null }
  | { status: "success"; action: null; message: string }
  | { status: "error"; action: null; message: string };

export function ChapterPage({ chapterId }: { chapterId: number }) {
  const [state, setState] = useState<ChapterPageState>({
    status: "loading",
    data: null,
    error: null,
  });
  const [actionState, setActionState] = useState<ActionState>({
    status: "idle",
    action: null,
    message: null,
  });

  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;
    let controller: AbortController | null = null;

    function loadChapter(initial = false) {
      controller?.abort();
      controller = new AbortController();
      if (initial) {
        setState({ status: "loading", data: null, error: null });
      }
      getJson<unknown>(`/api/chapters/${chapterId}`, { signal: controller.signal })
        .then((payload) => {
          const parsed = parseChapterResponse(payload);
          if (cancelled) {
            return;
          }
          if (!parsed) {
            setState({ status: "error", data: null, error: "章节数据格式无效。" });
            return;
          }
          setState({ status: "ready", data: parsed, error: null });
          if (parsed.chapter.status === "running") {
            pollTimer = setTimeout(() => loadChapter(false), 3000);
          }
        })
        .catch((error: unknown) => {
          if (isAbortError(error) || cancelled) {
            return;
          }
          setState({
            status: "error",
            data: null,
            error: error instanceof Error ? error.message : "章节加载失败。",
          });
        });
    }

    loadChapter(true);

    return () => {
      cancelled = true;
      if (pollTimer) {
        clearTimeout(pollTimer);
      }
      controller?.abort();
    };
  }, [chapterId]);

  async function submitAction(action: ChapterReviewAction, body: Record<string, unknown>) {
    setActionState({ status: "submitting", action, message: null });
    try {
      const payload = await postJson<unknown>(`/api/chapters/${chapterId}/${action}`, body);
      const parsed = parseChapterResponse(payload);
      if (parsed) {
        setState({ status: "ready", data: parsed, error: null });
      }
      setActionState({
        status: "success",
        action: null,
        message: action === "repair" || action === "run" ? "任务已提交，页面会自动刷新。" : "操作已保存。",
      });
    } catch (error) {
      setActionState({
        status: "error",
        action: null,
        message: errorMessage(error, "章节动作失败。"),
      });
    }
  }

  if (state.status === "loading") {
    return (
      <section className="workbench-page" aria-labelledby="chapter-page-title">
        <div className="workbench-panel" role="status">
          正在加载章节...
        </div>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="workbench-page" aria-labelledby="chapter-page-title">
        <div className="workbench-panel workbench-panel--alert" role="alert">
          <h1 id="chapter-page-title">章节加载失败</h1>
          <p>{state.error}</p>
          <a className="workbench-action-button" href="/">
            返回工作台
          </a>
        </div>
      </section>
    );
  }

  const { book, chapter, siblingChapters, latestCanon, traces, stageSlots } = state.data;

  return (
    <section className="workbench-page chapter-page" aria-labelledby="chapter-page-title">
      <div className="workbench-hero chapter-hero">
        <p className="eyebrow">Chapter Review</p>
        <h1 id="chapter-page-title">{chapter.title}</h1>
        <p className="book-workspace-meta">
          {book.title} · 第 {chapter.number} 章 · {chapterStatusLabel(chapter.status)}
        </p>
        <p className="lede">{chapter.summary || "本章尚未形成摘要。"}</p>
      </div>

      <ChapterStageBoard slots={stageSlots} traces={traces} />

      {actionState.status === "success" ? (
        <p className="setup-message" role="status">
          {actionState.message}
        </p>
      ) : null}
      {actionState.status === "error" ? (
        <p className="setup-message" role="alert">
          {actionState.message}
        </p>
      ) : null}

      <div className="content-grid chapter-review-grid">
        <main className="chapter-review-main">
          <ResultReport chapter={chapter} canonVersion={latestCanon?.version ?? null} />
          <section className="workbench-panel chapter-reader" aria-labelledby="chapter-text-title">
            <p className="eyebrow">Manuscript</p>
            <h2 id="chapter-text-title">章节正文</h2>
            <div className="chapter-text-body">{chapter.finalText || chapter.revisedText || chapter.draftText || "正文尚未生成。"}</div>
          </section>
        </main>

        <aside className="chapter-review-sidebar">
          <ChapterReviewActions
            actionBusy={actionState.status === "submitting" ? actionState.action : null}
            chapter={chapter}
            onAction={(action, body) => void submitAction(action, body)}
          />
          <section className="workspace-result-section">
            <p className="eyebrow">Chapter Queue</p>
            <h2>相邻章节</h2>
            <ol className="workspace-mini-list">
              {siblingChapters.map((item) => (
                <li key={item.id ?? item.number}>
                  <strong>
                    第 {item.number} 章 · {item.title}
                  </strong>
                  <span>{chapterStatusLabel(item.status)}</span>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>
    </section>
  );
}

function ResultReport({ chapter, canonVersion }: { chapter: ChapterDetailPayload; canonVersion: number | null }) {
  const stateChanges = stateDeltaChanges(chapter.stateDelta);
  const auditIssues = auditReportIssues(chapter.auditReport);

  return (
    <section className="workbench-panel chapter-result-report" aria-labelledby="chapter-result-title">
      <div className="workspace-section-head">
        <div>
          <p className="eyebrow">Result First</p>
          <h2 id="chapter-result-title">结果报告</h2>
        </div>
        <span>{canonVersion ? `Canon v${canonVersion}` : "未连接可信设定"}</span>
      </div>

      <div className="chapter-result-cards">
        <article>
          <strong>状态变化</strong>
          {stateChanges.length ? (
            <ul>
              {stateChanges.map((change, index) => (
                <li key={index}>{formatChange(change)}</li>
              ))}
            </ul>
          ) : (
            <p>还没有状态变化。</p>
          )}
        </article>
        <article>
          <strong>审计报告</strong>
          {auditIssues.length || chapter.auditReport.risk_level ? (
            <>
              <p>风险级别：{String(chapter.auditReport.risk_level ?? "未标注")}</p>
              {auditIssues.length ? (
                <ul>
                  {auditIssues.map((issue, index) => (
                    <li key={index}>{formatIssue(issue)}</li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : (
            <p>还没有审计报告。</p>
          )}
        </article>
      </div>
    </section>
  );
}

function parseChapterResponse(payload: unknown): ChapterResponse | null {
  if (!isRecord(payload) || !isRecord(payload.book) || !isChapterDetail(payload.chapter)) {
    return null;
  }
  if (!Array.isArray(payload.siblingChapters) || !Array.isArray(payload.traces) || !Array.isArray(payload.stageSlots)) {
    return null;
  }
  return payload as ChapterResponse;
}

function isChapterDetail(value: unknown): value is ChapterDetailPayload {
  return (
    isRecord(value) &&
    typeof value.id === "number" &&
    typeof value.bookId === "number" &&
    typeof value.number === "number" &&
    typeof value.title === "string" &&
    typeof value.status === "string" &&
    typeof value.summary === "string" &&
    typeof value.wordCount === "number" &&
    isRecord(value.plan) &&
    isRecord(value.contextPackage) &&
    typeof value.draftText === "string" &&
    typeof value.revisedText === "string" &&
    typeof value.finalText === "string" &&
    isRecord(value.auditReport) &&
    isRecord(value.stateDelta)
  );
}

function stateDeltaChanges(stateDelta: Record<string, unknown>): Record<string, unknown>[] {
  return Array.isArray(stateDelta.changes)
    ? stateDelta.changes.filter(isRecord)
    : [];
}

function auditReportIssues(auditReport: Record<string, unknown>): Record<string, unknown>[] {
  return Array.isArray(auditReport.issues)
    ? auditReport.issues.filter(isRecord)
    : [];
}

function formatChange(change: Record<string, unknown>): string {
  return [change.target, change.change].filter(Boolean).map(String).join("：") || JSON.stringify(change);
}

function formatIssue(issue: Record<string, unknown>): string {
  const title = String(issue.title ?? "未命名问题");
  const severity = issue.severity ? ` · ${String(issue.severity)}` : "";
  const resolved = issue.resolved === true ? " · 已解决" : issue.resolved === false ? " · 未解决" : "";
  return `${title}${severity}${resolved}`;
}

function chapterStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    planned: "已规划",
    running: "运行中",
    awaiting_review: "待审核",
    needs_revision: "需修订",
    accepted: "已批准",
  };
  return labels[status] ?? status;
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
