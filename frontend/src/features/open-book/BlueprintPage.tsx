import { useEffect, useState } from "react";

import { ApiError, getJson, postJson } from "@/lib/api";
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
  const [selectedTitle, setSelectedTitle] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function loadBlueprint() {
      try {
        const response = await getJson<BlueprintResponse>(`/api/blueprints/${blueprintId}`);
        if (cancelled) {
          return;
        }
        setState({ status: "ready", blueprint: response.blueprint, error: null });
        const titles = titleOptions(response.blueprint.content);
        if (titles.length > 0) {
          setSelectedTitle((current) => current || titles[0]);
        }
        if (isInProgress(response.blueprint.status)) {
          timer = window.setTimeout(() => {
            void loadBlueprint();
          }, 1500);
        }
      } catch (error) {
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
      if (timer !== undefined) {
        window.clearTimeout(timer);
      }
    };
  }, [blueprintId]);

  async function runAction(path: string, body: Record<string, unknown>) {
    setActionError(null);
    try {
      const response = await postJson<ActionResponse>(path, body);
      if (response.redirectTo) {
        navigateTo(response.redirectTo);
      }
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : "操作失败。");
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
  const titles = titleOptions(blueprint.content);

  return (
    <section className="workbench-page blueprint-page" aria-labelledby="blueprint-title">
      <div className="workbench-hero">
        <p className="eyebrow">Blueprint v{blueprint.version}</p>
        <h1 id="blueprint-title">开书蓝图</h1>
        <p className="lede">{statusText(blueprint.status)}</p>
      </div>

      {actionError && (
        <p className="setup-message" role="alert">
          {actionError}
        </p>
      )}

      {isInProgress(blueprint.status) && (
        <div className="workbench-panel" role="status">
          {blueprint.status === "pending" ? "蓝图排队中" : "蓝图生成中"}
        </div>
      )}

      {blueprint.status === "failed" && (
        <div className="workbench-panel workbench-panel--alert" role="alert">
          <h2>蓝图生成失败</h2>
          {blueprint.errorMessage && <p>{blueprint.errorMessage}</p>}
          {blueprint.parseError && <pre>{blueprint.parseError}</pre>}
          <button
            className="workbench-action-button"
            onClick={() => void runAction(`/api/blueprints/${blueprintId}/retry`, {})}
            type="button"
          >
            重试生成
          </button>
        </div>
      )}

      {blueprint.status === "succeeded" && (
        <div className="workbench-grid">
          <section className="workbench-panel blueprint-content">
            <h2>候选书名</h2>
            {titles.map((title) => (
              <label className="provider-checkbox" key={title}>
                <input
                  checked={selectedTitle === title}
                  name="selectedTitle"
                  onChange={() => setSelectedTitle(title)}
                  type="radio"
                />
                {title}
              </label>
            ))}
            <BlueprintSummary content={blueprint.content} />
          </section>

          <aside className="workbench-panel blueprint-actions">
            <h2>下一步</h2>
            <label className="provider-field">
              修订意见
              <textarea
                onChange={(event) => setRevisionNotes(event.target.value)}
                placeholder="主角更疯一点，节奏更爽文"
                value={revisionNotes}
              />
            </label>
            <button
              className="workbench-action-button"
              onClick={() =>
                void runAction(`/api/blueprints/${blueprintId}/revise`, {
                  revisionNotes,
                })
              }
              type="button"
            >
              提交修订
            </button>
            <button
              className="workbench-action-button"
              onClick={() =>
                void runAction(`/api/blueprints/${blueprintId}/accept`, {
                  selectedTitle,
                })
              }
              type="button"
            >
              接受并进入设定复审
            </button>
          </aside>
        </div>
      )}
    </section>
  );
}

function BlueprintSummary({ content }: { content: Record<string, unknown> }) {
  const premise = textValue(content.premise) || textValue(content.central_conflict);
  return (
    <div className="blueprint-summary">
      {premise && <p>{premise}</p>}
      {Array.isArray(content.reader_promises) && (
        <ul>
          {content.reader_promises.map((item, index) => (
            <li key={`${index}-${String(item)}`}>{String(item)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function titleOptions(content: Record<string, unknown>): string[] {
  const rawOptions = content.title_options;
  if (!Array.isArray(rawOptions)) {
    return [];
  }
  return rawOptions.map((option) => String(option).trim()).filter(Boolean);
}

function textValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function isInProgress(status: BlueprintPayload["status"]): boolean {
  return status === "pending" || status === "running";
}

function statusText(status: BlueprintPayload["status"]): string {
  const labels = {
    pending: "蓝图排队中",
    running: "蓝图生成中",
    succeeded: "蓝图已生成，选择书名后可进入设定复审。",
    failed: "蓝图生成失败，可重试或调整输入。",
  };
  return labels[status];
}
