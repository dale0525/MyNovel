import { useEffect, useState } from "react";

import { AiWaitingIndicator } from "@/components/feedback/AiWaitingIndicator";
import type { ChapterDetailPayload } from "@/lib/types";

export type ChapterReviewAction =
  | "run"
  | "request-revision"
  | "repair"
  | "edit"
  | "approve";

type ChapterReviewActionsProps = {
  chapter: ChapterDetailPayload;
  actionBusy: ChapterReviewAction | null;
  onAction: (action: ChapterReviewAction, body: Record<string, unknown>) => void;
};

export function ChapterReviewActions({ chapter, actionBusy, onAction }: ChapterReviewActionsProps) {
  const [manualText, setManualText] = useState(chapter.revisedText || chapter.draftText);
  const [manualNote, setManualNote] = useState("");
  const [repairNote, setRepairNote] = useState("");
  const [decisionNote, setDecisionNote] = useState("");
  const [allowMajorChanges, setAllowMajorChanges] = useState(false);

  useEffect(() => {
    setManualText(chapter.revisedText || chapter.draftText);
  }, [chapter.draftText, chapter.revisedText]);

  return (
    <section className="chapter-review-actions workbench-panel" aria-labelledby="chapter-actions-title">
      <div>
        <p className="eyebrow">Human Review</p>
        <h2 id="chapter-actions-title">审核动作</h2>
      </div>

      {chapter.status === "planned" || chapter.status === "needs_revision" ? (
        <button
          className="workbench-action-button"
          disabled={actionBusy !== null}
          type="button"
          onClick={() => onAction("run", {})}
        >
          {actionBusy === "run" ? (
            <AiWaitingIndicator label="提交运行中..." variant="inline" />
          ) : (
            "运行本章"
          )}
        </button>
      ) : null}

      <form
        className="chapter-action-form"
        onSubmit={(event) => {
          event.preventDefault();
          onAction("edit", { revisedText: manualText, reviewerNote: manualNote });
        }}
      >
        <label>
          手动修正文
          <textarea value={manualText} onChange={(event) => setManualText(event.target.value)} />
        </label>
        <label>
          修正说明
          <input value={manualNote} onChange={(event) => setManualNote(event.target.value)} />
        </label>
        <button className="workbench-secondary-button" disabled={actionBusy !== null} type="submit">
          {actionBusy === "edit" ? "保存中..." : "保存手动修正"}
        </button>
      </form>

      <form
        className="chapter-action-form"
        onSubmit={(event) => {
          event.preventDefault();
          onAction("repair", { reviewerNote: repairNote });
        }}
      >
        <label>
          修复要求
          <textarea
            value={repairNote}
            onChange={(event) => setRepairNote(event.target.value)}
            placeholder="说明希望 AI 重点修复的问题"
          />
        </label>
        <button className="workbench-secondary-button" disabled={actionBusy !== null} type="submit">
          {actionBusy === "repair" ? (
            <AiWaitingIndicator label="提交修复中..." variant="inline" />
          ) : (
            "让 AI 修复"
          )}
        </button>
      </form>

      <form
        className="chapter-action-form"
        onSubmit={(event) => {
          event.preventDefault();
          onAction("request-revision", { reviewerNote: decisionNote });
        }}
      >
        <label>
          决策说明
          <input value={decisionNote} onChange={(event) => setDecisionNote(event.target.value)} />
        </label>
        <button className="workbench-secondary-button" disabled={actionBusy !== null} type="submit">
          {actionBusy === "request-revision" ? "退回中..." : "退回修订"}
        </button>
      </form>

      <label className="chapter-major-change-toggle">
        <input
          checked={allowMajorChanges}
          type="checkbox"
          onChange={(event) => setAllowMajorChanges(event.target.checked)}
        />
        允许写入重大状态变化
      </label>
      <button
        className="workbench-action-button"
        disabled={actionBusy !== null}
        type="button"
        onClick={() =>
          onAction("approve", {
            reviewerNote: decisionNote,
            allowMajorChanges,
          })
        }
      >
        {actionBusy === "approve" ? "批准中..." : "批准章节"}
      </button>

      <a className="workbench-secondary-link" href={`/api/chapters/${chapter.id ?? 0}/export.txt`}>
        导出正文
      </a>
    </section>
  );
}
