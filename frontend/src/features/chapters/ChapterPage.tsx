import { useEffect, useState } from "react";

import {
  ChapterReviewActions,
  type ChapterReviewAction,
} from "@/features/chapters/ChapterReviewActions";
import {
  type ImpactItem,
  ProjectIdentityBar,
} from "@/components/guidance/GuidedPanels";
import { ApiError, getJson, isAbortError, postJson, postJsonLineStream } from "@/lib/api";
import { type LlmStreamEvent, nextStreamSnippets, streamEventPreview } from "@/lib/streaming";
import type { ChapterDetailPayload, ChapterResponse } from "@/lib/types";

type ChapterPageState =
  | { status: "loading"; data: null; error: null }
  | { status: "ready"; data: ChapterResponse; error: null }
  | { status: "error"; data: null; error: string };

type ActionState =
  | { status: "idle"; action: null; message: null }
  | { status: "submitting"; action: ChapterReviewAction; message: null; streamSnippets: string[] }
  | { status: "success"; action: null; message: string }
  | { status: "error"; action: null; message: string };

type ChapterStreamEvent = LlmStreamEvent<{
  chapter?: unknown;
  chapterId?: number;
  redirectTo?: string;
} & Record<string, unknown>>;

export function ChapterPage({
  bookId,
  chapterId,
  embedded = false,
}: {
  bookId?: number;
  chapterId: number;
  embedded?: boolean;
}) {
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
  const [pollKey, setPollKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let controller: AbortController | null = null;

    function loadChapter() {
      controller?.abort();
      controller = new AbortController();
      setState((current) =>
        current.status === "ready" && current.data.chapter.id === chapterId
          ? current
          : { status: "loading", data: null, error: null },
      );
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

    loadChapter();

    return () => {
      cancelled = true;
      controller?.abort();
    };
  }, [chapterId, pollKey]);

  useEffect(() => {
    if (state.status !== "ready" || state.data.chapter.status !== "running") {
      return;
    }
    const pollTimer = setTimeout(() => setPollKey((current) => current + 1), 3000);
    return () => clearTimeout(pollTimer);
  }, [state]);

  async function submitAction(action: ChapterReviewAction, body: Record<string, unknown>) {
    setActionState({ status: "submitting", action, message: null, streamSnippets: [] });
    try {
      if (action === "repair" || action === "run") {
        let completed = false;
        await postJsonLineStream<ChapterStreamEvent>(
          `/api/chapters/${chapterId}/${action}-stream`,
          body,
          (streamEvent) => {
            const snippet = streamEventPreview(streamEvent);
            if (snippet) {
              setActionState((current) => {
                if (current.status !== "submitting" || current.action !== action) {
                  return current;
                }
                return {
                  ...current,
                  streamSnippets: nextStreamSnippets(current.streamSnippets, snippet),
                };
              });
            }
            if (streamEvent.type === "failed") {
              throw new Error(typeof streamEvent.message === "string" ? streamEvent.message : "章节动作失败。");
            }
            if (streamEvent.type === "done") {
              completed = true;
              const parsed = parseChapterResponse(streamEvent.chapter);
              if (!parsed) {
                throw new Error("章节数据格式无效。");
              }
              setState({ status: "ready", data: parsed, error: null });
            }
          },
        );
        if (!completed) {
          throw new Error("章节动作没有返回结果。");
        }
      } else {
        const payload = await postJson<unknown>(`/api/chapters/${chapterId}/${action}`, body);
        const parsed = parseChapterResponse(payload);
        if (!parsed) {
          throw new Error("章节数据格式无效。");
        }
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
      <section className={embedded ? "chapter-page chapter-page--embedded" : "workbench-page"} aria-labelledby="chapter-page-title">
        <div className={embedded ? "workspace-result-section" : "workbench-panel"} role="status">
          正在加载章节...
        </div>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className={embedded ? "chapter-page chapter-page--embedded" : "workbench-page"} aria-labelledby="chapter-page-title">
        <div className={embedded ? "workspace-result-section workspace-result-section--alert" : "workbench-panel workbench-panel--alert"} role="alert">
          <h1 id="chapter-page-title">章节加载失败</h1>
          <p>{state.error}</p>
          <a className="workbench-action-button" href="/">
            返回工作台
          </a>
        </div>
      </section>
    );
  }

  const { book, chapter, latestCanon } = state.data;
  const parentBookId = bookId ?? book.id;

  return (
    <section className={embedded ? "chapter-page chapter-page--embedded" : "workbench-page chapter-page"} aria-label={chapter.title}>
      <ProjectIdentityBar
        eyebrow="章节审核"
        title={chapter.title}
        meta={[
          { label: "项目", value: book.title },
          { label: "章节", value: `第 ${chapter.number} 章` },
          { label: "状态", value: chapterStatusLabel(chapter.status) },
          { label: "设定", value: latestCanon ? `第 ${latestCanon.version} 版` : "未连接可信设定" },
        ]}
        actions={(
          <div className="chapter-identity-actions">
            <p className="lede">{chapter.summary || "本章尚未形成摘要。"}</p>
            {parentBookId === null ? null : (
              <a className="workbench-secondary-link" href={`/books/${parentBookId}/chapters`}>
                返回章节
              </a>
            )}
          </div>
        )}
      />

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

      <main className="chapter-operation-flow">
        <ChapterReviewActions
          actionBusy={actionState.status === "submitting" ? actionState.action : null}
          chapter={chapter}
          highRisk={hasHighRiskAudit(chapter)}
          impactItems={chapterImpactItems(chapter)}
          majorChange={hasMajorStateChange(chapter.stateDelta)}
          onAction={(action, body) => void submitAction(action, body)}
          streamSnippets={actionState.status === "submitting" ? actionState.streamSnippets : []}
        />
        <section className="workbench-panel chapter-reader" aria-labelledby="chapter-text-title">
          <p className="eyebrow">正文</p>
          <h2 id="chapter-text-title">章节正文</h2>
          <div className="chapter-text-body">{chapter.finalText || chapter.revisedText || chapter.draftText || "正文尚未生成。"}</div>
        </section>
        <ChapterReviewDetails chapter={chapter} />
      </main>
    </section>
  );
}

function chapterImpactItems(chapter: ChapterDetailPayload): ImpactItem[] {
  const changes = stateDeltaChanges(chapter.stateDelta);
  if (changes.length === 0) {
    return [{ label: "可信设定", value: "无状态变化", tone: "neutral" }];
  }

  return changes.slice(0, 4).map((change, index) => ({
    label: String(change.target ?? `变化 ${index + 1}`),
    value: String(change.change ?? "待写入"),
    tone: isMajorChangeRecord(change) ? "danger" : "warning",
  }));
}

function ChapterReviewDetails({ chapter }: { chapter: ChapterDetailPayload }) {
  const auditIssues = auditReportIssues(chapter.auditReport);
  const changes = stateDeltaChanges(chapter.stateDelta);

  return (
    <div className="chapter-review-details">
      <section className="workbench-panel" aria-labelledby="chapter-revision-notes-title">
        <p className="eyebrow">修订</p>
        <h2 id="chapter-revision-notes-title">修正意见</h2>
        {auditIssues.length > 0 ? (
          <ol className="chapter-detail-list">
            {auditIssues.map((issue, index) => (
              <li key={`${String(issue.title ?? "issue")}-${index}`}>
                {auditIssueSummary(issue, index)}
              </li>
            ))}
          </ol>
        ) : (
          <p>暂无修正意见。</p>
        )}
      </section>

      <section className="workbench-panel" aria-labelledby="chapter-state-delta-title">
        <p className="eyebrow">设定变化</p>
        <h2 id="chapter-state-delta-title">设定变动</h2>
        {changes.length > 0 ? (
          <ol className="chapter-detail-list chapter-detail-list--changes">
            {changes.map((change, index) => (
              <li key={`${String(change.target ?? "change")}-${index}`}>
                {stateChangeSummary(change, index)}
              </li>
            ))}
          </ol>
        ) : (
          <p>暂无设定变动。</p>
        )}
      </section>
    </div>
  );
}

function hasHighRiskAudit(chapter: ChapterDetailPayload): boolean {
  if (normalizedText(chapter.auditReport.risk_level) === "high") {
    return true;
  }
  return auditReportIssues(chapter.auditReport).some(
    (issue) => normalizedText(issue.severity) === "high" && issue.resolved !== true,
  );
}

function hasMajorStateChange(stateDelta: Record<string, unknown>): boolean {
  if (stateDelta.majorChange === true) {
    return true;
  }
  if (Array.isArray(stateDelta.major_changes) && stateDelta.major_changes.length > 0) {
    return true;
  }
  return stateDeltaChanges(stateDelta).some(isMajorChangeRecord);
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
    (typeof value.id === "number" || value.id === null) &&
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

function isMajorChangeRecord(change: Record<string, unknown>): boolean {
  if (change.major === true || normalizedText(change.severity) === "major") {
    return true;
  }

  const impact = typeof change.impact === "string" ? change.impact.toLowerCase() : "";
  if (["major", "critical", "high"].includes(impact)) {
    return true;
  }

  const majorTerms = ["角色死亡", "人物死亡", "死亡", "牺牲", "退场", "核心设定", "改写设定"];
  const changeText = [change.type, change.target, change.change]
    .filter((value) => typeof value === "string")
    .join(" ");
  return majorTerms.some((term) => changeText.includes(term));
}

function auditIssueSummary(issue: Record<string, unknown>, index: number): string {
  const title = String(issue.title ?? issue.type ?? `问题 ${index + 1}`);
  const severity = String(issue.severity ?? "未标注");
  const status = issue.resolved === true ? "已解决" : "未解决";
  return `${title} · ${severity} · ${status}`;
}

function stateChangeSummary(change: Record<string, unknown>, index: number): string {
  const target = String(change.target ?? change.entity ?? `变化 ${index + 1}`);
  const detail = String(change.change ?? change.summary ?? change.type ?? "待写入");
  return `${target}：${detail}`;
}

function normalizedText(value: unknown): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

function chapterStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    planned: "已规划",
    running: "运行中",
    awaiting_review: "待审核",
    needs_revision: "需修订",
    accepted: "已批准",
  };
  return labels[status] ?? "未知状态";
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
