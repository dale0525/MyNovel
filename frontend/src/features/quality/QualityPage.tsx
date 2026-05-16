import { useEffect, useState } from "react";

import { AiWaitingIndicator } from "@/components/feedback/AiWaitingIndicator";
import { ApiError, getJson, isAbortError, postJson } from "@/lib/api";
import type {
  BookPayload,
  DeconstructionStudyPayload,
  QualitySnapshotPayload,
  QualityResponse,
  StyleAssetPayload,
} from "@/lib/types";

type QualityState =
  | { status: "loading"; data: null; error: null }
  | { status: "ready"; data: QualityResponse; error: null }
  | { status: "error"; data: null; error: string };

type QualityAction = "style-asset" | "study" | "snapshot";

type ActionState =
  | { status: "idle"; message: null }
  | { status: "submitting"; action: QualityAction; message: null }
  | { status: "success"; message: string }
  | { status: "error"; message: string };

export function QualityPage({ bookId }: { bookId: number }) {
  const [state, setState] = useState<QualityState>({
    status: "loading",
    data: null,
    error: null,
  });
  const [actionState, setActionState] = useState<ActionState>({ status: "idle", message: null });
  const [assetName, setAssetName] = useState("");
  const [assetSourceTitle, setAssetSourceTitle] = useState("");
  const [assetText, setAssetText] = useState("");
  const [studyTitle, setStudyTitle] = useState("");
  const [studyText, setStudyText] = useState("");

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    setState({ status: "loading", data: null, error: null });

    fetchQuality(bookId, controller.signal)
      .then((payload) => {
        if (!cancelled) {
          setState({ status: "ready", data: payload, error: null });
        }
      })
      .catch((error: unknown) => {
        if (isAbortError(error) || cancelled) {
          return;
        }
        setState({
          status: "error",
          data: null,
          error: error instanceof Error ? error.message : "质量中心加载失败。",
        });
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [bookId]);

  async function refreshAfterAction(message: string) {
    const payload = await fetchQuality(bookId);
    setState({ status: "ready", data: payload, error: null });
    setActionState({ status: "success", message });
  }

  async function createStyleAsset(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActionState({ status: "submitting", action: "style-asset", message: null });
    try {
      await postJson(`/api/books/${bookId}/quality/style-assets`, {
        name: assetName,
        sourceTitle: assetSourceTitle,
        referenceText: assetText,
      });
      setAssetName("");
      setAssetSourceTitle("");
      setAssetText("");
      await refreshAfterAction("风格资产已保存。");
    } catch (error) {
      setActionState({ status: "error", message: errorMessage(error, "保存风格资产失败。") });
    }
  }

  async function createStudy(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActionState({ status: "submitting", action: "study", message: null });
    try {
      await postJson(`/api/books/${bookId}/quality/deconstruct-reference`, {
        sourceTitle: studyTitle,
        referenceText: studyText,
      });
      setStudyTitle("");
      setStudyText("");
      await refreshAfterAction("拆书笔记已生成。");
    } catch (error) {
      setActionState({ status: "error", message: errorMessage(error, "生成拆书笔记失败。") });
    }
  }

  async function createSnapshot() {
    setActionState({ status: "submitting", action: "snapshot", message: null });
    try {
      const payload = await postJson<unknown>(`/api/books/${bookId}/quality/snapshots`, {});
      const parsed = parseQualityResponse(payload);
      if (!parsed) {
        throw new Error("质量数据格式无效。");
      }
      setState({ status: "ready", data: parsed, error: null });
      setActionState({ status: "success", message: "质量分析已刷新。" });
    } catch (error) {
      setActionState({ status: "error", message: errorMessage(error, "刷新质量分析失败。") });
    }
  }

  if (state.status === "loading") {
    return (
      <section className="workbench-page" aria-labelledby="quality-page-title">
        <div className="workbench-panel" role="status">
          正在加载质量中心...
        </div>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="workbench-page" aria-labelledby="quality-page-title">
        <div className="workbench-panel workbench-panel--alert" role="alert">
          <h1 id="quality-page-title">质量中心加载失败</h1>
          <p>{state.error}</p>
          <a className="workbench-action-button" href={`/books/${bookId}`}>
            返回项目
          </a>
        </div>
      </section>
    );
  }

  const { book, styleAssets, deconstructionStudies, latestSnapshot, costStrategy } = state.data;
  const submitting = actionState.status === "submitting";
  const submittingAction = actionState.status === "submitting" ? actionState.action : null;

  return (
    <section className="workbench-page" aria-labelledby="quality-page-title">
      <div className="workbench-hero">
        <p className="eyebrow">Quality System</p>
        <h1 id="quality-page-title">质量中心</h1>
        <p className="lede">{book.title} · 风格资产、拆书学习、长期质量分析和导出入口。</p>
      </div>

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

      <div className="content-grid workspace-focus-layout">
        <main className="workbench-panel">
          <div className="workspace-section-head">
            <div>
              <p className="eyebrow">Long View</p>
              <h2>长期质量分析</h2>
            </div>
            <button
              className="workbench-secondary-button"
              disabled={submitting}
              onClick={() => void createSnapshot()}
              type="button"
            >
              {submittingAction === "snapshot" ? (
                <AiWaitingIndicator label="刷新分析中..." variant="inline" />
              ) : (
                "刷新质量分析"
              )}
            </button>
          </div>
          {latestSnapshot ? (
            <dl className="book-workspace-facts">
              <div>
                <dt>质量分</dt>
                <dd>{latestSnapshot.score}</dd>
              </div>
              <div>
                <dt>已批准</dt>
                <dd>{metric(latestSnapshot.metrics, "accepted_chapters")}</dd>
              </div>
              <div>
                <dt>待审核</dt>
                <dd>{metric(latestSnapshot.metrics, "review_backlog")}</dd>
              </div>
            </dl>
          ) : (
            <p>还没有长期质量分析。</p>
          )}
          {latestSnapshot?.recommendations.length ? (
            <ul className="workspace-mini-list">
              {latestSnapshot.recommendations.map((item, index) => (
                <li key={index}>{String(item)}</li>
              ))}
            </ul>
          ) : null}
        </main>

        <aside className="workspace-result-sidebar">
          <section className="workspace-result-section">
            <p className="eyebrow">Exports</p>
            <h2>下载</h2>
            <a className="workbench-secondary-link" href={`/api/books/${bookId}/export.md`}>
              导出 Markdown
            </a>
            <a className="workbench-secondary-link" href={`/api/books/${bookId}/export.json`}>
              导出 JSON
            </a>
          </section>
          <section className="workspace-result-section">
            <p className="eyebrow">Cost Strategy</p>
            <h2>成本策略</h2>
            {costStrategy ? (
              <p>
                {costStrategy.mode} · 建议批量数 {costStrategy.batch_limit} ·{" "}
                {costStrategy.context_policy}
              </p>
            ) : (
              <p>刷新质量分析后生成成本策略。</p>
            )}
          </section>
        </aside>
      </div>

      <div className="content-grid chapter-review-grid">
        <AssetPanel
          assets={styleAssets}
          disabled={submitting}
          name={assetName}
          sourceTitle={assetSourceTitle}
          text={assetText}
          onNameChange={setAssetName}
          onSourceTitleChange={setAssetSourceTitle}
          onTextChange={setAssetText}
          onSubmit={(event) => void createStyleAsset(event)}
        />
        <StudyPanel
          disabled={submitting}
          isBusy={submittingAction === "study"}
          studies={deconstructionStudies}
          title={studyTitle}
          text={studyText}
          onTitleChange={setStudyTitle}
          onTextChange={setStudyText}
          onSubmit={(event) => void createStudy(event)}
        />
      </div>
    </section>
  );
}

function AssetPanel({
  assets,
  disabled,
  name,
  sourceTitle,
  text,
  onNameChange,
  onSourceTitleChange,
  onTextChange,
  onSubmit,
}: {
  assets: StyleAssetPayload[];
  disabled: boolean;
  name: string;
  sourceTitle: string;
  text: string;
  onNameChange: (value: string) => void;
  onSourceTitleChange: (value: string) => void;
  onTextChange: (value: string) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="workbench-panel">
      <p className="eyebrow">Style Assets</p>
      <h2>风格资产</h2>
      {assets.length ? (
        <ul className="workspace-mini-list">
          {assets.slice(-5).map((asset) => (
            <li key={asset.id ?? asset.name}>
              <strong>{asset.name}</strong>
              <span>{asset.sourceTitle ?? asset.sourceExcerpt}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p>还没有风格资产。</p>
      )}
      <form className="chapter-action-form" onSubmit={onSubmit}>
        <label>
          资产名称
          <input disabled={disabled} onChange={(event) => onNameChange(event.target.value)} required value={name} />
        </label>
        <label>
          来源标题
          <input disabled={disabled} onChange={(event) => onSourceTitleChange(event.target.value)} value={sourceTitle} />
        </label>
        <label>
          参考片段
          <textarea disabled={disabled} onChange={(event) => onTextChange(event.target.value)} required value={text} />
        </label>
        <button className="workbench-secondary-button" disabled={disabled} type="submit">
          保存风格资产
        </button>
      </form>
    </section>
  );
}

function StudyPanel({
  disabled,
  isBusy,
  studies,
  title,
  text,
  onTitleChange,
  onTextChange,
  onSubmit,
}: {
  disabled: boolean;
  isBusy: boolean;
  studies: DeconstructionStudyPayload[];
  title: string;
  text: string;
  onTitleChange: (value: string) => void;
  onTextChange: (value: string) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="workbench-panel">
      <p className="eyebrow">Reference Study</p>
      <h2>拆书学习</h2>
      {studies.length ? (
        <ul className="workspace-mini-list">
          {studies.slice(-5).map((study) => (
            <li key={study.id ?? study.sourceTitle}>
              <strong>{study.sourceTitle}</strong>
              <span>{study.sourceExcerpt}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p>还没有拆书笔记。</p>
      )}
      <form className="chapter-action-form" onSubmit={onSubmit}>
        <label>
          参考标题
          <input disabled={disabled} onChange={(event) => onTitleChange(event.target.value)} required value={title} />
        </label>
        <label>
          参考正文
          <textarea disabled={disabled} onChange={(event) => onTextChange(event.target.value)} required value={text} />
        </label>
        <button className="workbench-secondary-button" disabled={disabled} type="submit">
          {isBusy ? <AiWaitingIndicator label="生成拆书中..." variant="inline" /> : "生成拆书笔记"}
        </button>
      </form>
    </section>
  );
}

async function fetchQuality(bookId: number, signal?: AbortSignal): Promise<QualityResponse> {
  const payload = await getJson<unknown>(`/api/books/${bookId}/quality`, { signal });
  const parsed = parseQualityResponse(payload);
  if (!parsed) {
    throw new Error("质量数据格式无效。");
  }
  return parsed;
}

function parseQualityResponse(payload: unknown): QualityResponse | null {
  if (!isRecord(payload) || !isBookPayload(payload.book)) {
    return null;
  }
  if (!Array.isArray(payload.styleAssets) || !payload.styleAssets.every(isStyleAssetPayload)) {
    return null;
  }
  if (
    !Array.isArray(payload.deconstructionStudies) ||
    !payload.deconstructionStudies.every(isDeconstructionStudyPayload)
  ) {
    return null;
  }
  if (payload.latestSnapshot !== null && !isQualitySnapshotPayload(payload.latestSnapshot)) {
    return null;
  }
  if (payload.costStrategy !== null && !isCostStrategyPayload(payload.costStrategy)) {
    return null;
  }
  return payload as QualityResponse;
}

function isBookPayload(value: unknown): value is BookPayload {
  return (
    isRecord(value) &&
    (typeof value.id === "number" || value.id === null) &&
    typeof value.title === "string" &&
    typeof value.genre === "string" &&
    typeof value.audience === "string" &&
    typeof value.status === "string" &&
    (typeof value.premise === "string" || value.premise === null)
  );
}

function isStyleAssetPayload(value: unknown): value is StyleAssetPayload {
  return (
    isRecord(value) &&
    (typeof value.id === "number" || value.id === null) &&
    typeof value.bookId === "number" &&
    typeof value.name === "string" &&
    (typeof value.sourceTitle === "string" || value.sourceTitle === null) &&
    typeof value.sourceExcerpt === "string" &&
    isRecord(value.fingerprint) &&
    isRecord(value.guidance) &&
    (typeof value.createdAt === "string" || value.createdAt === null)
  );
}

function isDeconstructionStudyPayload(value: unknown): value is DeconstructionStudyPayload {
  return (
    isRecord(value) &&
    (typeof value.id === "number" || value.id === null) &&
    typeof value.bookId === "number" &&
    typeof value.sourceTitle === "string" &&
    typeof value.sourceExcerpt === "string" &&
    Array.isArray(value.beatMap) &&
    isRecord(value.craftNotes) &&
    (typeof value.createdAt === "string" || value.createdAt === null)
  );
}

function isQualitySnapshotPayload(value: unknown): value is QualitySnapshotPayload {
  return (
    isRecord(value) &&
    (typeof value.id === "number" || value.id === null) &&
    typeof value.bookId === "number" &&
    typeof value.score === "number" &&
    isRecord(value.metrics) &&
    Array.isArray(value.recommendations) &&
    (typeof value.createdAt === "string" || value.createdAt === null)
  );
}

function isCostStrategyPayload(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.mode === "string" &&
    typeof value.batch_limit === "number" &&
    typeof value.context_policy === "string"
  );
}

function metric(metrics: Record<string, unknown>, key: string): string {
  const value = metrics[key];
  return typeof value === "number" || typeof value === "string" ? String(value) : "0";
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
