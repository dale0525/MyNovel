import { useEffect, useState } from "react";

import { AiWaitingIndicator } from "@/components/feedback/AiWaitingIndicator";
import {
  AdvancedDisclosure,
  ImpactPanel,
  type ImpactItem,
} from "@/components/guidance/GuidedPanels";
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
  highRisk: boolean;
  impactItems: ImpactItem[];
  majorChange: boolean;
  onAction: (action: ChapterReviewAction, body: Record<string, unknown>) => void;
};

export function ChapterReviewActions({
  chapter,
  actionBusy,
  highRisk,
  impactItems,
  majorChange,
  onAction,
}: ChapterReviewActionsProps) {
  const [manualText, setManualText] = useState(chapter.revisedText || chapter.draftText);
  const [manualNote, setManualNote] = useState("");
  const [repairNote, setRepairNote] = useState("");
  const [decisionNote, setDecisionNote] = useState("");
  const [allowMajorChanges, setAllowMajorChanges] = useState(false);
  const canReviewStage = chapter.status === "awaiting_review" || chapter.status === "needs_revision";
  const repairNoteTrimmed = repairNote.trim();
  const stateDeltaSignature = JSON.stringify(chapter.stateDelta);

  useEffect(() => {
    setManualText(chapter.revisedText || chapter.draftText);
  }, [chapter.draftText, chapter.revisedText]);

  useEffect(() => {
    setAllowMajorChanges(false);
  }, [chapter.id, chapter.status, majorChange, chapter.updatedAt, stateDeltaSignature]);

  const busy = actionBusy !== null;
  const approveDisabled = busy || (majorChange && !allowMajorChanges);

  return (
    <section className="chapter-review-actions guided-decision-panel workbench-panel" aria-labelledby="chapter-actions-title">
      <div>
        <p className="eyebrow">Human Review</p>
        <h2 id="chapter-actions-title">审核决策</h2>
      </div>

      {chapter.status === "planned" || chapter.status === "needs_revision" ? (
        <button
          className="workbench-action-button"
          disabled={busy}
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

      {chapter.status === "running" ? (
        <AiWaitingIndicator
          detail="AI 正在执行章节规划、上下文检索、草稿、修订和审计流水线。"
          label="章节生成中"
        />
      ) : null}

      {chapter.status === "awaiting_review" ? (
        <>
          <ImpactPanel title="将写入可信设定" items={impactItems} />

          {highRisk ? (
            <form
              className="chapter-action-form"
              onSubmit={(event) => {
                event.preventDefault();
                if (!repairNoteTrimmed) {
                  return;
                }
                onAction("repair", { reviewerNote: repairNoteTrimmed });
              }}
            >
              <label>
                修订意图
                <textarea
                  value={repairNote}
                  onChange={(event) => setRepairNote(event.target.value)}
                  placeholder="说明希望 AI 重点修订的问题"
                />
              </label>
              <button className="workbench-action-button" disabled={busy || !repairNoteTrimmed} type="submit">
                {actionBusy === "repair" ? (
                  <AiWaitingIndicator label="提交修复中..." variant="inline" />
                ) : (
                  "让 AI 修订"
                )}
              </button>
            </form>
          ) : (
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
                onClick={() =>
                  onAction("approve", {
                    reviewerNote: decisionNote,
                    allowMajorChanges,
                  })
                }
              >
                {actionBusy === "approve" ? "批准中..." : "批准并写入可信设定"}
              </button>
            </>
          )}

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
            <button className="workbench-secondary-button" disabled={busy} type="submit">
              {actionBusy === "request-revision" ? "退回中..." : "退回修订"}
            </button>
          </form>
        </>
      ) : null}

      <AdvancedDisclosure title="高级审核工具">
        {canReviewStage ? (
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
            <button className="workbench-secondary-button" disabled={busy} type="submit">
              {actionBusy === "edit" ? "保存中..." : "保存手动修正"}
            </button>
          </form>
        ) : null}

        {canReviewStage && !highRisk ? (
          <form
            className="chapter-action-form"
            onSubmit={(event) => {
              event.preventDefault();
              onAction("repair", { reviewerNote: repairNoteTrimmed });
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
            <button className="workbench-secondary-button" disabled={busy} type="submit">
              {actionBusy === "repair" ? (
                <AiWaitingIndicator label="提交修复中..." variant="inline" />
              ) : (
                "让 AI 修复"
              )}
            </button>
          </form>
        ) : null}

        {chapter.id !== null ? (
          <a className="workbench-secondary-link" href={`/api/chapters/${chapter.id}/export.txt`}>
            导出正文
          </a>
        ) : null}
      </AdvancedDisclosure>
    </section>
  );
}
