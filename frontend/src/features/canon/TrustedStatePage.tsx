import { ChevronDown, Lock, Unlock } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { AiWaitingIndicator } from "@/components/feedback/AiWaitingIndicator";
import { ProjectIdentityBar } from "@/components/guidance/GuidedPanels";
import { getJson, isAbortError, postJson, postJsonLineStream } from "@/lib/api";
import { navigateTo } from "@/lib/navigation";
import { streamPreviewLine } from "@/lib/streaming";
import type { CanonSectionPayload, TrustedStateResponse } from "@/lib/types";

type TrustedState =
  | { status: "loading"; data: null; error: null }
  | { status: "ready"; data: TrustedStateResponse; error: null }
  | { status: "error"; data: null; error: string };

type TrustedStatePageProps = {
  bookId: number;
};

type CanonAction = "global-revise" | "section-revise" | "lock" | "next";

type ActionState =
  | { status: "idle"; message: null; action: null; targetSection: null }
  | {
      status: "submitting";
      message: null;
      action: CanonAction;
      targetSection: string | null;
      streamSnippets: string[];
    }
  | { status: "success"; message: string; action: CanonAction; targetSection: string | null }
  | { status: "error"; message: string; action: CanonAction; targetSection: string | null };

const idleAction: ActionState = {
  status: "idle",
  message: null,
  action: null,
  targetSection: null,
};

type CanonRevisionStreamEvent = {
  type: "started" | "chunk" | "applying" | "done" | "failed";
  text?: string;
  message?: string;
  state?: unknown;
};

const hiddenCanonSectionKeys = new Set(["state_history"]);

