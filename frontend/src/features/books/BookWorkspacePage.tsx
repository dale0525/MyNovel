import { type FormEvent, useEffect, useState } from "react";
import { ArrowRight, BookOpen, FileText, ListChecks, Settings, ShieldCheck } from "lucide-react";

import { ProjectIdentityBar } from "@/components/guidance/GuidedPanels";
import { ProjectChapterListView } from "@/features/books/ChapterListPanel";
import {
  ProjectVolumeOutlineView,
  type VolumeRevisionPayload,
  volumePlanSections,
} from "@/features/books/VolumeOutlinePanel";
import { TrustedStatePage } from "@/features/canon/TrustedStatePage";
import { ChapterPage } from "@/features/chapters/ChapterPage";
import { QualityPage } from "@/features/quality/QualityPage";
import { ApiError, getJson, isAbortError, postJson, postJsonLineStream } from "@/lib/api";
import { navigateTo } from "@/lib/navigation";
import { type LlmStreamEvent, nextStreamSnippets, streamEventPreview } from "@/lib/streaming";
import type { BookPayload, BookResponse, ChapterPayload, WordTargetsPayload } from "@/lib/types";

type BookWorkspaceState =
  | { status: "loading"; data: null; error: null }
  | { status: "ready"; data: BookResponse; error: null }
  | { status: "error"; data: null; error: string };

type BookWorkspacePageProps = {
  bookId: number;
  chapterId?: number;
  view?: BookWorkspaceView;
};

type BookWorkspaceView = "overview" | "settings" | "state" | "volumes" | "chapters" | "quality";

type WorkspaceAction = "run-batch" | "word-targets" | "volume-outline" | "volume-revision";

type ActionRedirectResponse = {
  redirectTo: string;
};

type WorkspaceStreamEvent = LlmStreamEvent<
  ActionRedirectResponse & { book?: unknown } & Record<string, unknown>
>;

