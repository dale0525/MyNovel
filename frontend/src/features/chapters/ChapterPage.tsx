import { useEffect, useState } from "react";

import {
  ChapterReviewActions,
  type ChapterReviewAction,
} from "@/features/chapters/ChapterReviewActions";
import {
  ImpactPanel,
  type ImpactItem,
  ProjectIdentityBar,
} from "@/components/guidance/GuidedPanels";
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
    setActionState({ status: "submitting", action, message: null });
    try {
      const payload = await postJson<unknown>(`/api/chapters/${chapterId}/${action}`, body);
      const parsed = parseChapterResponse(payload);
      if (!parsed) {
        throw new Error("章节数据格式无效。");
      }
      setState({ status: "ready", data: parsed, error: null });
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
    <section className="workbench-page chapter-page" aria-label={chapter.title}>
      <ProjectIdentityBar
        eyebrow="Chapter Review"
        title={chapter.title}
        meta={[
          { label: "项目", value: book.title },
          { label: "章节", value: `第 ${chapter.number} 章` },
          { label: "状态", value: chapterStatusLabel(chapter.status) },
          { label: "Canon", value: latestCanon ? `v${latestCanon.version}` : "未连接可信设定" },
        ]}
        actions={<p className="lede">{chapter.summary || "本章尚未形成摘要。"}</p>}
      />

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
          <ImpactPanel title="章节结果" items={chapterResultItems(chapter)} />
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
            highRisk={hasHighRiskAudit(chapter)}
            impactItems={chapterImpactItems(chapter)}
            majorChange={hasMajorStateChange(chapter.stateDelta)}
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

function chapterResultItems(chapter: ChapterDetailPayload): ImpactItem[] {
  const stateChanges = stateDeltaChanges(chapter.stateDelta);
  const auditIssues = auditReportIssues(chapter.auditReport);
  const riskLevel = String(chapter.auditReport.risk_level ?? "未标注");
  const highRisk = hasHighRiskAudit(chapter);
  const majorChange = hasMajorStateChange(chapter.stateDelta);

  return [
    {
      label: "正文",
      value: chapter.finalText || chapter.revisedText || chapter.draftText ? "已生成" : "未生成",
      tone: chapter.finalText || chapter.revisedText || chapter.draftText ? "good" : "warning",
    },
    {
      label: "审计",
      value: `${riskLevel} · ${auditIssues.length} 项`,
      tone: highRisk ? "danger" : "neutral",
    },
    {
      label: "状态变化",
      value: `${stateChanges.length} 项`,
      tone: stateChanges.length > 0 ? "warning" : "neutral",
    },
    {
      label: "重大变化",
      value: majorChange ? "需要确认" : "无",
      tone: majorChange ? "danger" : "neutral",
    },
  ];
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

function hasHighRiskAudit(chapter: ChapterDetailPayload): boolean {
  if (chapter.auditReport.risk_level === "high") {
    return true;
  }
  return auditReportIssues(chapter.auditReport).some(
    (issue) => issue.severity === "high" && issue.resolved !== true,
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
  if (change.major === true || change.severity === "major") {
    return true;
  }

  const impact = typeof change.impact === "string" ? change.impact.toLowerCase() : "";
  if (["major", "critical", "high"].includes(impact)) {
    return true;
  }

  const majorTerms = ["角色死亡", "人物死亡", "死亡", "牺牲", "退场", "核心设定", "改写设定"];
  const changeText = [change.target, change.change]
    .filter((value) => typeof value === "string")
    .join(" ");
  return majorTerms.some((term) => changeText.includes(term));
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
