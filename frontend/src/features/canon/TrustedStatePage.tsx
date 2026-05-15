import { useEffect, useState } from "react";

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

export function TrustedStatePage({ bookId }: TrustedStatePageProps) {
  const [state, setState] = useState<TrustedState>({
    status: "loading",
    data: null,
    error: null,
  });
  const [targetSection, setTargetSection] = useState("characters");
  const [instruction, setInstruction] = useState("");
  const [actionMessage, setActionMessage] = useState<string | null>(null);

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
            if (firstEditable) {
              setTargetSection(firstEditable.key);
            }
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
    await postJson(`/api/books/${bookId}/canon-proposals/apply`, { revisionId });
    setActionMessage("已应用修订。");
    navigateTo(`/books/${bookId}/state`);
  }

  async function discardRevision() {
    const revisionId = state.status === "ready" ? state.data.selectedRevision?.id : null;
    if (typeof revisionId !== "number") {
      return;
    }
    await postJson(`/api/books/${bookId}/canon-proposals/discard`, { revisionId });
    setActionMessage("已放弃修订。");
    navigateTo(`/books/${bookId}/state`);
  }

  async function reviseState(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await postJson<{ redirectTo?: string }>(
      `/api/books/${bookId}/canon-proposals/revise`,
      { targetSection, instruction },
    );
    setActionMessage("已提交修订任务。");
    if (response.redirectTo) {
      navigateTo(response.redirectTo);
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
  const editableSections = canonSections.filter((section) => section.editable && !section.locked);

  return (
    <section className="workbench-page canon-gate-layout" aria-labelledby="trusted-state-title">
      <div className="workbench-hero">
        <p className="eyebrow">Trusted State</p>
        <h1 id="trusted-state-title">可信设定</h1>
        <p className="lede">
          {book.title} · {statusLabel(book.status)} ·{" "}
          {readiness.complete ? "设定已满足生产门槛" : "仍有分区需要补全"}
        </p>
      </div>

      <div className="content-grid completion-grid">
        <main className="workbench-panel canon-gate-main">
          {actionMessage ? <p role="status">{actionMessage}</p> : null}
          <section
            className={readiness.complete ? "canon-completion-gate trusted" : "canon-completion-gate"}
          >
            <h2>{readiness.complete ? "可信设定已完整" : "可信设定仍需补全"}</h2>
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

          <RevisionPreview
            revision={selectedRevision}
            onApply={() => void applyRevision()}
            onDiscard={() => void discardRevision()}
          />

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
        </main>

        <aside className="completion-aside">
          <section>
            <p className="eyebrow">Revision Request</p>
            <h2>生成修订预览</h2>
            <form className="canon-revision-form" onSubmit={(event) => void reviseState(event)}>
              <label>
                修订分区
                <select value={targetSection} onChange={(event) => setTargetSection(event.target.value)}>
                  {editableSections.map((section) => (
                    <option key={section.key} value={section.key}>
                      {section.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                修订指令
                <textarea
                  value={instruction}
                  onChange={(event) => setInstruction(event.target.value)}
                  placeholder="说明你希望 AI 如何调整这个分区"
                />
              </label>
              <button className="workbench-action-button" disabled={!editableSections.length} type="submit">
                生成修订预览
              </button>
            </form>
          </section>
        </aside>
      </div>
    </section>
  );
}

function RevisionPreview({
  revision,
  onApply,
  onDiscard,
}: {
  revision: CanonProposalRevisionPayload | null;
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

      <div className="canon-preview-actions">
        <button className="workbench-action-button" onClick={onApply} type="button">
          应用修订
        </button>
        <button className="workbench-secondary-button" onClick={onDiscard} type="button">
          放弃修订
        </button>
      </div>

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