export function BookWorkspacePage({ bookId, chapterId, view = "overview" }: BookWorkspacePageProps) {
  const [state, setState] = useState<BookWorkspaceState>({
    status: "loading",
    data: null,
    error: null,
  });
  const [actionBusy, setActionBusy] = useState<WorkspaceAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [streamAction, setStreamAction] = useState<WorkspaceAction | null>(null);
  const [streamSnippets, setStreamSnippets] = useState<string[]>([]);
  const [batchLimit, setBatchLimit] = useState(1);
  const [selectedVolumeKey, setSelectedVolumeKey] = useState<string | null>(null);
  const [targetWordCount, setTargetWordCount] = useState(120000);
  const [chapterWordCount, setChapterWordCount] = useState(2800);
  const [updateExistingChapters, setUpdateExistingChapters] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    setState({ status: "loading", data: null, error: null });

    getJson<unknown>(`/api/books/${bookId}`, { signal: controller.signal })
      .then((payload) => {
        const parsed = parseBookResponse(payload);
        if (!cancelled) {
          if (parsed) {
            setState({ status: "ready", data: parsed, error: null });
            setTargetWordCount(parsed.wordTargets.targetWordCount);
            setChapterWordCount(parsed.wordTargets.chapterWordCount);
          } else {
            setState({ status: "error", data: null, error: "项目数据格式无效。" });
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
            error: error instanceof Error ? error.message : "项目加载失败。",
          });
        }
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [bookId]);

  async function runBatchProduction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runAction("run-batch", async () => {
      await runStreamingRedirect(`/api/books/${bookId}/chapters/run-batch-stream`, {
        limit: batchLimit,
      });
    });
  }

  async function generateVolumeOutline() {
    await runAction("volume-outline", async () => {
      let response: BookResponse | null = null;
      await postJsonLineStream<WorkspaceStreamEvent>(
        `/api/books/${bookId}/volume-outline/generate-stream`,
        {},
        (streamEvent) => {
          const snippet = streamEventPreview(streamEvent);
          if (snippet) {
            setStreamSnippets((current) => nextStreamSnippets(current, snippet));
          }
          if (streamEvent.type === "failed") {
            throw new Error(typeof streamEvent.message === "string" ? streamEvent.message : "卷纲补全失败。");
          }
          if (streamEvent.type === "done") {
            response = parseBookResponse(streamEvent.book);
            if (!response) {
              throw new Error("卷纲补全结果格式无效。");
            }
          }
        },
      );
      if (!response) {
        throw new Error("卷纲补全没有返回结果。");
      }
      setState({ status: "ready", data: response, error: null });
      setActionStatus("卷纲已补全。");
    });
  }

  async function reviseVolumeOutline(payload: VolumeRevisionPayload) {
    await runAction("volume-revision", async () => {
      let response: BookResponse | null = null;
      await postJsonLineStream<WorkspaceStreamEvent>(
        `/api/books/${bookId}/volume-outline/revise-stream`,
        payload,
        (streamEvent) => {
          const snippet = streamEventPreview(streamEvent);
          if (snippet) {
            setStreamSnippets((current) => nextStreamSnippets(current, snippet));
          }
          if (streamEvent.type === "failed") {
            throw new Error(typeof streamEvent.message === "string" ? streamEvent.message : "卷纲修订失败。");
          }
          if (streamEvent.type === "done") {
            response = parseBookResponse(streamEvent.book);
            if (!response) {
              throw new Error("卷纲修订结果格式无效。");
            }
          }
        },
      );
      if (!response) {
        throw new Error("卷纲修订没有返回结果。");
      }
      setState({ status: "ready", data: response, error: null });
      setActionStatus("卷纲修订已应用。");
    });
  }

  async function saveWordTargets(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runAction("word-targets", async () => {
      const payload = await postJson<unknown>(`/api/books/${bookId}/word-targets`, {
        targetWordCount,
        chapterWordCount,
        updateExistingChapters,
      });
      const response = parseBookResponse(payload);
      if (!response) {
        throw new Error("目标字数保存结果格式无效。");
      }
      setState({ status: "ready", data: response, error: null });
      setTargetWordCount(response.wordTargets.targetWordCount);
      setChapterWordCount(response.wordTargets.chapterWordCount);
      setActionStatus("目标字数已保存。");
    });
  }

  async function runAction(action: WorkspaceAction, callback: () => Promise<void>) {
    setActionBusy(action);
    setActionError(null);
    setActionStatus(null);
    setStreamAction(action);
    setStreamSnippets([]);
    try {
      await callback();
    } catch (error) {
      setActionError(errorMessage(error, "操作失败。"));
    } finally {
      setActionBusy(null);
    }
  }

  async function runStreamingRedirect(path: string, body: Record<string, unknown>) {
    let redirectTo: string | null = null;
    await postJsonLineStream<WorkspaceStreamEvent>(path, body, (streamEvent) => {
      const snippet = streamEventPreview(streamEvent);
      if (snippet) {
        setStreamSnippets((current) => nextStreamSnippets(current, snippet));
      }
      if (streamEvent.type === "failed") {
        throw new Error(typeof streamEvent.message === "string" ? streamEvent.message : "操作失败。");
      }
      if (streamEvent.type === "done") {
        const response = parseActionRedirectResponse(streamEvent);
        if (!response) {
          throw new Error("运行结果格式无效。");
        }
        redirectTo = response.redirectTo;
      }
    });
    if (!redirectTo) {
      throw new Error("操作没有返回结果。");
    }
    navigateTo(projectScopedRedirect(bookId, redirectTo));
  }

  if (state.status === "loading") {
    return (
      <section className="workbench-page" aria-labelledby="book-workspace-title">
        <div className="workbench-panel" role="status">
          正在加载项目...
        </div>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="workbench-page" aria-labelledby="book-workspace-title">
        <div className="workbench-panel workbench-panel--alert" role="alert">
          <h1 id="book-workspace-title">项目加载失败</h1>
          <p>{state.error}</p>
          <a className="workbench-action-button" href="/">
            返回工作台
          </a>
        </div>
      </section>
    );
  }

  const { book, chapters, latestCanon, volumePlans } = state.data;
  const productionReady = latestCanon !== null && book.status !== "draft";
  const batchReady = productionReady && chapters.some(canBatchRunChapter);
  const volumeSections = volumePlanSections(volumePlans, chapters);
  const totalWordCount = chapters.reduce((total, chapter) => total + chapter.wordCount, 0);
  const acceptedChapterCount = chapters.filter((chapter) => chapter.status === "accepted").length;

  return (
    <section className="workbench-page book-workspace-page" aria-label={book.title}>
      <ProjectIdentityBar
        eyebrow="项目"
        title={book.title}
        meta={[
          { label: "状态", value: statusLabel(book.status) },
          { label: "设定", value: latestCanon ? versionLabel(latestCanon.version) : "尚未定盘" },
          { label: "章节", value: `${acceptedChapterCount}/${chapters.length}` },
          { label: "正文", value: `${totalWordCount} 字` },
        ]}
      />

      <ProjectSecondaryNav activeView={view} bookId={bookId} />

      {actionError ? (
        <section className="workspace-result-section workspace-result-section--alert" role="alert">
          {actionError}
        </section>
      ) : null}
      {actionStatus ? (
        <section className="workspace-result-section workspace-result-section--success" role="status">
          {actionStatus}
        </section>
      ) : null}

      <div className="book-workspace-sections">
        {view === "overview" ? (
          <ProjectOverview
            book={book}
            bookId={bookId}
            chapterCount={chapters.length}
            chapterWordCount={chapterWordCount}
            latestCanonVersion={latestCanon?.version ?? null}
            targetWordCount={targetWordCount}
            totalWordCount={totalWordCount}
            volumeCount={volumePlans.length}
          />
        ) : null}

        {view === "settings" ? (
          <ProjectSettingsView
            actionBusy={actionBusy}
            chapterWordCount={chapterWordCount}
            setChapterWordCount={setChapterWordCount}
            setTargetWordCount={setTargetWordCount}
            setUpdateExistingChapters={setUpdateExistingChapters}
            targetWordCount={targetWordCount}
            updateExistingChapters={updateExistingChapters}
            onSubmit={saveWordTargets}
          />
        ) : null}

        {view === "state" ? <TrustedStatePage bookId={bookId} embedded /> : null}

        {view === "volumes" ? (
          <ProjectVolumeOutlineView
            actionBusy={actionBusy}
            bookId={bookId}
            selectedVolumeKey={selectedVolumeKey}
            setSelectedVolumeKey={setSelectedVolumeKey}
            streamAction={streamAction}
            streamSnippets={streamSnippets}
            volumeSections={volumeSections}
            wordTargets={state.data.wordTargets}
            onGenerateVolumeOutline={generateVolumeOutline}
            onReviseVolumeOutline={reviseVolumeOutline}
          />
        ) : null}

        {view === "chapters" ? (
          chapterId === undefined ? (
            <ProjectChapterListView
              actionBusy={actionBusy}
              batchLimit={batchLimit}
              batchReady={batchReady}
              bookId={bookId}
              chapters={chapters}
              productionReady={productionReady}
              setBatchLimit={setBatchLimit}
              streamAction={streamAction}
              streamSnippets={streamSnippets}
              volumeSections={volumeSections}
              wordTargets={state.data.wordTargets}
              onRunBatchProduction={runBatchProduction}
            />
          ) : (
            <ChapterPage bookId={bookId} chapterId={chapterId} embedded />
          )
        ) : null}

        {view === "quality" ? <QualityPage bookId={bookId} embedded /> : null}
      </div>
    </section>
  );
}

