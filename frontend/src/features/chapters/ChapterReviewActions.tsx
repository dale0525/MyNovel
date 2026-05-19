import { AlertTriangle, ListChecks, ShieldCheck, WandSparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { AiWaitingIndicator } from "@/components/feedback/AiWaitingIndicator";
import type { ChapterDetailPayload } from "@/lib/types";

export type ChapterReviewAction =
  | "run"
  | "request-revision"
  | "repair"
  | "edit"
  | "approve";

export type ReviewIssueDisplay = {
  title: string;
  resolved: boolean;
};

type ChapterReviewActionsProps = {
  chapter: ChapterDetailPayload;
  actionBusy: ChapterReviewAction | null;
  highRisk: boolean;
  importantChanges: Array<{
    target: string;
    detail: string;
    major: boolean;
  }>;
  majorChange: boolean;
  onAction: (action: ChapterReviewAction, body: Record<string, unknown>) => void;
  reviewIssues: ReviewIssueDisplay[];
  actionProgressLabel: string | null;
};

export function ChapterReviewActions({
  chapter,
  actionBusy,
  highRisk,
  importantChanges,
  majorChange,
  onAction,
  reviewIssues,
  actionProgressLabel,
}: ChapterReviewActionsProps) {
  const [repairNote, setRepairNote] = useState("");
  const [allowMajorChanges, setAllowMajorChanges] = useState(false);
  const canReview = chapter.status === "awaiting_review";
  const canRepair = canReview || chapter.status === "needs_revision";
  const repairNoteTrimmed = repairNote.trim();
  const stateDeltaSignature = JSON.stringify(chapter.stateDelta);
  const majorChangeConfirmationSignature = [
    chapter.id ?? "new",
    chapter.status,
    majorChange,
    chapter.updatedAt ?? "",
    stateDeltaSignature,
  ].join("|");
  const lastMajorChangeConfirmationSignature = useRef<string | null>(null);

  useEffect(() => {
    setRepairNote("");
  }, [chapter.id, chapter.status, chapter.updatedAt]);

  useEffect(() => {
    if (lastMajorChangeConfirmationSignature.current === null) {
      lastMajorChangeConfirmationSignature.current = majorChangeConfirmationSignature;
      return;
    }
    if (lastMajorChangeConfirmationSignature.current !== majorChangeConfirmationSignature) {
      lastMajorChangeConfirmationSignature.current = majorChangeConfirmationSignature;
      setAllowMajorChanges(false);
    }
  }, [majorChangeConfirmationSignature]);

  const busy = actionBusy !== null;
  const approveDisabled = busy || (majorChange && !allowMajorChanges);
  const hasUnresolvedIssue = reviewIssues.some((issue) => !issue.resolved);
  const runActionCopy = chapter.status === "needs_revision"
    ? { idle: "修改本章", busy: "修改中..." }
    : { idle: "生成本章", busy: "生成中..." };
  const showRunAction = chapter.status === "planned" || chapter.status === "needs_revision";
  const repairButtonIdleLabel = hasUnresolvedIssue ? "一键让 AI 修正" : "修复";

  return (
    <section className="chapter-review-actions guided-decision-panel workbench-panel" aria-labelledby="chapter-actions-title">
      <header className="chapter-action-header">
        <div>
          <p className="eyebrow">章节操作</p>
          <h2 id="chapter-actions-title">章节操作</h2>
        </div>
        <span className={`chapter-action-status chapter-action-status--${chapter.status}`}>
          {chapterStatusLabel(chapter.status)}
        </span>
      </header>

      <div className="chapter-action-primary">
        {showRunAction ? (
          <button
            className="workbench-action-button"
            disabled={busy}
            type="button"
            onClick={() => onAction("run", {})}
          >
            {actionBusy === "run" ? (
              <AiWaitingIndicator label={actionProgressLabel ?? runActionCopy.busy} variant="inline" />
            ) : (
              runActionCopy.idle
            )}
          </button>
        ) : null}

        {chapter.status === "running" ? (
          <AiWaitingIndicator
            detail="AI 正在执行章节规划、上下文检索、草稿、修订和审计流水线。"
            label="章节生成中"
          />
        ) : null}

        {canReview && !highRisk ? (
          <>
            {majorChange ? (
              <label className="chapter-major-change-toggle">
                <input
                  checked={allowMajorChanges}
                  type="checkbox"
                  onChange={(event) => setAllowMajorChanges(event.target.checked)}
                />
                确认写入重大变化
              </label>
            ) : null}
            <button
              className="workbench-action-button"
              disabled={approveDisabled}
              type="button"
              onClick={() => onAction("approve", { allowMajorChanges })}
            >
              {actionBusy === "approve" ? (
                <AiWaitingIndicator label="写入可信设定中..." variant="inline" />
              ) : (
                <>
                  <ShieldCheck aria-hidden="true" size={16} />
                  确定，下一章
                </>
              )}
            </button>
          </>
        ) : null}
      </div>

      <section className="chapter-action-section chapter-action-section--revision" aria-labelledby="chapter-revision-notes-title">
        <div className="chapter-action-section__head">
          <ListChecks aria-hidden="true" size={18} />
          <h3 id="chapter-revision-notes-title">修正意见</h3>
        </div>
        {reviewIssues.length > 0 ? (
          <ul aria-label="修正意见标签" className="chapter-issue-tag-list">
            {reviewIssues.map((issue, index) => (
              <li key={`${issue.title}-${index}`}>
                <span
                  aria-label={`${issue.resolved ? "已满足" : "未满足"}：${issue.title}`}
                  className={`chapter-issue-tag ${issue.resolved ? "chapter-issue-tag--resolved" : "chapter-issue-tag--unmet"}`}
                >
                  {issue.resolved ? `${issue.title}（已修正）` : issue.title}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="chapter-action-muted">暂无修正意见。</p>
        )}
        {canRepair ? (
          <form
            className="chapter-action-repair-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (!repairNoteTrimmed && !hasUnresolvedIssue) {
                return;
              }
              onAction("repair", repairNoteTrimmed ? { reviewerNote: repairNoteTrimmed } : {});
            }}
          >
            <label className="chapter-manual-opinion-field">
              人工意见
              <textarea
                disabled={busy}
                placeholder="写下希望系统重点修复的问题"
                value={repairNote}
                onChange={(event) => setRepairNote(event.target.value)}
              />
            </label>
            <button
              className="workbench-action-button chapter-repair-button"
              disabled={busy || (!repairNoteTrimmed && !hasUnresolvedIssue)}
              type="submit"
            >
              {actionBusy === "repair" ? (
                <AiWaitingIndicator label={actionProgressLabel ?? "修复中..."} variant="inline" />
              ) : (
                <>
                  <WandSparkles aria-hidden="true" size={16} />
                  {repairButtonIdleLabel}
                </>
              )}
            </button>
          </form>
        ) : null}
      </section>

      {importantChanges.length > 0 ? (
        <section className="chapter-action-section chapter-action-section--changes" aria-labelledby="chapter-important-changes-title">
          <div className="chapter-action-section__head">
            <AlertTriangle aria-hidden="true" size={18} />
            <h3 id="chapter-important-changes-title">重要变动</h3>
          </div>
          <dl className="chapter-important-change-list" aria-label="重要变动">
            {importantChanges.map((change, index) => (
              <div className={change.major ? "is-major" : undefined} key={`${change.target}-${index}`}>
                <dt>{change.target || `变化 ${index + 1}`}</dt>
                <dd>{change.detail || "待写入"}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}
    </section>
  );
}

function chapterStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    planned: "已规划",
    running: "生成中",
    awaiting_review: "待审核",
    needs_revision: "需修订",
    accepted: "已批准",
  };
  return labels[status] ?? "未知状态";
}
