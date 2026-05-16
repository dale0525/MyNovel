import { useEffect, useState } from "react";

import { AiWaitingIndicator } from "@/components/feedback/AiWaitingIndicator";
import {
  AdvancedDisclosure,
  ImpactPanel,
  type ImpactItem,
  ProjectIdentityBar,
} from "@/components/guidance/GuidedPanels";
import { getJson, isAbortError, postJson } from "@/lib/api";
import { navigateTo } from "@/lib/navigation";
import type {
  CanonProposalRevisionPayload,
  CanonSectionPayload,
  TrustedStateResponse,
} from "@/lib/types";

type TrustedState =
  | { status: "loading"; data: null; error: null }
  | { status: "ready"; data: TrustedStateResponse; error: null }
  | { status: "error"; data: null; error: string };

type TrustedStatePageProps = {
  bookId: number;
};

type CanonAction = "apply" | "discard" | "revise" | "auto-complete";

type ActionState =
  | { status: "idle"; message: null; action: null }
  | { status: "submitting"; message: null; action: CanonAction }
  | { status: "success"; message: string; action: null }
  | { status: "error"; message: string; action: null };

export function TrustedStatePage({ bookId }: TrustedStatePageProps) {
  const [state, setState] = useState<TrustedState>({
    status: "loading",
    data: null,
    error: null,
  });
  const [selectedSectionKey, setSelectedSectionKey] = useState("");
  const [instruction, setInstruction] = useState("");
  const [actionState, setActionState] = useState<ActionState>({
    status: "idle",
    message: null,
    action: null,
  });

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const query = window.location.search;
    setState({ status: "loading", data: null, error: null });

    getJson<unknown>(`/api/books/${bookId}/state${query}`, { signal: controller.signal })
      .then((payload) => {
        const parsed = parseTrustedState(payload);
        if (!cancelled) {
          if (parsed) {
            setState({ status: "ready", data: parsed, error: null });
            const firstEditable = parsed.canonSections.find(
              (section) => section.editable && !section.locked,
            );
            setSelectedSectionKey(firstEditable?.key ?? parsed.canonSections[0]?.key ?? "");
          } else {
            setState({ status: "error", data: null, error: "可信设定数据格式无效。" });
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
            error: error instanceof Error ? error.message : "可信设定加载失败。",
          });
        }
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [bookId]);

  async function applyRevision() {
    const revisionId = state.status === "ready" ? state.data.selectedRevision?.id : null;
    if (typeof revisionId !== "number") {
      return;
    }
    setActionState({ status: "submitting", message: null, action: "apply" });
    try {
      await postJson(`/api/books/${bookId}/canon-proposals/apply`, { revisionId });
      setActionState({ status: "success", message: "已应用修订。", action: null });
      navigateTo(`/books/${bookId}/state`);
    } catch (error) {
      setActionState({
        status: "error",
        message: errorMessage(error, "应用修订失败。"),
        action: null,
      });
    }
  }

  async function discardRevision() {
    const revisionId = state.status === "ready" ? state.data.selectedRevision?.id : null;
    if (typeof revisionId !== "number") {
      return;
    }
    setActionState({ status: "submitting", message: null, action: "discard" });
    try {
      await postJson(`/api/books/${bookId}/canon-proposals/discard`, { revisionId });
      setActionState({ status: "success", message: "已放弃修订。", action: null });
      navigateTo(`/books/${bookId}/state`);
    } catch (error) {
      setActionState({
        status: "error",
        message: errorMessage(error, "放弃修订失败。"),
        action: null,
      });
    }
  }

  async function reviseState(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const selectedSection =
      state.status === "ready"
        ? state.data.canonSections.find((section) => section.key === selectedSectionKey)
        : null;
    const trimmedInstruction = instruction.trim();
    if (
      actionState.status === "submitting" ||
      !selectedSection ||
      selectedSection.locked ||
      !selectedSection.editable ||
      trimmedInstruction.length === 0
    ) {
      return;
    }
    await requestCanonRevision(selectedSection.key, trimmedInstruction, "revise");
  }

  async function autoCompleteCanon() {
    if (state.status !== "ready" || actionState.status === "submitting") {
      return;
    }
    const targetSection = autoCompleteTargetSection(
      state.data.canonSections,
      state.data.readiness.missingSections,
    );
    if (!targetSection) {
      return;
    }
    setActionState({ status: "submitting", message: null, action: "auto-complete" });
    try {
      const response = await postJson<{ redirectTo?: string }>(
        `/api/books/${bookId}/canon-proposals/revise`,
        { autoComplete: true },
      );
      setActionState({ status: "success", message: "已提交修订任务。", action: null });
      if (response.redirectTo) {
        navigateTo(response.redirectTo);
      }
    } catch (error) {
      setActionState({
        status: "error",
        message: errorMessage(error, "提交修订失败。"),
        action: null,
      });
    }
  }

  async function requestCanonRevision(
    targetSection: string,
    revisionInstruction: string,
    action: "revise" | "auto-complete",
  ) {
    setActionState({ status: "submitting", message: null, action });
    try {
      const response = await postJson<{ redirectTo?: string }>(
        `/api/books/${bookId}/canon-proposals/revise`,
        { targetSection, instruction: revisionInstruction },
      );
      setActionState({ status: "success", message: "已提交修订任务。", action: null });
      if (response.redirectTo) {
        navigateTo(response.redirectTo);
      }
    } catch (error) {
      setActionState({
        status: "error",
        message: errorMessage(error, "提交修订失败。"),
        action: null,
      });
    }
  }

  if (state.status === "loading") {
    return (
      <section className="workbench-page" aria-labelledby="trusted-state-title">
        <div className="workbench-panel" role="status">
          正在加载可信设定...
        </div>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="workbench-page" aria-labelledby="trusted-state-title">
        <div className="workbench-panel workbench-panel--alert" role="alert">
          <h1 id="trusted-state-title">可信设定加载失败</h1>
          <p>{state.error}</p>
          <a className="workbench-action-button" href={`/books/${bookId}`}>
            返回项目页
          </a>
        </div>
      </section>
    );
  }

  const { book, canonSections, readiness, selectedRevision } = state.data;
  const selectedSection = canonSections.find((section) => section.key === selectedSectionKey) ?? null;
  const selectedSectionBlocked = !selectedSection || selectedSection.locked || !selectedSection.editable;
  const submittingAction = actionState.status === "submitting" ? actionState.action : null;
  const completionTarget = autoCompleteTargetSection(canonSections, readiness.missingSections);
  const reviseDisabled =
    selectedSectionBlocked || submittingAction !== null || instruction.trim().length === 0;

  function selectSection(sectionKey: string) {
    if (selectedSectionKey !== sectionKey) {
      setInstruction("");
      setActionState({ status: "idle", message: null, action: null });
    }
    setSelectedSectionKey(sectionKey);
  }

  return (
    <section className="workbench-page canon-gate-layout" aria-label="可信设定">
      <ProjectIdentityBar
        eyebrow="Trusted State"
        title="可信设定"
        meta={[
          { label: "项目", value: book.title },
          { label: "状态", value: statusLabel(book.status) },
          { label: "完整度", value: readiness.complete ? "已完整" : "待补全" },
        ]}
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

      <div className="guided-canon-grid">
        <main className="workbench-panel canon-gate-main">
          <section
            className={readiness.complete ? "canon-completion-gate trusted" : "canon-completion-gate"}
          >
            <div className="canon-completion-gate__header">
              <h2>{readiness.complete ? "可信设定已完整" : "可信设定仍需补全"}</h2>
              {!readiness.complete && completionTarget ? (
                <button
                  className="workbench-action-button canon-completion-gate__action"
                  disabled={submittingAction !== null}
                  type="button"
                  onClick={() => void autoCompleteCanon()}
                >
                  {submittingAction === "auto-complete" ? (
                    <AiWaitingIndicator label="自动补全中..." variant="inline" />
                  ) : (
                    "AI 自动补全"
                  )}
                </button>
              ) : null}
            </div>
            {readiness.messages.length ? (
              <ul>
                {readiness.messages.map((message) => (
                  <li key={message}>{message}</li>
                ))}
              </ul>
            ) : (
              <p>当前没有阻塞项。</p>
            )}
          </section>

          <CanonSectionMap
            sections={canonSections}
            selectedSectionKey={selectedSectionKey}
            onSelect={selectSection}
          />

          <AdvancedDisclosure title="完整设定内容">
            <section className="detail-state-sections" aria-label="可信设定分区">
              {canonSections.map((section) => (
                <article className="canon-section-panel data-card" id={section.anchor} key={section.key}>
                  <header className="canon-section-head">
                    <div>
                      <p className="eyebrow">{section.key}</p>
                      <h2>{section.label}</h2>
                    </div>
                    <span className={section.locked ? "status-pill trusted" : "status-pill pending"}>
                      {section.locked ? "已锁定" : "可修订"}
                    </span>
                  </header>
                  <CanonSectionContent section={section} />
                </article>
              ))}
            </section>
          </AdvancedDisclosure>
        </main>

        <aside className="completion-aside guided-canon-aside">
          <section>
            <p className="eyebrow">Revision Request</p>
            <h2>生成修订预览</h2>
            <form className="canon-revision-form" onSubmit={(event) => void reviseState(event)}>
              <p className="canon-revision-target">
                当前分区：{selectedSection?.label ?? "未选择"}
              </p>
              <label>
                修订意图
                <textarea
                  disabled={selectedSectionBlocked || submittingAction !== null}
                  value={instruction}
                  onChange={(event) => setInstruction(event.target.value)}
                  placeholder="说明你希望 AI 如何调整这个分区"
                />
              </label>
              <button
                className="workbench-action-button"
                disabled={reviseDisabled}
                type="submit"
              >
                {submittingAction === "revise" ? (
                  <AiWaitingIndicator label="提交修订中..." variant="inline" />
                ) : (
                  "生成修订预览"
                )}
              </button>
            </form>
          </section>
          <ImpactPanel title="影响预览" items={selectedSectionImpact(selectedSection)} />
          <RevisionPreview
            revision={selectedRevision}
            submittingAction={submittingAction}
            onApply={() => void applyRevision()}
            onDiscard={() => void discardRevision()}
          />
        </aside>
      </div>
    </section>
  );
}

