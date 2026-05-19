import { useEffect, useState } from "react";

import { ApiError, getJson, postJson } from "@/lib/api";

type UpdateResult = {
  available: boolean;
  version: string | null;
  url: string | null;
  sha256: string | null;
  notes: string;
  publishedAt: string | null;
  sizeLabel: string;
};

type UpdateDefaults = {
  currentVersion: string;
  platform: string;
  manifestUrl: string | null;
};

type UpdateResponse = {
  result: UpdateResult;
  stagedInstall?: {
    planPath: string;
    payload: Record<string, unknown>;
  };
};

type DefaultsState =
  | { status: "loading"; data: null; error: null }
  | { status: "ready"; data: UpdateDefaults; error: null }
  | { status: "error"; data: null; error: string };

type UpdateState =
  | { status: "idle"; result: null; error: null }
  | { status: "submitting"; result: UpdateResult | null; error: null }
  | { status: "ready"; result: UpdateResult; error: null }
  | { status: "staged"; result: UpdateResult; planPath: string; error: null }
  | { status: "error"; result: UpdateResult | null; error: string };

export function UpdatesPage() {
  const [state, setState] = useState<UpdateState>({
    status: "idle",
    result: null,
    error: null,
  });

  const [defaultsState, setDefaultsState] = useState<DefaultsState>({
    status: "loading",
    data: null,
    error: null,
  });
  const [revealBusy, setRevealBusy] = useState(false);
  const [revealError, setRevealError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getJson<unknown>("/api/updates")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        const defaults = parseUpdateDefaults(payload);
        if (!defaults) {
          setDefaultsState({ status: "error", data: null, error: "更新配置格式无效。" });
          return;
        }
        setDefaultsState({ status: "ready", data: defaults, error: null });
      })
      .catch((error) => {
        if (!cancelled) {
          setDefaultsState({
            status: "error",
            data: null,
            error: errorMessage(error, "更新配置加载失败。"),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function checkUpdate() {
    const manifestUrl = updateManifestUrl(defaultsState);
    if (!manifestUrl) {
      setState({
        status: "error",
        result: state.result,
        error: "当前平台暂无可用更新通道。",
      });
      return;
    }
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
    const manifestUrl = updateManifestUrl(defaultsState);
    if (!manifestUrl) {
      setState({
        status: "error",
        result: state.result,
        error: "当前平台暂无可用更新通道。",
      });
      return;
    }
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

  async function revealStagedUpdate() {
    if (state.status !== "staged") {
      return;
    }
    setRevealBusy(true);
    setRevealError(null);
    try {
      await postJson<unknown>("/api/updates/reveal", { planPath: state.planPath });
    } catch (error) {
      setRevealError(errorMessage(error, "打开安装包位置失败。"));
    } finally {
      setRevealBusy(false);
    }
  }

  const result = state.result;
  const isSubmitting = state.status === "submitting";
  const defaults = defaultsState.status === "ready" ? defaultsState.data : null;
  const canCheck = defaultsState.status === "ready" && Boolean(defaults?.manifestUrl);

  return (
    <section className="workbench-page" aria-labelledby="updates-page-title">
      <div className="workbench-hero">
        <p className="eyebrow">Updates</p>
        <h1 id="updates-page-title">检查更新</h1>
        <p className="lede">只检查稳定版本；准备安装时会校验包并备份数据库，不会静默安装。</p>
      </div>

      <section className="workbench-panel open-book-form">
        {defaultsState.status === "error" ? (
          <p className="setup-message" role="alert">
            {defaultsState.error}
          </p>
        ) : null}
        {state.status === "error" ? (
          <p className="setup-message" role="alert">
            {state.error}
          </p>
        ) : null}
        {defaults ? (
          <dl className="book-workspace-facts">
            <div>
              <dt>当前版本</dt>
              <dd>当前版本 {defaults.currentVersion}</dd>
            </div>
            <div>
              <dt>安装包</dt>
              <dd>{platformLabel(defaults.platform)}</dd>
            </div>
          </dl>
        ) : null}
        <button
          className="workbench-action-button"
          disabled={isSubmitting || defaultsState.status === "loading" || !canCheck}
          onClick={() => void checkUpdate()}
          type="button"
        >
          {defaultsState.status === "loading" ? "加载中..." : isSubmitting ? "检查中..." : "检查更新"}
        </button>
      </section>

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
          {revealError ? (
            <p className="setup-message" role="alert">
              {revealError}
            </p>
          ) : null}
          <button
            className="workbench-secondary-button"
            disabled={revealBusy}
            onClick={() => void revealStagedUpdate()}
            type="button"
          >
            {revealBusy ? "打开中..." : "打开安装包位置"}
          </button>
        </section>
      ) : null}
    </section>
  );
}

function updateManifestUrl(defaultsState: DefaultsState): string | null {
  return defaultsState.status === "ready" ? defaultsState.data.manifestUrl : null;
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

function parseUpdateDefaults(payload: unknown): UpdateDefaults | null {
  if (!isRecord(payload)) {
    return null;
  }
  if (
    typeof payload.currentVersion !== "string" ||
    typeof payload.platform !== "string" ||
    (typeof payload.manifestUrl !== "string" && payload.manifestUrl !== null)
  ) {
    return null;
  }
  return {
    currentVersion: payload.currentVersion,
    platform: payload.platform,
    manifestUrl: payload.manifestUrl,
  };
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

function platformLabel(platformName: string): string {
  const labels: Record<string, string> = {
    "macos-arm64": "macOS Apple Silicon",
    "macos-x64": "macOS Intel",
    "windows-x64": "Windows x64",
  };
  return labels[platformName] ?? "当前平台";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
