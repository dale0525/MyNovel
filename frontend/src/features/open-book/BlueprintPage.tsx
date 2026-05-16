import { useEffect, useRef, useState } from "react";

import { AiWaitingIndicator } from "@/components/feedback/AiWaitingIndicator";
import {
  type BlueprintCandidateView,
  fieldEntries,
  normalizeBlueprintCandidates,
  summaryValue,
} from "@/features/open-book/blueprintCandidates";
import { ApiError, getJson, isAbortError, postJson } from "@/lib/api";
import { navigateTo } from "@/lib/navigation";
import type { BlueprintPayload, BlueprintResponse } from "@/lib/types";

type BlueprintPageState =
  | { status: "loading"; blueprint: null; error: null }
  | { status: "ready"; blueprint: BlueprintPayload; error: null }
  | { status: "error"; blueprint: null; error: string };

type ActionResponse = {
  blueprintId?: number;
  bookId?: number;
  redirectTo?: string;
};

export function BlueprintPage({ blueprintId }: { blueprintId: number }) {
  const [state, setState] = useState<BlueprintPageState>({
    status: "loading",
    blueprint: null,
    error: null,
  });
  const [revisionNotes, setRevisionNotes] = useState("");
  const [selectedCandidateIndex, setSelectedCandidateIndex] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const pendingActionRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    const controller = new AbortController();
    setState({ status: "loading", blueprint: null, error: null });
    setRevisionNotes("");
    setSelectedCandidateIndex(0);
    setActionError(null);
    setPendingAction(null);
    pendingActionRef.current = null;

    async function loadBlueprint() {
      try {
        const response = await getJson<BlueprintResponse>(`/api/blueprints/${blueprintId}`, {
          signal: controller.signal,
        });
        if (cancelled) {
          return;
        }
        setState({ status: "ready", blueprint: response.blueprint, error: null });
        setSelectedCandidateIndex(0);
        if (isInProgress(response.blueprint.status)) {
          timer = window.setTimeout(() => {
            void loadBlueprint();
          }, 1500);
        }
      } catch (error) {
        if (isAbortError(error)) {
          return;
        }
        if (!cancelled) {
          setState({
            status: "error",
            blueprint: null,
            error: error instanceof Error ? error.message : "蓝图加载失败。",
          });
        }
      }
    }

    void loadBlueprint();

    return () => {
      cancelled = true;
      controller.abort();
      if (timer !== undefined) {
        window.clearTimeout(timer);
      }
    };
  }, [blueprintId]);

  async function runAction(action: string, path: string, body: Record<string, unknown>) {
    if (pendingActionRef.current !== null) {
      return;
    }
    pendingActionRef.current = action;
    setPendingAction(action);
    setActionError(null);
    try {
      const response = await postJson<ActionResponse>(path, body);
      if (response.redirectTo) {
        navigateTo(response.redirectTo);
      }
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : "操作失败。");
    } finally {
      pendingActionRef.current = null;
      setPendingAction(null);
    }
  }

  if (state.status === "loading") {
    return (
      <section className="workbench-page" aria-labelledby="blueprint-title">
        <div className="workbench-panel" role="status">
          正在加载蓝图...
        </div>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="workbench-page" aria-labelledby="blueprint-title">
        <div className="workbench-panel workbench-panel--alert" role="alert">
          <h1 id="blueprint-title">蓝图加载失败</h1>
          <p>{state.error}</p>
        </div>
      </section>
    );
  }

  const blueprint = state.blueprint;
  const blueprintInProgress = isInProgress(blueprint.status);
  const waitingLabel = blueprint.status === "pending" ? "蓝图排队中" : "蓝图生成中";
  const waitingDetail =
    blueprint.status === "pending"
      ? "任务已进入队列，等待模型开始生成。"
      : "模型正在拆解灵感、组织卖点和开篇结构。";
  const candidates = normalizeBlueprintCandidates(blueprint.content);
  const selectedCandidate =
    candidates.find((candidate) => candidate.index === selectedCandidateIndex) ?? candidates[0] ?? null;

  return (
    <section className="workbench-page blueprint-page" aria-labelledby="blueprint-title">
      <div className="workbench-hero">
        <p className="eyebrow">Blueprint v{blueprint.version}</p>
        <h1 id="blueprint-title">开书蓝图</h1>
        {blueprintInProgress ? (
          <AiWaitingIndicator detail={waitingDetail} label={waitingLabel} variant="hero" />
        ) : (
          <p className="lede">{statusText(blueprint.status)}</p>
        )}
      </div>

      {actionError && (
        <p className="setup-message" role="alert">
          {actionError}
        </p>
      )}

      {blueprint.status === "failed" && (
        <div className="workbench-panel workbench-panel--alert" role="alert">
          <h2>蓝图生成失败</h2>
          {blueprint.errorMessage && <p>{blueprint.errorMessage}</p>}
          {blueprint.parseError && <pre>{blueprint.parseError}</pre>}
          <button
            className="workbench-action-button"
            disabled={pendingAction !== null}
            onClick={() => void runAction("retry", `/api/blueprints/${blueprintId}/retry`, {})}
            type="button"
          >
            {pendingAction === "retry" ? (
              <AiWaitingIndicator label="重新提交中..." variant="inline" />
            ) : (
              "重试生成"
            )}
          </button>
        </div>
      )}

      {blueprint.status === "succeeded" && (
        <>
          {candidates.length > 0 && selectedCandidate ? (
            <div className="workbench-grid blueprint-workbench-grid">
              <section className="workbench-panel blueprint-content">
                <CandidateTabs
                  candidates={candidates}
                  onSelect={setSelectedCandidateIndex}
                  selectedIndex={selectedCandidate.index}
                />
                <CandidateComparison
                  candidates={candidates}
                  onSelect={setSelectedCandidateIndex}
                  selectedIndex={selectedCandidate.index}
                />
                <CandidateDetail candidate={selectedCandidate} />
              </section>

              <DecisionPanel
                blueprint={blueprint}
                candidate={selectedCandidate}
                onAccept={() =>
                  void runAction("accept", `/api/blueprints/${blueprintId}/accept`, {
                    selectedTitle: selectedCandidate.title,
                  })
                }
                onRevise={() =>
                  void runAction("revise", `/api/blueprints/${blueprintId}/revise`, {
                    revisionNotes,
                    selectedTitle: selectedCandidate.title,
                    selectedCandidateIndex: selectedCandidate.index,
                  })
                }
                pendingAction={pendingAction}
                revisionNotes={revisionNotes}
                setRevisionNotes={setRevisionNotes}
              />
            </div>
          ) : (
            <div className="workbench-panel workbench-panel--alert" role="alert">
              <h2>当前蓝图没有可用候选方向</h2>
              <p>模型返回内容里没有可选择的书名。可以重试生成，或查看模型原始返回排查问题。</p>
              <RawBlueprintDetails blueprint={blueprint} />
            </div>
          )}
        </>
      )}
    </section>
  );
}