function autoCompleteTargetSection(
  sections: CanonSectionPayload[],
  missingSections: string[],
): CanonSectionPayload | null {
  return (
    missingSections
      .map((sectionKey) => sections.find((section) => section.key === sectionKey) ?? null)
      .find((section) => section !== null && section.editable && !section.locked) ?? null
  );
}

function CanonSectionMap({
  sections,
  selectedSectionKey,
  onSelect,
}: {
  sections: CanonSectionPayload[];
  selectedSectionKey: string;
  onSelect: (sectionKey: string) => void;
}) {
  return (
    <section className="canon-section-map" aria-label="可信设定分区地图">
      {sections.map((section) => {
        const selected = section.key === selectedSectionKey;
        return (
          <button
            aria-pressed={selected}
            className={selected ? "canon-section-tile is-selected" : "canon-section-tile"}
            key={section.key}
            onClick={() => onSelect(section.key)}
            type="button"
          >
            <span className="canon-section-tile__key">{section.key}</span>
            <strong>{section.label}</strong>
            <span>{sectionItemCount(section.content)} 项</span>
            <span className={section.locked ? "status-pill trusted" : "status-pill pending"}>
              {section.locked ? "已锁定" : section.editable ? "可修订" : "不可修订"}
            </span>
          </button>
        );
      })}
    </section>
  );
}