function ProjectSecondaryNav({ activeView, bookId }: { activeView: BookWorkspaceView; bookId: number }) {
  const items = [
    { label: "概览", href: `/books/${bookId}`, view: "overview" },
    { label: "设置", href: `/books/${bookId}/settings`, view: "settings" },
    { label: "设定", href: `/books/${bookId}/state`, view: "state" },
    { label: "卷纲", href: `/books/${bookId}/volumes`, view: "volumes" },
    { label: "章节", href: `/books/${bookId}/chapters`, view: "chapters" },
    { label: "质量", href: `/books/${bookId}/quality`, view: "quality" },
  ];

  return (
    <nav className="book-workspace-subnav" aria-label="项目二级导航">
      {items.map((item) => (
        <a
          aria-current={item.view === activeView ? "page" : undefined}
          className="book-workspace-subnav__link"
          href={item.href}
          key={item.label}
        >
          {item.label}
        </a>
      ))}
    </nav>
  );
}

function ProjectOverview({
  book,
  bookId,
  chapterCount,
  chapterWordCount,
  latestCanonVersion,
  targetWordCount,
  totalWordCount,
  volumeCount,
}: {
  book: BookPayload;
  bookId: number;
  chapterCount: number;
  chapterWordCount: number;
  latestCanonVersion: number | null;
  targetWordCount: number;
  totalWordCount: number;
  volumeCount: number;
}) {
  const overviewCards = [
    {
      label: "项目设置",
      description: "字数目标与生产节奏",
      href: `/books/${bookId}/settings`,
      icon: Settings,
      value: `${targetWordCount} / ${chapterWordCount} 字`,
    },
    {
      label: "可信设定",
      description: "世界规则、人物和伏笔账本",
      href: `/books/${bookId}/state`,
      icon: ShieldCheck,
      value: latestCanonVersion === null ? "尚未定盘" : versionLabel(latestCanonVersion),
    },
    {
      label: "卷纲",
      description: "卷结构、卷概括与章节规划",
      href: `/books/${bookId}/volumes`,
      icon: BookOpen,
      value: `${volumeCount} 卷`,
    },
    {
      label: "章节",
      description: "章节队列、状态与批量生成",
      href: `/books/${bookId}/chapters`,
      icon: ListChecks,
      value: `${chapterCount} 章`,
    },
    {
      label: "质量",
      description: "风格资产、复审和导出",
      href: `/books/${bookId}/quality`,
      icon: FileText,
      value: `${totalWordCount} 字`,
    },
  ];

  return (
    <>
      <section className="workspace-result-section book-workspace-summary" aria-labelledby="project-summary-title">
        <div>
          <p className="eyebrow">项目概览</p>
          <h2 id="project-summary-title">项目概括</h2>
        </div>
        <p className="book-workspace-premise">{book.premise ?? "这个项目还没有记录核心承诺。"}</p>
        <dl className="book-workspace-facts book-workspace-facts--compact">
          <div>
            <dt>题材</dt>
            <dd>{book.genre || "未填写"}</dd>
          </div>
          <div>
            <dt>目标读者</dt>
            <dd>{book.audience || "未填写"}</dd>
          </div>
          <div>
            <dt>状态</dt>
            <dd>{statusLabel(book.status)}</dd>
          </div>
          <div>
            <dt>已有正文</dt>
            <dd>{totalWordCount} 字</dd>
          </div>
        </dl>
      </section>

      <section className="book-workspace-navigation" aria-label="项目二级入口">
        {overviewCards.map((item) => {
          const Icon = item.icon;
          return (
            <a className="book-workspace-nav-card" href={item.href} key={item.label}>
              <span className="book-workspace-nav-card__icon" aria-hidden="true">
                <Icon size={20} />
              </span>
              <span>
                <strong>{item.label}</strong>
                <small>{item.description}</small>
              </span>
              <em>{item.value}</em>
              <ArrowRight aria-hidden="true" size={18} />
            </a>
          );
        })}
      </section>
    </>
  );
}

