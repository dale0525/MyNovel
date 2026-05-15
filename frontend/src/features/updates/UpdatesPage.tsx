import { useState } from "react";

import { ApiError, postJson } from "@/lib/api";

type UpdateResult = {
  available: boolean;
  version: string | null;
  url: string | null;
  sha256: string | null;
  notes: string;
  publishedAt: string | null;
  sizeLabel: string;
};

type UpdateResponse = {
  result: UpdateResult;
  stagedInstall?: {
    planPath: string;
    payload: Record<string, unknown>;
  };
};

type UpdateState =
  | { status: "idle"; result: null; error: null }
  | { status: "submitting"; result: UpdateResult | null; error: null }
  | { status: "ready"; result: UpdateResult; error: null }
  | { status: "staged"; result: UpdateResult; planPath: string; error: null }
  | { status: "error"; result: UpdateResult | null; error: string };

export function UpdatesPage() {
  const [manifestUrl, setManifestUrl] = useState("");
  const [state, setState] = useState<UpdateState>({
    status: "idle",
    result: null,
    error: null,
  });

  async function checkUpdate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState({ status: "submitting", result: state.result, error: null });
    try {
      const payload = await postJson<unknown>("/api/updates/check", { manifestUrl });
      const response = parseUpdateResponse(payload);
      if (!response) {
        throw new Error("更新结果格式无效。");
      }
      setState({ status: "ready", result: response.result, error: null });
    } catch (error) {
      setState({
        status: "error",
        result: state.result,
        error: errorMessage(error, "检查更新失败。"),
      });
    }
  }

  async function stageUpdate() {
    setState({ status: "submitting", result: state.result, error: null });
    try {
      const payload = await postJson<unknown>("/api/updates/stage", { manifestUrl });
      const response = parseUpdateResponse(payload);
      if (!response) {
        throw new Error("更新结果格式无效。");
      }
      if (response.stagedInstall) {
        setState({
          status: "staged",
          result: response.result,
          planPath: response.stagedInstall.planPath,
          error: null,
        });
      } else {
        setState({ status: "ready", result: response.result, error: null });
      }
    } catch (error) {
      setState({
        status: "error",
        result: state.result,
        error: errorMessage(error, "准备更新失败。"),
      });
    }
  }

  const result = state.result;
  const isSubmitting = state.status === "submitting";

  return (
    <section className="workbench-page" aria-labelledby="updates-page-title">
      <div className="workbench-hero">
        <p className="eyebrow">Updates</p>
        <h1 id="updates-page-title">检查更新</h1>
        <p className="lede">只检查稳定版本；准备安装时会校验包并备份数据库，不会静默安装。</p>
      </div>

      <form className="workbench-panel open-book-form" onSubmit={(event) => void checkUpdate(event)}>
        {state.status === "error" ? (
          <p className="setup-message" role="alert">
            {state.error}
          </p>
        ) : null}
        <label className="provider-field">
          更新元数据地址
          <input
            onChange={(event) => setManifestUrl(event.target.value)}
            placeholder="https://example.test/update.json"
            required
            type="url"
            value={manifestUrl}
          />
        </label>
        <button className="workbench-action-button" disabled={isSubmitting} type="submit">
          {isSubmitting ? "检查中..." : "检查更新"}
        </button>
      </form>

      {result ? (
        <section className="workbench-panel">
          {result.available ? (
            <>
              <p className="eyebrow">Stable Release</p>
              <h2>发现新版本 {result.version}</h2>
              <p>{result.notes || "没有变更说明。"}</p>
              <dl className="book-workspace-facts">
                <div>
                  <dt>下载大小</dt>
                  <dd>{result.sizeLabel || "未知"}</dd>
                </div>
                <div>
                  <dt>发布时间</dt>
                  <dd>{result.publishedAt || "未提供"}</dd>
                </div>
                <div>
                  <dt>校验值</dt>
                  <dd>{result.sha256 || "未提供"}</dd>
                </div>
              </dl>
              {result.url ? (
                <a className="workbench-secondary-link" href={result.url}>
                  下载更新
                </a>
              ) : null}
              <button
                className="workbench-secondary-button"
                disabled={isSubmitting}
                onClick={() => void stageUpdate()}
                type="button"
              >
                下载并准备安装
              </button>
            </>
          ) : (
            <>
              <p className="eyebrow">Stable Release</p>
              <h2>当前没有可用更新</h2>
              <p>当前版本已经是可用的稳定版本，或该版本已被跳过。</p>
            </>
          )}
        </section>
      ) : null}

      {state.status === "staged" ? (
        <section className="workbench-panel" role="status">
          <p className="eyebrow">Manual Install</p>
          <h2>更新已准备</h2>
          <p>安装包已下载并校验，数据库备份已生成。请手动确认安装。</p>
          <p>{state.planPath}</p>
        </section>
      ) : null}
    </section>
  );
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

function parseUpdateResponse(payload: unknown): UpdateResponse | null {
  if (!isRecord(payload) || !isUpdateResult(payload.result)) {
    return null;
  }
  if (payload.stagedInstall === undefined) {
    return { result: payload.result };
  }
  if (!isStagedInstall(payload.stagedInstall)) {
    return null;
  }
  return {
    result: payload.result,
    stagedInstall: payload.stagedInstall,
  };
}

function isUpdateResult(value: unknown): value is UpdateResult {
  return (
    isRecord(value) &&
    typeof value.available === "boolean" &&
    (typeof value.version === "string" || value.version === null) &&
    (typeof value.url === "string" || value.url === null) &&
    (typeof value.sha256 === "string" || value.sha256 === null) &&
    typeof value.notes === "string" &&
    (typeof value.publishedAt === "string" || value.publishedAt === null) &&
    typeof value.sizeLabel === "string"
  );
}

function isStagedInstall(value: unknown): value is NonNullable<UpdateResponse["stagedInstall"]> {
  return isRecord(value) && typeof value.planPath === "string" && isRecord(value.payload);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