export function TrustedStatePage({ bookId }: TrustedStatePageProps) {
  const [state, setState] = useState<TrustedState>({
    status: "loading",
    data: null,
    error: null,
  });
  const [globalInstruction, setGlobalInstruction] = useState("");
  const [sectionInstructions, setSectionInstructions] = useState<Record<string, string>>({});
  const [expandedSections, setExpandedSections] = useState<Set<string>>(() => new Set());
  const [actionState, setActionState] = useState<ActionState>(idleAction);

  const loadTrustedState = useCallback(
    async (signal?: AbortSignal, options: { quiet?: boolean; query?: string } = {}) => {
      if (!options.quiet) {
        setState({ status: "loading", data: null, error: null });
      }
      const query = options.query ?? window.location.search;
      try {
        const payload = await getJson<unknown>(`/api/books/${bookId}/state${query}`, { signal });
        const parsed = parseTrustedState(payload);
        if (parsed) {
          setState({ status: "ready", data: parsed, error: null });
          return;
        }
        setState({ status: "error", data: null, error: "设定数据格式无效。" });
      } catch (error: unknown) {
        if (isAbortError(error)) {
          return;
        }
        setState({
          status: "error",
          data: null,
          error: errorMessage(error, "设定加载失败。"),
        });
      }
    },
    [bookId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadTrustedState(controller.signal);
    return () => {
      controller.abort();
    };
  }, [loadTrustedState]);

  useEffect(() => {
    if (state.status !== "ready" || state.data.selectedRevision?.status !== "running") {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      void loadTrustedState(undefined, { quiet: true });
    }, 2500);
    return () => {
      window.clearTimeout(timer);
    };
  }, [loadTrustedState, state]);

  const globalTarget = useMemo(() => {
    if (state.status !== "ready") {
      return null;
    }
    return revisionTargetSection(state.data.canonSections, state.data.readiness.missingSections);
  }, [state]);

  async function reviseAllCanon(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.status !== "ready" || actionState.status === "submitting" || !globalTarget) {
      return;
    }
    const trimmedInstruction = globalInstruction.trim();
    if (trimmedInstruction.length === 0) {
      await requestCanonAutoCompletion("global-revise", globalTarget.key);
      return;
    }
    await requestCanonRevision(globalTarget.key, trimmedInstruction, "global-revise");
  }

  async function reviseSection(section: CanonSectionPayload, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedInstruction = (sectionInstructions[section.key] ?? "").trim();
    if (
      actionState.status === "submitting" ||
      section.locked ||
      !section.editable ||
      trimmedInstruction.length === 0
    ) {
      return;
    }
    await requestCanonRevision(section.key, trimmedInstruction, "section-revise");
  }

  async function requestCanonAutoCompletion(action: "global-revise", targetSection: string) {
    await requestCanonRevisionStream({ autoComplete: true }, action, targetSection);
  }

  async function requestCanonRevision(
    targetSection: string,
    revisionInstruction: string,
    action: "global-revise" | "section-revise",
  ) {
    await requestCanonRevisionStream(
      { targetSection, instruction: revisionInstruction },
      action,
      targetSection,
    );
  }

  async function requestCanonRevisionStream(
    body: Record<string, unknown>,
    action: "global-revise" | "section-revise",
    targetSection: string,
  ) {
    let completed = false;
    setActionState({ status: "submitting", message: null, action, targetSection, streamSnippets: [] });
    try {
      await postJsonLineStream<CanonRevisionStreamEvent>(
        `/api/books/${bookId}/canon-proposals/revise-stream`,
        body,
        async (event) => {
          if (event.type === "chunk") {
            appendStreamSnippet(action, targetSection, event.text ?? "");
            return;
          }
          if (event.type === "applying") {
            appendStreamSnippet(action, targetSection, event.message ?? "");
            return;
          }
          if (event.type === "failed") {
            throw new Error(event.message || "AI 修改失败。");
          }
          if (event.type !== "done") {
            return;
          }
          completed = true;
          const parsed = parseTrustedState(event.state);
          if (parsed) {
            setState({ status: "ready", data: parsed, error: null });
          } else {
            await loadTrustedState(undefined, { quiet: true, query: "" });
          }
          setActionState({
            status: "success",
            message: event.message || "AI 修改已写入设定。",
            action,
            targetSection,
          });
        },
      );
      if (!completed) {
        throw new Error("AI 修改没有返回结果。");
      }
    } catch (error) {
      setActionState({
        status: "error",
        message: errorMessage(error, "提交修改失败。"),
        action,
        targetSection,
      });
    }
  }

  function appendStreamSnippet(
    action: "global-revise" | "section-revise",
    targetSection: string,
    text: string,
  ) {
    const snippet = streamPreviewLine(text);
    if (!snippet) {
      return;
    }
    setActionState((current) => {
      if (
        current.status !== "submitting" ||
        current.action !== action ||
        current.targetSection !== targetSection
      ) {
        return current;
      }
      return {
        ...current,
        streamSnippets: [...current.streamSnippets, snippet].slice(-2),
      };
    });
  }

  async function toggleSectionLock(section: CanonSectionPayload) {
    if (state.status !== "ready" || actionState.status === "submitting") {
      return;
    }
    const nextLocked = !section.locked;
    setActionState({
      status: "submitting",
      message: null,
      action: "lock",
      targetSection: section.key,
      streamSnippets: [],
    });
    try {
      const payload = await postJson<unknown>(`/api/books/${bookId}/canon-proposals/lock`, {
        section: section.key,
        locked: nextLocked,
      });
      const parsed = parseTrustedState(payload);
      if (parsed) {
        setState({ status: "ready", data: parsed, error: null });
      } else {
        await loadTrustedState(undefined, { quiet: true });
      }
      setActionState({
        status: "success",
        message: nextLocked ? "已锁定该设定。" : "已解锁该设定。",
        action: "lock",
        targetSection: section.key,
      });
    } catch (error) {
      setActionState({
        status: "error",
        message: errorMessage(error, "锁定状态修改失败。"),
        action: "lock",
        targetSection: section.key,
      });
    }
  }

  async function lockAndContinue() {
    if (state.status !== "ready" || actionState.status === "submitting") {
      return;
    }
    if (!state.data.readiness.complete) {
      setActionState({
        status: "error",
        message: "必须先修正不满足硬性设定要求的内容，才能下一步。",
        action: "next",
        targetSection: null,
      });
      return;
    }
    setActionState({
      status: "submitting",
      message: null,
      action: "next",
      targetSection: null,
      streamSnippets: [],
    });
    try {
      const response = await postJson<{ redirectTo?: string }>(`/api/books/${bookId}/state/lock`, {});
      setActionState({ status: "success", message: "已锁定全部设定。", action: "next", targetSection: null });
      navigateTo(response.redirectTo ?? `/books/${bookId}`);
    } catch (error) {
      setActionState({
        status: "error",
        message: errorMessage(error, "锁定设定失败。"),
        action: "next",
        targetSection: null,
      });
    }
  }

  function updateSectionInstruction(sectionKey: string, value: string) {
    setSectionInstructions((current) => ({ ...current, [sectionKey]: value }));
  }

  function toggleExpandedSection(sectionKey: string) {
    setExpandedSections((current) => {
      const next = new Set(current);
      if (next.has(sectionKey)) {
        next.delete(sectionKey);
      } else {
        next.add(sectionKey);
      }
      return next;
    });
  }

  if (state.status === "loading") {
    return (
      <section className="workbench-page canon-page" aria-label="设定">
        <div className="workbench-panel" role="status">
          正在加载设定...
        </div>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="workbench-page canon-page" aria-labelledby="trusted-state-title">
        <div className="workbench-panel workbench-panel--alert" role="alert">
          <h1 id="trusted-state-title">设定加载失败</h1>
          <p>{state.error}</p>
          <a className="workbench-action-button" href={`/books/${bookId}`}>
            返回项目
          </a>
        </div>
      </section>
    );
  }

  const { book, canonSections, readiness, selectedRevision } = state.data;
  const visibleCanonSections = canonSections.filter((section) => !hiddenCanonSectionKeys.has(section.key));
  const submittingAction = actionState.status === "submitting" ? actionState.action : null;

  return (
    <section className="workbench-page canon-page" aria-label="设定">
      <ProjectIdentityBar
        eyebrow="项目身份"
        title="设定"
        meta={[
          { label: "作品", value: book.title },
          { label: "类型", value: book.genre || "未填写" },
          { label: "状态", value: statusLabel(book.status) },
        ]}
      />

      <main className="canon-centered-flow">
        <section className="workbench-panel canon-global-revision" aria-label="整体修改">
          <form
            className="canon-revision-form canon-global-revision__form"
            onSubmit={(event) => void reviseAllCanon(event)}
          >
            <label className="canon-revision-label" htmlFor="canon-global-instruction">
              全部设定修改意见
            </label>
            <div className="canon-revision-control">
              <textarea
                id="canon-global-instruction"
                value={globalInstruction}
                onChange={(event) => setGlobalInstruction(event.target.value)}
                placeholder="留空时，AI 会优先补齐缺口"
              />
              <div className="canon-revision-control__actions">
                <button
                  className="workbench-action-button canon-global-revision__button"
                  disabled={submittingAction !== null || !globalTarget}
                  type="submit"
                >
                  {submittingAction === "global-revise" ? (
                    <AiWaitingIndicator label="提交修订中..." variant="inline" />
                  ) : (
                    "让 AI 修改全部设定"
                  )}
                </button>
                <InlineActionFeedback
                  actionState={actionState}
                  action="global-revise"
                  targetSection={globalTarget?.key ?? null}
                />
              </div>
            </div>
          </form>
        </section>

        <section className="canon-section-rows" aria-label="设定列表">
          {visibleCanonSections.map((section) => (
            <CanonSectionRow
              actionState={actionState}
              expanded={expandedSections.has(section.key)}
              instruction={sectionInstructions[section.key] ?? ""}
              key={section.key}
              readiness={readiness}
              revisionStatus={selectedRevision?.targetSection === section.key ? selectedRevision.status : null}
              section={section}
              onInstructionChange={updateSectionInstruction}
              onLockToggle={() => void toggleSectionLock(section)}
              onRevisionSubmit={(event) => void reviseSection(section, event)}
              onToggle={() => toggleExpandedSection(section.key)}
            />
          ))}
        </section>

        <section className="workbench-panel canon-next-step" aria-label="下一步">
          <div className="canon-next-step__status" aria-hidden="true">
            <span className={readiness.complete ? "canon-step-light is-ready" : "canon-step-light"} />
            <strong>{readiness.complete ? "可以进入下一步" : `${readiness.messages.length || readiness.missingSections.length} 处待修正`}</strong>
          </div>
          <div className="canon-next-step__actions">
            <button
              className="workbench-action-button canon-next-step__button"
              disabled={submittingAction !== null}
              onClick={() => void lockAndContinue()}
              type="button"
            >
              {submittingAction === "next" ? <AiWaitingIndicator label="锁定中..." variant="inline" /> : "下一步"}
            </button>
            <InlineActionFeedback actionState={actionState} action="next" targetSection={null} />
          </div>
        </section>
      </main>
    </section>
  );
}