function ProjectSettingsView({
  actionBusy,
  chapterWordCount,
  setChapterWordCount,
  setTargetWordCount,
  setUpdateExistingChapters,
  targetWordCount,
  updateExistingChapters,
  onSubmit,
}: {
  actionBusy: WorkspaceAction | null;
  chapterWordCount: number;
  setChapterWordCount: (value: number) => void;
  setTargetWordCount: (value: number) => void;
  setUpdateExistingChapters: (value: boolean) => void;
  targetWordCount: number;
  updateExistingChapters: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => Promise<void>;
}) {
  return (
    <section className="workspace-result-section" aria-labelledby="word-target-title">
      <p className="eyebrow">项目设置</p>
      <h2 id="word-target-title">项目设定</h2>
      <form className="chapter-action-form book-workspace-inline-form" onSubmit={(event) => void onSubmit(event)}>
        <label>
          全书目标字数
          <input
            min={1}
            type="number"
            value={targetWordCount}
            onChange={(event) => setTargetWordCount(clampedPositiveInt(event.target.value, 1))}
          />
        </label>
        <label>
          单章目标字数
          <input
            min={1}
            type="number"
            value={chapterWordCount}
            onChange={(event) => setChapterWordCount(clampedPositiveInt(event.target.value, 1))}
          />
        </label>
        <label className="chapter-major-change-toggle">
          <input
            checked={updateExistingChapters}
            type="checkbox"
            onChange={(event) => setUpdateExistingChapters(event.target.checked)}
          />
          同步更新待生产章节计划
        </label>
        <p className="book-workspace-form-note">已生成、待审核、需修订和已接受章节不会被改动。</p>
        <button className="workbench-action-button" disabled={actionBusy !== null} type="submit">
          {actionBusy === "word-targets" ? "保存中..." : "保存目标字数"}
        </button>
      </form>
    </section>
  );
}