function CandidateTabs({
  candidates,
  onSelect,
  selectedIndex,
}: {
  candidates: BlueprintCandidateView[];
  onSelect: (index: number) => void;
  selectedIndex: number;
}) {
  return (
    <div aria-label="候选方向" className="blueprint-candidate-tabs" role="tablist">
      {candidates.map((candidate) => (
        <button
          aria-selected={selectedIndex === candidate.index}
          className={selectedIndex === candidate.index ? "is-active" : ""}
          key={`${candidate.index}-${candidate.title}`}
          onClick={() => onSelect(candidate.index)}
          role="tab"
          type="button"
        >
          <strong>{candidate.title}</strong>
          {candidate.genre && <span>{candidate.genre}</span>}
        </button>
      ))}
    </div>
  );
}

function CandidateComparison({
  candidates,
  onSelect,
  selectedIndex,
}: {
  candidates: BlueprintCandidateView[];
  onSelect: (index: number) => void;
  selectedIndex: number;
}) {
  const rows = [
    { label: "题材", value: (candidate: BlueprintCandidateView) => candidate.genre },
    { label: "目标读者", value: (candidate: BlueprintCandidateView) => candidate.audience },
    { label: "核心冲突", value: (candidate: BlueprintCandidateView) => candidate.centralConflict },
    { label: "主角定位", value: (candidate: BlueprintCandidateView) => summaryValue(candidate.protagonist) },
    {
      label: "前三章钩子",
      value: (candidate: BlueprintCandidateView) =>
        candidate.chapterDirections
          .slice(0, 3)
          .map((chapter) => chapter.goal || chapter.title)
          .filter(Boolean)
          .join(" / "),
    },
    {
      label: "主要卖点",
      value: (candidate: BlueprintCandidateView) => candidate.sellingPoints.slice(0, 3).join("、"),
    },
  ];

  return (
    <div className="blueprint-comparison-wrap">
      <table aria-label="候选方向对比" className="blueprint-comparison">
        <thead>
          <tr>
            <th scope="col">对比项</th>
            {candidates.map((candidate) => (
              <th key={candidate.title} scope="col">
                <button
                  className={selectedIndex === candidate.index ? "is-active" : ""}
                  onClick={() => onSelect(candidate.index)}
                  type="button"
                >
                  {candidate.title}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th scope="row">{row.label}</th>
              {candidates.map((candidate) => (
                <td key={`${candidate.index}-${row.label}`}>{row.value(candidate) || "未提供"}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CandidateDetail({ candidate }: { candidate: BlueprintCandidateView }) {
  return (
    <article className="blueprint-candidate-detail">
      <header className="blueprint-direction-summary">
        <p className="eyebrow">当前方向</p>
        <h2>{candidate.centralConflict || candidate.title}</h2>
        <div className="blueprint-meta-strip">
          {candidate.genre && <span>{candidate.genre}</span>}
          {candidate.audience && <span>{candidate.audience}</span>}
        </div>
      </header>

      <section aria-labelledby="blueprint-selling-points" className="blueprint-info-section">
        <h3 id="blueprint-selling-points">卖点与读者承诺</h3>
        <ChipList emptyText="未提供核心卖点" items={candidate.sellingPoints} />
        <CompactList emptyText="未提供读者承诺" items={candidate.readerPromises} />
      </section>

      <div className="blueprint-two-column">
        <EntityPanel title="主角" value={candidate.protagonist} />
        <EntityPanel title="世界观" value={candidate.world} />
      </div>

      <section aria-labelledby="blueprint-chapters" className="blueprint-info-section">
        <h3 id="blueprint-chapters">前 10 章方向</h3>
        {candidate.chapterDirections.length > 0 ? (
          <ol className="blueprint-chapter-timeline">
            {candidate.chapterDirections.map((chapter) => (
              <li key={`${chapter.number}-${chapter.title}-${chapter.goal}`}>
                <span>{String(chapter.number).padStart(2, "0")}</span>
                <div>
                  <strong>{chapter.title}</strong>
                  {chapter.goal && <p>{chapter.goal}</p>}
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p>未提供章节方向</p>
        )}
      </section>

      {Object.keys(candidate.extras).length > 0 && (
        <details className="blueprint-extra-fields">
          <summary>模型补充信息</summary>
          <KeyValueList value={candidate.extras} />
        </details>
      )}
    </article>
  );
}

function DecisionPanel({
  blueprint,
  candidate,
  onAccept,
  onRevise,
  pendingAction,
  revisionNotes,
  setRevisionNotes,
}: {
  blueprint: BlueprintPayload;
  candidate: BlueprintCandidateView;
  onAccept: () => void;
  onRevise: () => void;
  pendingAction: string | null;
  revisionNotes: string;
  setRevisionNotes: (value: string) => void;
}) {
  const firstHooks = candidate.chapterDirections.slice(0, 3);
  const directionSummary = [
    candidate.sellingPoints.slice(0, 2).join("、"),
    candidate.centralConflict,
    firstHooks.map((chapter) => chapter.goal || chapter.title).join(" / "),
  ].filter(Boolean);

  return (
    <aside className="workbench-panel blueprint-actions blueprint-decision-panel">
      <h2>决策面板</h2>
      <section className="blueprint-decision-block">
        <p className="eyebrow">当前选择</p>
        <strong>{candidate.title}</strong>
        <p>{[candidate.genre, candidate.audience].filter(Boolean).join(" · ") || "题材和读者未提供"}</p>
      </section>

      <section className="blueprint-decision-block">
        <p className="eyebrow">方向差异</p>
        <CompactList emptyText="暂无可提取的差异摘要" items={directionSummary} />
      </section>

      <label className="provider-field">
        想让这一批怎么改
        <textarea
          onChange={(event) => setRevisionNotes(event.target.value)}
          placeholder="保留当前方向，但主角更主动，前三章冲突更强"
          value={revisionNotes}
        />
      </label>

      <div aria-label="修订提示" className="blueprint-revision-prompts">
        <span>保留当前方向，加强前三章</span>
        <span>主角更主动</span>
        <span>融合另一个候选的世界观</span>
      </div>

      <details className="blueprint-accept-preview" open>
        <summary>接受前预览</summary>
        <KeyValueList
          value={{
            书名: candidate.title,
            题材: candidate.genre,
            目标读者: candidate.audience,
            核心冲突: candidate.centralConflict,
            主角: summaryValue(candidate.protagonist),
            世界观: summaryValue(candidate.world),
            前10章: candidate.chapterDirections.map((chapter) => chapter.title || chapter.goal).join(" / "),
          }}
        />
      </details>

      <button className="workbench-action-button" disabled={pendingAction !== null} onClick={onAccept} type="button">
        {pendingAction === "accept" ? (
          <AiWaitingIndicator label="进入项目中..." variant="inline" />
        ) : (
          "选定这个方向，进入项目页"
        )}
      </button>
      <button
        className="workbench-action-button workbench-action-button--secondary"
        disabled={pendingAction !== null}
        onClick={onRevise}
        type="button"
      >
        {pendingAction === "revise" ? (
          <AiWaitingIndicator label="提交修订中..." variant="inline" />
        ) : (
          "按意见重生成一版"
        )}
      </button>

      <RawBlueprintDetails blueprint={blueprint} />
    </aside>
  );
}

function ChipList({ emptyText, items }: { emptyText: string; items: string[] }) {
  if (items.length === 0) {
    return <p>{emptyText}</p>;
  }
  return (
    <div className="blueprint-chip-list">
      {items.map((item) => (
        <span key={item}>{item}</span>
      ))}
    </div>
  );
}

function CompactList({ emptyText, items }: { emptyText: string; items: string[] }) {
  if (items.length === 0) {
    return <p>{emptyText}</p>;
  }
  return (
    <ul className="blueprint-compact-list">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function EntityPanel({ title, value }: { title: string; value: unknown }) {
  const summary = summaryValue(value);
  const knownFields = knownEntityFields(value);
  const extraFields = extraEntityFields(value);

  return (
    <section className="blueprint-entity-panel">
      <h3>{title}</h3>
      <p>{summary || "未提供"}</p>
      {Object.keys(knownFields).length > 0 && <KeyValueList value={knownFields} />}
      {Object.keys(extraFields).length > 0 && (
        <details className="blueprint-extra-fields">
          <summary>更多设定</summary>
          <KeyValueList value={extraFields} />
        </details>
      )}
    </section>
  );
}

function RawBlueprintDetails({ blueprint }: { blueprint: BlueprintPayload }) {
  return (
    <details className="blueprint-extra-fields">
      <summary>模型原始信息</summary>
      <KeyValueList
        value={{
          蓝图版本: `v${blueprint.version}`,
          原始灵感: blueprint.idea,
          修订来源: blueprint.instruction ?? "无",
          解析错误: blueprint.parseError ?? "",
        }}
      />
      <div className="blueprint-raw-content">
        <strong>模型返回</strong>
        <pre>{JSON.stringify(blueprint.content, null, 2)}</pre>
      </div>
    </details>
  );
}

function KeyValueList({ value }: { value: Record<string, unknown> }) {
  const entries = fieldEntries(value);
  if (entries.length === 0) {
    return <p>暂无信息</p>;
  }
  return (
    <dl className="blueprint-key-values">
      {entries.map(([key, entryValue]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{entryValue}</dd>
        </div>
      ))}
    </dl>
  );
}

const entitySummaryFields = ["summary", "name", "identity", "role", "goal", "flaw", "rules"];

function knownEntityFields(value: unknown): Record<string, unknown> {
  const fields = recordValue(value);
  return Object.fromEntries(entitySummaryFields.filter((key) => key in fields).map((key) => [key, fields[key]]));
}

function extraEntityFields(value: unknown): Record<string, unknown> {
  const fields = recordValue(value);
  return Object.fromEntries(Object.entries(fields).filter(([key]) => !entitySummaryFields.includes(key)));
}

function recordValue(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function isInProgress(status: BlueprintPayload["status"]): boolean {
  return status === "pending" || status === "running";
}

function statusText(status: BlueprintPayload["status"]): string {
  const labels = {
    pending: "蓝图排队中",
    running: "蓝图生成中",
    succeeded: "蓝图已生成，选择书名后可进入项目页。",
    failed: "蓝图生成失败，可重试或调整输入。",
  };
  return labels[status];
}