function selectedSectionImpact(section: CanonSectionPayload | null): ImpactItem[] {
  if (!section) {
    return [{ label: "分区", value: "未选择", tone: "warning" }];
  }
  if (section.locked || !section.editable) {
    return [
      { label: "状态", value: "已锁定", tone: "warning" },
      { label: "修订", value: "不可提交", tone: "danger" },
    ];
  }
  return [
    { label: "提交结果", value: "只生成预览", tone: "neutral" },
    { label: "应用", value: "确认后才覆盖", tone: "good" },
  ];
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

function RevisionPreview({
  revision,
  submittingAction,
  onApply,
  onDiscard,
}: {
  revision: CanonProposalRevisionPayload | null;
  submittingAction: CanonAction | null;
  onApply: () => void;
  onDiscard: () => void;
}) {
  if (!revision) {
    return null;
  }
  return (
    <section className="canon-revision-preview" aria-labelledby="revision-preview-title">
      <div className="canon-preview-head">
        <div>
          <p className="eyebrow">Revision Proposal</p>
          <h2 id="revision-preview-title">变更预览</h2>
          <p>{revision.summary || "AI 尚未生成摘要。"}</p>
        </div>
        <span className="status-pill pending">{revision.status}</span>
      </div>

      <RevisionPreviewActions
        revision={revision}
        submittingAction={submittingAction}
        onApply={onApply}
        onDiscard={onDiscard}
      />

      <div className="canon-preview-sections">
        {Object.entries(revision.changedSections).map(([section, value]) => (
          <article className="canon-preview-section" key={section}>
            <header>
              <h3>{section}</h3>
              <span>将被替换</span>
            </header>
            <pre>{formatCanonValue(value)}</pre>
          </article>
        ))}
      </div>

      {revision.blockedSections.length ? (
        <section>
          <h3>blocked sections</h3>
          <ul>
            {revision.blockedSections.map((item, index) => (
              <li key={index}>{formatBlockedSection(item)}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  );
}

function RevisionPreviewActions({
  revision,
  submittingAction,
  onApply,
  onDiscard,
}: {
  revision: CanonProposalRevisionPayload;
  submittingAction: CanonAction | null;
  onApply: () => void;
  onDiscard: () => void;
}) {
  if (revision.status === "running") {
    return (
      <AiWaitingIndicator
        detail="模型正在生成可审阅的可信设定变更。"
        label="修订生成中"
        variant="message"
      />
    );
  }
  if (revision.status === "failed") {
    return (
      <p className="setup-message" role="alert">
        修订生成失败
      </p>
    );
  }
  if (revision.status !== "pending") {
    return null;
  }
  return (
    <div className="canon-preview-actions">
      <button
        className="workbench-action-button"
        disabled={submittingAction !== null}
        onClick={onApply}
        type="button"
      >
        {submittingAction === "apply" ? "应用中..." : "应用修订"}
      </button>
      <button
        className="workbench-secondary-button"
        disabled={submittingAction !== null}
        onClick={onDiscard}
        type="button"
      >
        {submittingAction === "discard" ? "放弃中..." : "放弃修订"}
      </button>
    </div>
  );
}

function CanonSectionContent({ section }: { section: CanonSectionPayload }) {
  if (!Array.isArray(section.content) || section.content.length === 0) {
    return <p>暂无记录。</p>;
  }
  return (
    <ul className="value-list">
      {section.content.slice(0, 8).map((item, index) => (
        <li key={index}>{shortValue(item)}</li>
      ))}
    </ul>
  );
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

function formatBlockedSection(value: unknown): string {
  if (isRecord(value)) {
    return `${String(value.section ?? "unknown")}: ${String(value.reason ?? "blocked")}`;
  }
  return String(value);
}

function formatCanonValue(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function shortValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (isRecord(value)) {
    return Object.values(value).map(shortValue).join(" · ");
  }
  if (value === null || value === undefined) {
    return "暂无记录";
  }
  return String(value);
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

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}