function InlineActionFeedback({
  actionState,
  action,
  targetSection,
}: {
  actionState: ActionState;
  action: CanonAction;
  targetSection: string | null;
}) {
  if (
    actionState.status === "submitting" &&
    actionState.action === action &&
    actionState.targetSection === targetSection &&
    actionState.streamSnippets.length > 0
  ) {
    return (
      <div className="canon-stream-feedback" role="status">
        {actionState.streamSnippets.map((snippet, index) => (
          <span key={`${snippet}-${index}`}>{snippet}</span>
        ))}
      </div>
    );
  }
  if (
    (actionState.status !== "success" && actionState.status !== "error") ||
    actionState.action !== action ||
    actionState.targetSection !== targetSection
  ) {
    return null;
  }
  if (actionState.status === "success") {
    return (
      <p className="canon-inline-feedback" role="status">
        {actionState.message}
      </p>
    );
  }
  return (
    <p className="canon-inline-feedback is-error" role="alert">
      {actionState.message}
    </p>
  );
}

function CanonSectionRow({
  actionState,
  expanded,
  instruction,
  readiness,
  revisionStatus,
  section,
  onInstructionChange,
  onLockToggle,
  onRevisionSubmit,
  onToggle,
}: {
  actionState: ActionState;
  expanded: boolean;
  instruction: string;
  readiness: TrustedStateResponse["readiness"];
  revisionStatus: string | null;
  section: CanonSectionPayload;
  onInstructionChange: (sectionKey: string, value: string) => void;
  onLockToggle: () => void;
  onRevisionSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onToggle: () => void;
}) {
  const summary = sectionSummary(section, readiness);
  const sectionLabel = sectionDisplayName(section.key, section.label);
  const sectionStatus = sectionStatusLabel(section, readiness);
  const missingHardRequirement = readiness.missingSections.includes(section.key);
  const isSubmitting = actionState.status === "submitting";
  const sectionSubmitting =
    isSubmitting && actionState.action === "section-revise" && actionState.targetSection === section.key;
  const lockSubmitting = isSubmitting && actionState.action === "lock" && actionState.targetSection === section.key;
  const revisionDisabled = isSubmitting || section.locked || !section.editable || instruction.trim().length === 0;
  const detailsId = `canon-section-${section.key}`;
  const instructionId = `canon-section-${section.key}-instruction`;

  return (
    <article className={expanded ? "canon-section-row is-expanded" : "canon-section-row"}>
      <header className="canon-section-row__header">
        <button
          aria-controls={detailsId}
          aria-expanded={expanded}
          aria-label={summary}
          className="canon-section-row__summary"
          onClick={onToggle}
          type="button"
        >
          <span className="canon-section-row__headline" aria-hidden="true">
            <strong>{sectionLabel}</strong>
            <span>{sectionItemCount(section.content)} 条</span>
            <span>{sectionStatus}</span>
          </span>
          <ChevronDown aria-hidden="true" className="canon-section-row__chevron" size={20} />
        </button>
        {!missingHardRequirement ? (
          <div className="canon-section-row__actions">
            <button
              className={section.locked ? "canon-lock-button is-locked" : "canon-lock-button"}
              disabled={isSubmitting}
              onClick={onLockToggle}
              type="button"
            >
              {section.locked ? <Unlock aria-hidden="true" size={18} /> : <Lock aria-hidden="true" size={18} />}
              {lockSubmitting ? "处理中..." : `${section.locked ? "解锁" : "锁定"}${sectionLabel}`}
            </button>
            <InlineActionFeedback actionState={actionState} action="lock" targetSection={section.key} />
          </div>
        ) : null}
      </header>

      {expanded ? (
        <div className="canon-section-row__details" id={detailsId}>
          <CanonSectionContent section={section} />
          <form className="canon-revision-form canon-section-row__form" onSubmit={onRevisionSubmit}>
            <label className="canon-revision-label" htmlFor={instructionId}>
              {sectionLabel}修改意见
            </label>
            <div className="canon-revision-control">
              <textarea
                disabled={isSubmitting || section.locked || !section.editable}
                id={instructionId}
                value={instruction}
                onChange={(event) => onInstructionChange(section.key, event.target.value)}
                placeholder={`${section.locked ? "解锁后" : "填写后"}让 AI 修改${sectionLabel}`}
              />
              <div className="canon-revision-control__actions">
                <button className="workbench-action-button" disabled={revisionDisabled} type="submit">
                  {sectionSubmitting ? (
                    <AiWaitingIndicator label="提交修订中..." variant="inline" />
                  ) : (
                    `让 AI 修改${sectionLabel}`
                  )}
                </button>
                <InlineActionFeedback
                  actionState={actionState}
                  action="section-revise"
                  targetSection={section.key}
                />
                <SectionRevisionFeedback status={revisionStatus} />
              </div>
            </div>
          </form>
        </div>
      ) : null}
    </article>
  );
}

