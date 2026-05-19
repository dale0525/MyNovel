import { ArrowLeft, Download, PencilLine, Save, X } from "lucide-react";
import { useEffect, useState } from "react";

import { AiWaitingIndicator } from "@/components/feedback/AiWaitingIndicator";
import {
  ChapterReviewActions,
  type ChapterReviewAction,
  type ReviewIssueDisplay,
} from "@/features/chapters/ChapterReviewActions";
import {
  ProjectIdentityBar,
} from "@/components/guidance/GuidedPanels";
import { ApiError, getJson, isAbortError, postJson, postJsonLineStream } from "@/lib/api";
import { navigateTo } from "@/lib/navigation";
import { type LlmStreamEvent, streamPreviewLine } from "@/lib/streaming";
import type { ChapterDetailPayload, ChapterPayload, ChapterResponse } from "@/lib/types";

type ChapterPageState =
  | { status: "loading"; data: null; error: null }
  | { status: "ready"; data: ChapterResponse; error: null }
  | { status: "error"; data: null; error: string };

type ActionState =
  | { status: "idle"; action: null; message: null }
  | { status: "submitting"; action: ChapterReviewAction; message: null; progressLabel: string | null }
  | { status: "success"; action: null; message: string | null }
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
    setActionState({ status: "submitting", action, message: null, progressLabel: null });
    try {
      let nextPath: string | null = null;
      if (action === "repair" || action === "run") {
        let completed = false;
        await postJsonLineStream<ChapterStreamEvent>(
          `/api/chapters/${chapterId}/${action}-stream`,
          body,
          (streamEvent) => {
            const progressLabel = streamEventProgressLabel(streamEvent);
            if (progressLabel) {
              setActionState((current) => {
                if (current.status !== "submitting" || current.action !== action) {
                  return current;
                }
                return { ...current, progressLabel };
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
        if (action === "approve") {
          nextPath = nextChapterWorkbenchPath(parsed, chapterId, bookId);
        }
      }
      setActionState({
        status: "success",
        action: null,
        message: successMessageForAction(action),
      });
      if (nextPath) {
        navigateTo(nextPath);
      }
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
  const reviewIssues = auditIssueDisplays(auditReportIssues(chapter.auditReport));
  const importantChanges = meaningfulStateChanges(chapter.stateDelta);

  return (
    <section className={embedded ? "chapter-page chapter-page--embedded" : "workbench-page chapter-page"} aria-label={chapter.title}>
      <ProjectIdentityBar
        className="chapter-review-identity"
        eyebrow="章节审核"
        title={chapter.title}
        summary={chapter.summary || "本章尚未形成摘要。"}
        meta={[
          { label: "项目", value: book.title },
          { label: "章节", value: `第 ${chapter.number} 章` },
          { label: "状态", value: chapterStatusLabel(chapter.status) },
          { label: "设定", value: latestCanon ? `第 ${latestCanon.version} 版` : "未连接可信设定" },
        ]}
        actions={(
          <div className="chapter-identity-actions">
            {parentBookId === null ? null : (
              <a className="workbench-secondary-link chapter-back-link" href={`/books/${parentBookId}/chapters`}>
                <ArrowLeft aria-hidden="true" size={16} />
                返回章节
              </a>
            )}
          </div>
        )}
      />

      {actionState.status === "success" && actionState.message ? (
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
          importantChanges={importantChanges}
          majorChange={hasMajorStateChange(chapter.stateDelta)}
          onAction={(action, body) => void submitAction(action, body)}
          reviewIssues={reviewIssues}
          actionProgressLabel={actionState.status === "submitting" ? actionState.progressLabel : null}
        />
        <ChapterTextPanel
          actionBusy={actionState.status === "submitting" ? actionState.action : null}
          chapter={chapter}
          onSave={(revisedText) => submitAction("edit", { revisedText })}
        />
      </main>
    </section>
  );
}

function successMessageForAction(action: ChapterReviewAction): string | null {
  return action === "edit" || action === "request-revision" ? "操作已保存。" : null;
}

function streamEventProgressLabel(event: ChapterStreamEvent): string {
  if (!["started", "stage", "applying"].includes(event.type)) {
    return "";
  }
  const text = typeof event.message === "string" ? event.message : "";
  return text ? streamPreviewLine(text) : "";
}

function nextChapterWorkbenchPath(
  response: ChapterResponse,
  currentChapterId: number,
  parentBookId?: number,
): string | null {
  const nextChapter = nextChapterAfter(response.siblingChapters, response.chapter, currentChapterId);
  const bookId = parentBookId ?? response.book.id ?? response.chapter.bookId;
  if (nextChapter?.id !== null && nextChapter?.id !== undefined) {
    return `/books/${bookId}/chapters/${nextChapter.id}`;
  }
  return `/books/${bookId}/chapters`;
}

function nextChapterAfter(
  siblings: ChapterPayload[],
  currentChapter: ChapterDetailPayload,
  currentChapterId: number,
): ChapterPayload | null {
  const currentNumber = currentChapter.number;
  const currentId = currentChapter.id ?? currentChapterId;
  return [...siblings]
    .filter((chapter) => chapter.id !== null && chapter.id !== currentId && chapter.number > currentNumber)
    .sort((left, right) => left.number - right.number)[0] ?? null;
}

type StateChangeDisplay = {
  target: string;
  detail: string;
  major: boolean;
};

function ChapterTextPanel({
  actionBusy,
  chapter,
  onSave,
}: {
  actionBusy: ChapterReviewAction | null;
  chapter: ChapterDetailPayload;
  onSave: (revisedText: string) => Promise<void>;
}) {
  const bodyText = chapter.finalText || chapter.revisedText || chapter.draftText || "";
  const displayText = bodyText || "正文尚未生成。";
  const canEdit = chapter.status === "awaiting_review" || chapter.status === "needs_revision";
  const [editing, setEditing] = useState(false);
  const [draftText, setDraftText] = useState(bodyText);
  const trimmedDraft = draftText.trim();
  const saving = actionBusy === "edit";
  const hasUnsavedChanges = draftText !== bodyText;

  useEffect(() => {
    if (!editing) {
      setDraftText(bodyText);
    }
  }, [bodyText, editing]);

  function startEditing() {
    setDraftText(bodyText);
    setEditing(true);
  }

  function saveDraft() {
    if (!trimmedDraft || saving) {
      return;
    }
    void onSave(draftText).finally(() => setEditing(false));
  }

  function cancelEditing() {
    if (!hasUnsavedChanges) {
      setDraftText(bodyText);
      setEditing(false);
      return;
    }
    if (window.confirm("是否保存当前正文修改？")) {
      saveDraft();
      return;
    }
    setDraftText(bodyText);
    setEditing(false);
  }

  return (
    <section className="workbench-panel chapter-reader" aria-labelledby="chapter-text-title">
      <header className="chapter-reader__head">
        <div>
          <p className="eyebrow">正文</p>
          <h2 id="chapter-text-title">章节正文</h2>
        </div>
        <div className="chapter-reader__actions">
          {chapter.id !== null ? (
            <a className="workbench-secondary-link chapter-export-link" href={`/api/chapters/${chapter.id}/export.txt`}>
              <Download aria-hidden="true" size={16} />
              导出正文
            </a>
          ) : null}
          {canEdit ? (
            <>
              <button
                className={editing ? "workbench-action-button" : "workbench-secondary-button"}
                disabled={saving || (editing && !trimmedDraft)}
                type="button"
                onClick={editing ? saveDraft : startEditing}
              >
                {editing ? (
                  saving ? (
                    <AiWaitingIndicator label="保存中..." variant="inline" />
                  ) : (
                    <>
                      <Save aria-hidden="true" size={16} />
                      保存
                    </>
                  )
                ) : (
                  <>
                    <PencilLine aria-hidden="true" size={16} />
                    编辑
                  </>
                )}
              </button>
              {editing ? (
                <button
                  className="workbench-secondary-button"
                  disabled={saving}
                  type="button"
                  onClick={cancelEditing}
                >
                  <X aria-hidden="true" size={16} />
                  取消
                </button>
              ) : null}
            </>
          ) : null}
        </div>
      </header>
      {editing ? (
        <textarea
          aria-label="章节正文手动编辑"
          className="chapter-text-editor"
          disabled={saving}
          value={draftText}
          onChange={(event) => setDraftText(event.target.value)}
        />
      ) : (
        <div className="chapter-text-body">{displayText}</div>
      )}
    </section>
  );
}

function hasHighRiskAudit(chapter: ChapterDetailPayload): boolean {
  if (normalizedText(chapter.auditReport.risk_level) === "high") {
    return true;
  }
  return auditReportIssues(chapter.auditReport).some(
    (issue) => normalizedText(issue.severity) === "high" && !auditIssueResolved(issue),
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

function meaningfulStateChanges(stateDelta: Record<string, unknown>): StateChangeDisplay[] {
  return stateDeltaChanges(stateDelta).flatMap((change, index) => {
    if (isLowInformationStateChange(change)) {
      return [];
    }
    const display = stateChangeDisplay(change, index);
    return display === null ? [] : [display];
  });
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

type NormalizedReviewIssue = ReviewIssueDisplay & {
  key: string;
  wordCountIssue: boolean;
};

const WORD_COUNT_ISSUE_KEY = "word-count-target";
const WORD_COUNT_RESOLVED_TITLE = "字数已在目标区间";
const WORD_COUNT_UNMET_TITLE = "字数不在目标区间";

function auditIssueDisplays(issues: Record<string, unknown>[]): ReviewIssueDisplay[] {
  const byKey = new Map<string, NormalizedReviewIssue>();
  for (const [index, issue] of issues.entries()) {
    const display = auditIssueDisplay(issue, index);
    const previous = byKey.get(display.key);
    if (!previous) {
      byKey.set(display.key, display);
      continue;
    }
    previous.resolved = previous.resolved && display.resolved;
  }

  return [...byKey.values()].map(({ title, resolved, wordCountIssue }) => ({
    title: wordCountIssue ? wordCountIssueTitle(resolved) : title,
    resolved,
  }));
}

function auditIssueDisplay(issue: Record<string, unknown>, index: number): NormalizedReviewIssue {
  const title = stringValue(issue.title) || stringValue(issue.type) || `问题 ${index + 1}`;
  const wordCountIssue = isWordCountAuditIssue(issue, title);
  return {
    key: wordCountIssue ? WORD_COUNT_ISSUE_KEY : normalizedText(title),
    title,
    resolved: auditIssueResolved(issue),
    wordCountIssue,
  };
}

function wordCountIssueTitle(resolved: boolean): string {
  return resolved ? WORD_COUNT_RESOLVED_TITLE : WORD_COUNT_UNMET_TITLE;
}

function isWordCountAuditIssue(issue: Record<string, unknown>, title: string): boolean {
  const issueText = [
    title,
    issue.type,
    issue.detail,
    issue.description,
    issue.suggestion,
    issue.suggested_fix,
  ].map(stringValue).join(" ");
  const normalized = issueText.toLowerCase();
  return (
    normalized.includes("字数") ||
    normalized.includes("目标区间") ||
    normalized.includes("word count") ||
    normalized.includes("word_count")
  );
}

function stateChangeDisplay(change: Record<string, unknown>, index: number): StateChangeDisplay | null {
  const rawTarget = stateChangeValueText(change.target) || stateChangeValueText(change.entity);
  const rawDetail = (
    stateChangeValueText(change.change)
    || stateChangeValueText(change.summary)
    || stateChangeValueText(change.detail)
    || stateChangeValueText(change.description)
  );
  const rawType = stringValue(change.type);
  const [splitTarget, splitDetail] = splitTargetFromDetail(rawDetail);
  let target = rawTarget || splitTarget;
  let detail = splitDetail || rawDetail;

  if ((isGenericStateTarget(target) || isSectionKey(target)) && splitTarget) {
    target = splitTarget;
  }
  if (isGenericStateTarget(target) || isSectionKey(target)) {
    target = "";
  }
  if (isSectionKey(detail) || isGenericStateTarget(detail)) {
    detail = "";
  }
  if (!detail && rawType && !isGenericStateTarget(rawType) && !isSectionKey(rawType)) {
    detail = rawType;
  }
  if (!target && !detail) {
    return null;
  }

  return {
    target: target || `变化 ${index + 1}`,
    detail: detail || "待写入",
    major: isMajorChangeRecord(change),
  };
}

function stateChangeValueText(value: unknown): string {
  const directValue = stringValue(value);
  if (directValue) {
    return directValue;
  }
  if (Array.isArray(value)) {
    return value
      .map(stateChangeValueText)
      .filter(Boolean)
      .join("；");
  }
  if (isRecord(value)) {
    return stateChangeObjectSummary(value);
  }
  return "";
}

function stateChangeObjectSummary(value: Record<string, unknown>): string {
  const direct = (
    stringValue(value.summary)
    || stringValue(value.description)
    || stringValue(value.detail)
    || stringValue(value.change)
    || stringValue(value.value)
    || stringValue(value.text)
    || stringValue(value.name)
  );
  if (direct) {
    return direct;
  }

  const before = stateChangeValueText(value.before);
  const after = stateChangeValueText(value.after);
  if (before && after) {
    return `${before} -> ${after}`;
  }
  if (after) {
    return after;
  }
  if (before) {
    return before;
  }

  return Object.entries(value)
    .filter(([key]) => !isSectionKey(key) && !isGenericStateTarget(key))
    .map(([key, itemValue]) => {
      const summary = stateChangeValueText(itemValue);
      return summary ? `${key}：${summary}` : "";
    })
    .filter(Boolean)
    .slice(0, 3)
    .join("；");
}

function splitTargetFromDetail(value: string): [string, string] {
  const separatorIndex = value.search(/[：:]/);
  if (separatorIndex <= 0) {
    return ["", value];
  }
  const target = value.slice(0, separatorIndex).trim();
  const detail = value.slice(separatorIndex + 1).trim();
  return target && detail ? [target, detail] : ["", value];
}

function isLowInformationStateChange(change: Record<string, unknown>): boolean {
  const target = stateChangeValueText(change.target) || stateChangeValueText(change.entity);
  const detail = (
    stateChangeValueText(change.change)
    || stateChangeValueText(change.summary)
    || stateChangeValueText(change.detail)
    || stateChangeValueText(change.description)
  );
  const type = stringValue(change.type);
  const hasConcreteTarget = Boolean(target) && !isGenericStateTarget(target) && !isSectionKey(target);
  const hasConcreteDetail = Boolean(detail) && !isGenericStateTarget(detail) && !isSectionKey(detail);
  const typeIsGeneric = !type || isGenericStateTarget(type) || isSectionKey(type);
  return !hasConcreteTarget && !hasConcreteDetail && typeIsGeneric;
}

function isGenericStateTarget(value: string): boolean {
  const normalized = normalizedText(value);
  return [
    "待确认",
    "待定",
    "待写入",
    "未确认",
    "未知",
    "无",
    "unknown",
    "n/a",
    "none",
    "todo",
    "change",
    "changes",
    "state change",
    "状态变化",
    "设定变化",
    "变化",
  ].includes(normalized);
}

function isSectionKey(value: string): boolean {
  const normalized = normalizedText(value).replaceAll("-", "_").replaceAll(" ", "_");
  return [
    "character",
    "characters",
    "relations",
    "relationship",
    "relationships",
    "location",
    "locations",
    "resource",
    "resources",
    "faction",
    "factions",
    "foreshadowing",
    "information_exposure",
    "timeline",
    "timelines",
    "event",
    "events",
    "plot",
    "plots",
    "world",
    "world_rules",
    "rule",
    "rules",
    "item",
    "items",
    "人物",
    "角色",
    "关系",
    "地点",
    "场景",
    "资源",
    "阵营",
    "组织",
    "伏笔",
    "信息揭示",
    "时间线",
    "事件",
    "剧情",
    "世界观",
    "规则",
    "道具",
    "设定",
  ].includes(normalized);
}

function stringValue(value: unknown): string {
  if (typeof value === "string") {
    return value.trim();
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

function normalizedText(value: unknown): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

function auditIssueResolved(issue: Record<string, unknown>): boolean {
  const value = issue.resolved;
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    return value === 1;
  }
  if (typeof value === "string") {
    return ["true", "1", "yes", "y", "resolved", "fixed", "已解决", "已修正", "已满足"].includes(
      value.trim().toLowerCase(),
    );
  }
  return false;
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