function parseBookResponse(payload: unknown): BookResponse | null {
  if (!isRecord(payload) || !isBookPayload(payload.book)) {
    return null;
  }
  const bookOnlyResponse = {
    book: payload.book,
    wordTargets: defaultWordTargets(),
    chapters: [],
    latestCanon: null,
    runTraces: [],
    volumePlans: [],
  };
  if (
    payload.chapters === undefined &&
    payload.latestCanon === undefined &&
    payload.runTraces === undefined &&
    payload.volumePlans === undefined &&
    payload.wordTargets === undefined
  ) {
    return bookOnlyResponse;
  }
  if (
    !Array.isArray(payload.chapters) ||
    !Array.isArray(payload.runTraces) ||
    !Array.isArray(payload.volumePlans) ||
    (payload.latestCanon !== null && !isRecord(payload.latestCanon)) ||
    !isWordTargetsPayload(payload.wordTargets)
  ) {
    return null;
  }
  return {
    book: payload.book,
    wordTargets: payload.wordTargets,
    chapters: payload.chapters as BookResponse["chapters"],
    latestCanon: payload.latestCanon as BookResponse["latestCanon"],
    runTraces: payload.runTraces as BookResponse["runTraces"],
    volumePlans: payload.volumePlans as BookResponse["volumePlans"],
  };
}

function isBookPayload(value: unknown): value is BookPayload {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "number" &&
    typeof value.title === "string" &&
    typeof value.genre === "string" &&
    typeof value.audience === "string" &&
    typeof value.status === "string" &&
    (typeof value.premise === "string" || value.premise === null)
  );
}

function isWordTargetsPayload(value: unknown): value is WordTargetsPayload {
  return (
    isRecord(value) &&
    typeof value.targetWordCount === "number" &&
    typeof value.chapterWordCount === "number"
  );
}

function defaultWordTargets(): WordTargetsPayload {
  return {
    targetWordCount: 120000,
    chapterWordCount: 2800,
  };
}

function parseActionRedirectResponse(payload: unknown): ActionRedirectResponse | null {
  if (!isRecord(payload) || !isSafeAppPath(payload.redirectTo)) {
    return null;
  }
  return { redirectTo: payload.redirectTo };
}

function isSafeAppPath(value: unknown): value is string {
  return typeof value === "string" && value.startsWith("/") && !value.startsWith("//");
}

function projectScopedRedirect(bookId: number, redirectTo: string): string {
  const chapterMatch = redirectTo.match(/^\/chapters\/(\d+)$/);
  if (chapterMatch) {
    return `/books/${bookId}/chapters/${chapterMatch[1]}`;
  }
  return redirectTo;
}

function canBatchRunChapter(chapter: ChapterPayload): boolean {
  return ["planned", "running", "needs_revision"].includes(chapter.status);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

function clampedPositiveInt(value: string, min: number, max?: number): number {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return min;
  }
  const withMin = Math.max(min, parsed);
  return max === undefined ? withMin : Math.min(withMin, max);
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: "草稿",
    canon_locked: "可信设定已锁定",
    producing: "生产中",
    paused: "暂停",
  };
  return labels[status] ?? "未知状态";
}

function versionLabel(version: number): string {
  return `第 ${version} 版`;
}