function SectionRevisionFeedback({ status }: { status: string | null }) {
  if (status === "running") {
    return (
      <AiWaitingIndicator
        detail="结果返回后会自动刷新到这里。"
        label="修订生成中"
        variant="message"
      />
    );
  }
  if (status === "failed") {
    return (
      <p className="canon-inline-feedback is-error" role="alert">
        修订生成失败
      </p>
    );
  }
  return null;
}

function CanonSectionContent({ section }: { section: CanonSectionPayload }) {
  const lines = canonValueLines(section.content);
  if (!lines.length) {
    return <p className="canon-empty-content">暂无内容。</p>;
  }
  return (
    <ul className="value-list canon-full-content">
      {lines.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
    </ul>
  );
}

function revisionTargetSection(
  sections: CanonSectionPayload[],
  missingSections: string[],
): CanonSectionPayload | null {
  const missingTarget = missingSections
    .map((sectionKey) => sections.find((section) => section.key === sectionKey) ?? null)
    .find((section) => section !== null && section.editable && !section.locked);
  if (missingTarget) {
    return missingTarget;
  }
  return sections.find((section) => section.editable && !section.locked) ?? null;
}

function sectionSummary(section: CanonSectionPayload, readiness: TrustedStateResponse["readiness"]): string {
  return `${sectionDisplayName(section.key, section.label)} ${sectionItemCount(section.content)} 条 ${sectionStatusLabel(section, readiness)}`;
}

function sectionStatusLabel(section: CanonSectionPayload, readiness: TrustedStateResponse["readiness"]): string {
  if (section.locked) {
    return "已锁定";
  }
  if (!section.editable) {
    return "不可修订";
  }
  if (readiness.missingSections.includes(section.key)) {
    return "待修订";
  }
  return "已满足";
}

function sectionItemCount(content: unknown): number {
  if (Array.isArray(content)) {
    return content.length;
  }
  if (isRecord(content)) {
    return Object.keys(content).length;
  }
  if (content === null || content === undefined || content === "") {
    return 0;
  }
  return 1;
}

function parseTrustedState(payload: unknown): TrustedStateResponse | null {
  if (!isRecord(payload) || !isRecord(payload.book)) {
    return null;
  }
  if (!Array.isArray(payload.canonSections) || !Array.isArray(payload.pendingRevisions)) {
    return null;
  }
  return payload as TrustedStateResponse;
}

function canonValueLines(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.flatMap((item) => canonValueLines(item)).filter((item) => item.length > 0);
  }
  if (isRecord(value)) {
    const values = Object.values(value);
    if (!values.length) {
      return [];
    }
    if (values.every((item) => !Array.isArray(item) && !isRecord(item))) {
      return values.map(shortValue).filter(Boolean);
    }
    return values.flatMap((item) => canonValueLines(item)).filter((item) => item.length > 0);
  }
  const valueText = shortValue(value);
  return valueText ? [valueText] : [];
}

function shortValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number") {
    return String(value);
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (value === null || value === undefined) {
    return "";
  }
  if (Array.isArray(value)) {
    return value.map(shortValue).filter(Boolean).join("；");
  }
  if (isRecord(value)) {
    return Object.values(value).map(shortValue).filter(Boolean).join("；");
  }
  return String(value);
}

function sectionDisplayName(sectionKey: string, fallback?: string): string {
  const labels: Record<string, string> = {
    accepted_chapters: "已接纳章节",
    characters: "人物",
    conflicts: "冲突",
    factions: "势力",
    locations: "地点",
    resources: "资源",
    state_history: "状态历史",
    themes: "主题",
    timeline: "时间线",
    world_rules: "世界规则",
  };
  return fallback || labels[sectionKey] || "未命名设定";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    canon_locked: "设定已锁定",
    draft: "草稿",
    paused: "暂停",
    producing: "生产中",
  };
  return labels[status] ?? "未知状态";
}

function errorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof Error) || !error.message) {
    return fallback;
  }
  const knownMessages: Record<string, string> = {
    "Revision is still running.": "修订仍在生成中。",
  };
  return knownMessages[error.message] ?? (/[A-Za-z_]/.test(error.message) ? fallback : error.message);
}
