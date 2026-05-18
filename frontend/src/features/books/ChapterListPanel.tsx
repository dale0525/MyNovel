import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Play, WandSparkles } from "lucide-react";

import { AiStreamFeedback } from "@/components/feedback/AiStreamFeedback";
import { AiWaitingIndicator } from "@/components/feedback/AiWaitingIndicator";
import type { ChapterPayload, WordTargetsPayload } from "@/lib/types";
import {
  AllVolumesRevisionPanel,
  SingleVolumeRevisionPanel,
  VolumePlanHighlights,
  volumeTitle,
  type VolumeRevisionPayload,
  type VolumeSection,
} from "@/features/books/VolumeOutlinePanel";

type WorkspaceAction = "run-batch" | "word-targets" | "volume-outline" | "volume-revision";

type BatchProgressState = {
  completedSteps: number;
  totalSteps: number;
  currentLabel: string | null;
};

const BATCH_STAGE_LABELS = ["规划", "草稿", "状态", "审计", "修订"];

export function ProjectChapterListView({
  actionBusy,
  actionProgressLabel,
  batchProgress,
  batchReady,
  bookId,
  chapters,
  productionReady,
  selectedVolumeKey,
  setSelectedVolumeKey,
  streamAction,
  streamSnippets,
  volumeSections,
  wordTargets,
  onGenerateVolumeOutline,
  onRunBatchProduction,
  onReviseVolumeOutline,
}: {
  actionBusy: WorkspaceAction | null;
  actionProgressLabel: string | null;
  batchProgress: BatchProgressState | null;
  batchReady: boolean;
  bookId: number;
  chapters: ChapterPayload[];
  productionReady: boolean;
  selectedVolumeKey: string | null;
  setSelectedVolumeKey: (value: string | null) => void;
  streamAction: WorkspaceAction | null;
  streamSnippets: string[];
  volumeSections: VolumeSection[];
  wordTargets: WordTargetsPayload;
  onGenerateVolumeOutline: () => Promise<void>;
  onRunBatchProduction: (chapterIds: number[]) => Promise<void>;
  onReviseVolumeOutline: (payload: VolumeRevisionPayload) => Promise<void>;
}) {
  const sortedChapters = useMemo(
    () => [...chapters].sort((left, right) => left.number - right.number),
    [chapters],
  );
  const targetChapterCount = targetChapters(wordTargets);
  const missingChapterCount = Math.max(0, targetChapterCount - sortedChapters.length);
  const effectiveVolumeKey = selectedVolumeKey ?? firstActionableVolumeKey(volumeSections) ?? volumeSections[0]?.key ?? null;
  const selectedSection = volumeSections.find((section) => section.key === effectiveVolumeKey) ?? volumeSections[0] ?? null;
  const [selectedChapterIds, setSelectedChapterIds] = useState<number[]>([]);
  const selectableChapterIds = useMemo(
    () => sortedChapters.filter(isSelectableForBatch).map((chapter) => chapter.id as number),
    [sortedChapters],
  );
  const selectableChapterIdKey = selectableChapterIds.join(",");

  useEffect(() => {
    setSelectedChapterIds((current) => {
      const next = current.filter((chapterId) => selectableChapterIds.includes(chapterId));
      return next.length === current.length ? current : next;
    });
  }, [selectableChapterIdKey, selectableChapterIds]);

  return (
    <section className="workspace-result-section workspace-chapter-board" aria-labelledby="chapter-list-title">
      <div className="workspace-section-head">
        <div>
          <p className="eyebrow">章节列表</p>
          <h2 id="chapter-list-title">章节</h2>
        </div>
        {missingChapterCount > 0 ? (
          <button
            className="workbench-action-button"
            disabled={actionBusy !== null}
            type="button"
            onClick={() => void onGenerateVolumeOutline()}
          >
            {actionBusy === "volume-outline" ? (
              <AiWaitingIndicator label="补全卷纲中..." variant="inline" />
            ) : (
              <>
                <WandSparkles aria-hidden="true" size={17} />
                补全卷纲
              </>
            )}
          </button>
        ) : null}
      </div>

      <ChapterHeatmap
        missingChapterCount={missingChapterCount}
        selectedChapterIds={selectedChapterIds}
        setSelectedChapterIds={setSelectedChapterIds}
        setSelectedVolumeKey={setSelectedVolumeKey}
        sortedChapters={sortedChapters}
        targetChapterCount={targetChapterCount}
        volumeSections={volumeSections}
        wordTargets={wordTargets}
      />

      <AiStreamFeedback snippets={streamAction === "volume-outline" ? streamSnippets : []} />

      <BatchProductionPanel
        actionBusy={actionBusy}
        actionProgressLabel={actionProgressLabel}
        batchProgress={batchProgress}
        batchReady={batchReady}
        chapters={sortedChapters}
        productionReady={productionReady}
        selectedChapterIds={selectedChapterIds}
        streamSnippets={streamAction === "run-batch" ? streamSnippets : []}
        onRunBatchProduction={onRunBatchProduction}
      />

      <div className="workspace-planning-board">
        <VolumeSelectionRail
          effectiveVolumeKey={effectiveVolumeKey}
          selectedChapterIds={selectedChapterIds}
          setSelectedChapterIds={setSelectedChapterIds}
          setSelectedVolumeKey={setSelectedVolumeKey}
          volumeSections={volumeSections}
        />
        {selectedSection ? (
          <SelectedVolumePanel
            actionBusy={actionBusy}
            bookId={bookId}
            chapterWordCount={wordTargets.chapterWordCount}
            section={selectedSection}
            selectedChapterIds={selectedChapterIds}
            setSelectedChapterIds={setSelectedChapterIds}
            streamSnippets={streamAction === "volume-revision" ? streamSnippets : []}
            onRevisionSubmit={onReviseVolumeOutline}
          />
        ) : null}
      </div>

      <AllVolumesRevisionPanel
        actionBusy={actionBusy}
        streamSnippets={streamAction === "volume-revision" ? streamSnippets : []}
        onSubmit={onReviseVolumeOutline}
      />
    </section>
  );
}

function ChapterHeatmap({
  missingChapterCount,
  selectedChapterIds,
  setSelectedChapterIds,
  setSelectedVolumeKey,
  sortedChapters,
  targetChapterCount,
  volumeSections,
  wordTargets,
}: {
  missingChapterCount: number;
  selectedChapterIds: number[];
  setSelectedChapterIds: (updater: (current: number[]) => number[]) => void;
  setSelectedVolumeKey: (value: string | null) => void;
  sortedChapters: ChapterPayload[];
  targetChapterCount: number;
  volumeSections: VolumeSection[];
  wordTargets: WordTargetsPayload;
}) {
  const [hoveredChapter, setHoveredChapter] = useState<{
    chapter: ChapterPayload;
    section: VolumeSection;
  } | null>(null);
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef<{ chapter: ChapterPayload; section: VolumeSection } | null>(null);
  const dragModeRef = useRef<"add" | "remove">("add");
  const selectedSet = useMemo(() => new Set(selectedChapterIds), [selectedChapterIds]);
  const statusCards = chapterStatusCards(sortedChapters);

  useEffect(() => {
    const stopDragging = () => {
      isDraggingRef.current = false;
      dragStartRef.current = null;
      dragModeRef.current = "add";
    };
    window.addEventListener("mouseup", stopDragging);
    return () => window.removeEventListener("mouseup", stopDragging);
  }, []);

  function addCell(chapter: ChapterPayload, section: VolumeSection) {
    setSelectedVolumeKey(section.key);
    if (!isSelectableForBatch(chapter)) {
      return;
    }
    setSelectedChapterIds((current) => addIds(current, [chapter.id as number]));
  }

  function removeCell(chapter: ChapterPayload, section: VolumeSection) {
    setSelectedVolumeKey(section.key);
    if (!isSelectableForBatch(chapter)) {
      return;
    }
    setSelectedChapterIds((current) => removeIds(current, [chapter.id as number]));
  }

  function applyDragCell(chapter: ChapterPayload, section: VolumeSection) {
    if (dragModeRef.current === "remove") {
      removeCell(chapter, section);
      return;
    }
    addCell(chapter, section);
  }

  function toggleCell(chapter: ChapterPayload, section: VolumeSection) {
    setSelectedVolumeKey(section.key);
    if (!isSelectableForBatch(chapter)) {
      return;
    }
    setSelectedChapterIds((current) => toggleIds(current, [chapter.id as number]));
  }

  return (
    <section className="workspace-chapter-summary workspace-chapter-heatmap" aria-label="章节概览">
      <div className="workspace-heatmap-head">
        <div>
          <p className="eyebrow">章节地图</p>
          <strong>按卷选择生产目标</strong>
        </div>
        <dl className="workspace-heatmap-metrics" aria-label="章节规划覆盖">
          <div>
            <dt>覆盖进度</dt>
            <dd>{sortedChapters.length}/{targetChapterCount} 章</dd>
          </div>
          <div>
            <dt>规划缺口</dt>
            <dd>{missingChapterCount} 章</dd>
          </div>
          <div>
            <dt>单章目标</dt>
            <dd>{wordTargets.chapterWordCount} 字</dd>
          </div>
        </dl>
      </div>

      <div
        aria-label="横向滚动章节地图"
        className="workspace-heatmap-scroll"
        role="region"
        tabIndex={0}
      >
        <div className="workspace-heatmap-volumes" onMouseLeave={() => setHoveredChapter(null)}>
          {volumeSections.map((section) => (
            <section className="workspace-heatmap-volume" aria-label={volumeTitle(section)} key={section.key}>
              <div className="workspace-heatmap-volume__label">
                <strong>{volumeTitle(section)}</strong>
                <span>{chapterNumberRange(section.chapters)}</span>
              </div>
              <div
                className="workspace-heatmap-cells"
                style={{ gridTemplateColumns: `repeat(${heatmapColumnCount(section.chapters.length)}, 0.9rem)` }}
              >
                {section.chapters.map((chapter) => {
                  const selected = chapter.id !== null && selectedSet.has(chapter.id);
                  const selectable = isSelectableForBatch(chapter);
                  return (
                    <button
                      aria-label={`第 ${chapter.number} 章 · ${chapter.title} · ${chapterStatusLabel(chapter.status)}`}
                      aria-pressed={selected}
                      className={[
                        "workspace-heatmap-cell",
                        `workspace-heatmap-cell--${chapter.status}`,
                        selected ? "is-selected" : "",
                        selectable ? "" : "is-not-selectable",
                      ].filter(Boolean).join(" ")}
                      key={chapter.id ?? chapter.number}
                      type="button"
                      onClick={() => toggleCell(chapter, section)}
                      onFocus={() => setHoveredChapter({ chapter, section })}
                      onMouseDown={(event) => {
                        event.preventDefault();
                        isDraggingRef.current = true;
                        dragStartRef.current = { chapter, section };
                        dragModeRef.current = selected ? "remove" : "add";
                      }}
                      onMouseEnter={(event) => {
                        setHoveredChapter({ chapter, section });
                        if (isDraggingRef.current || event.buttons === 1) {
                          if (dragStartRef.current) {
                            applyDragCell(dragStartRef.current.chapter, dragStartRef.current.section);
                          }
                          applyDragCell(chapter, section);
                        }
                      }}
                      onMouseLeave={() => setHoveredChapter(null)}
                      onMouseUp={() => {
                        isDraggingRef.current = false;
                        dragStartRef.current = null;
                        dragModeRef.current = "add";
                      }}
                    />
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      </div>

      <div className="workspace-heatmap-footer">
        <div className="workspace-heatmap-legend" aria-label="章节状态统计">
          {statusCards.map((card) => (
            <span key={card.label}>
              <i className={`workspace-heatmap-swatch workspace-heatmap-cell--${card.status}`} aria-hidden="true" />
              <b>{card.label}</b>
              <em>{card.count}</em>
            </span>
          ))}
        </div>
        <span className="workspace-heatmap-selection">已选择 {selectedChapterIds.length} 章</span>
      </div>

      {hoveredChapter ? (
        <ChapterHeatmapTooltip chapter={hoveredChapter.chapter} section={hoveredChapter.section} />
      ) : null}
    </section>
  );
}

function ChapterHeatmapTooltip({
  chapter,
  section,
}: {
  chapter: ChapterPayload;
  section: VolumeSection;
}) {
  return (
    <aside className="workspace-heatmap-tooltip" role="tooltip">
      <div>
        <strong>第 {chapter.number} 章 · {chapter.title}</strong>
        <span>{volumeTitle(section)} · {chapterStatusLabel(chapter.status)}</span>
      </div>
      <p>{chapter.summary || "未写入摘要"}</p>
      <small>{chapter.wordCount} 字</small>
    </aside>
  );
}

function VolumeSelectionRail({
  effectiveVolumeKey,
  selectedChapterIds,
  setSelectedChapterIds,
  setSelectedVolumeKey,
  volumeSections,
}: {
  effectiveVolumeKey: string | null;
  selectedChapterIds: number[];
  setSelectedChapterIds: (updater: (current: number[]) => number[]) => void;
  setSelectedVolumeKey: (value: string | null) => void;
  volumeSections: VolumeSection[];
}) {
  return (
    <section className="workspace-volume-rail" aria-label="卷列表">
      <div className="workspace-volume-rail__head">
        <strong>卷纲</strong>
        <span>{volumeSections.length} 项</span>
      </div>
      {volumeSections.map((section) => {
        const selectableIds = selectableChapterIdsForSection(section);
        const checked = selectableIds.length > 0 && selectableIds.every((chapterId) => selectedChapterIds.includes(chapterId));
        const indeterminate = selectableIds.some((chapterId) => selectedChapterIds.includes(chapterId)) && !checked;
        return (
          <div className="workspace-volume-select-row" key={section.key}>
            <TriStateCheckbox
              checked={checked}
              disabled={selectableIds.length === 0}
              indeterminate={indeterminate}
              label={`选择${volumeTitle(section)}`}
              onChange={() => {
                setSelectedVolumeKey(section.key);
                setSelectedChapterIds((current) => toggleIds(current, selectableIds));
              }}
            />
            <button
              aria-pressed={effectiveVolumeKey === section.key}
              className="workspace-volume-tab"
              type="button"
              onClick={() => setSelectedVolumeKey(section.key)}
            >
              <span>{volumeTitle(section)}</span>
              <small>{chapterNumberRange(section.chapters)} · {volumeStatusSummary(section.chapters)}</small>
            </button>
          </div>
        );
      })}
    </section>
  );
}

function SelectedVolumePanel({
  actionBusy,
  bookId,
  chapterWordCount,
  section,
  selectedChapterIds,
  setSelectedChapterIds,
  streamSnippets,
  onRevisionSubmit,
}: {
  actionBusy: WorkspaceAction | null;
  bookId: number;
  chapterWordCount: number;
  section: VolumeSection;
  selectedChapterIds: number[];
  setSelectedChapterIds: (updater: (current: number[]) => number[]) => void;
  streamSnippets: string[];
  onRevisionSubmit: (payload: VolumeRevisionPayload) => Promise<void>;
}) {
  const volumeWords = section.chapters.length * chapterWordCount;

  return (
    <section className="workspace-volume-main" aria-label={`${volumeTitle(section)}章节规划`}>
      <section className="workspace-volume-detail" aria-label={`${volumeTitle(section)}概括`}>
        <header className="workspace-volume-detail__head">
          <div>
            <p className="eyebrow">当前卷</p>
            <strong>{volumeTitle(section)}</strong>
            <p>{section.plan?.coreConflict || "这一组章节还没有绑定卷纲。"}</p>
          </div>
          <span>{volumeStatusSummary(section.chapters)}</span>
        </header>
        <dl className="workspace-volume-detail__metrics" aria-label="单卷规划指标">
          <div>
            <dt>章节</dt>
            <dd>{section.chapters.length} 章</dd>
          </div>
          <div>
            <dt>目标正文</dt>
            <dd>{volumeWords} 字</dd>
          </div>
          <div>
            <dt>单章目标</dt>
            <dd>{chapterWordCount} 字</dd>
          </div>
          <div>
            <dt>可生产</dt>
            <dd>{selectableChapterIdsForSection(section).length} 章</dd>
          </div>
        </dl>
      </section>

      {section.plan ? <VolumePlanHighlights plan={section.plan} /> : null}

      <SelectableVolumeChapterList
        bookId={bookId}
        chapters={section.chapters}
        selectedChapterIds={selectedChapterIds}
        setSelectedChapterIds={setSelectedChapterIds}
      />

      <SingleVolumeRevisionPanel
        actionBusy={actionBusy}
        section={section}
        streamSnippets={streamSnippets}
        onSubmit={onRevisionSubmit}
      />
    </section>
  );
}

function SelectableVolumeChapterList({
  bookId,
  chapters,
  selectedChapterIds,
  setSelectedChapterIds,
}: {
  bookId: number;
  chapters: ChapterPayload[];
  selectedChapterIds: number[];
  setSelectedChapterIds: (updater: (current: number[]) => number[]) => void;
}) {
  if (!chapters.length) {
    return <p className="workspace-volume-empty">这一卷还没有章节规划。</p>;
  }

  return (
    <ol className="workspace-volume-chapter-list workspace-volume-chapter-list--selectable" aria-label="本卷章节列表">
      {chapters.map((chapter) => {
        const selectable = isSelectableForBatch(chapter);
        const chapterId = chapter.id ?? 0;
        return (
          <li key={chapter.id ?? chapter.number}>
            <input
              aria-label={`选择第 ${chapter.number} 章 · ${chapter.title}`}
              checked={selectedChapterIds.includes(chapterId)}
              disabled={!selectable}
              type="checkbox"
              onChange={() => setSelectedChapterIds((current) => toggleIds(current, [chapterId]))}
            />
            <span className="workspace-volume-chapter-number">第 {chapter.number} 章</span>
            <div>
              {chapter.id === null || chapter.id === undefined ? (
                <strong>第 {chapter.number} 章 · {chapter.title}</strong>
              ) : (
                <a className="workspace-mini-list-link" href={`/books/${bookId}/chapters/${chapter.id}`}>
                  第 {chapter.number} 章 · {chapter.title}
                </a>
              )}
              <small>{chapter.summary || "未写入摘要"}</small>
            </div>
            <span className={`workspace-chapter-status workspace-chapter-status--${chapter.status}`}>
              {chapterStatusLabel(chapter.status)} · {chapter.wordCount} 字
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function BatchProductionPanel({
  actionBusy,
  actionProgressLabel,
  batchProgress,
  batchReady,
  chapters,
  productionReady,
  selectedChapterIds,
  streamSnippets,
  onRunBatchProduction,
}: {
  actionBusy: WorkspaceAction | null;
  actionProgressLabel: string | null;
  batchProgress: BatchProgressState | null;
  batchReady: boolean;
  chapters: ChapterPayload[];
  productionReady: boolean;
  selectedChapterIds: number[];
  streamSnippets: string[];
  onRunBatchProduction: (chapterIds: number[]) => Promise<void>;
}) {
  const selectedChapters = chapters.filter((chapter) => chapter.id !== null && selectedChapterIds.includes(chapter.id));
  const selectedCount = selectedChapters.length;

  function submitSelection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!batchReady || selectedCount === 0 || actionBusy !== null) {
      return;
    }
    void onRunBatchProduction(selectedChapters.map((chapter) => chapter.id as number));
  }

  return (
    <section className="workspace-chapter-command workspace-chapter-command--batch" aria-labelledby="batch-production-title">
      <div className="workspace-batch-heading">
        <p className="eyebrow">批量生产</p>
        <h3 id="batch-production-title">批量操作</h3>
      </div>
      {batchReady ? (
        <form aria-label="批量生成控制" className="book-workspace-batch-form workspace-batch-control" onSubmit={submitSelection}>
          <div className="workspace-batch-selection" aria-label="批量章节选择">
            <span>已选择</span>
            <strong>{selectedCount}</strong>
            <span>章</span>
          </div>
          <BatchProgressMeter
            progress={batchProgress}
            selectedCount={selectedCount}
          />
          <div className="workspace-batch-submit">
            <button className="workbench-action-button" disabled={actionBusy !== null || selectedCount === 0} type="submit">
              {actionBusy === "run-batch" ? (
                <AiWaitingIndicator label={actionProgressLabel ?? "提交批量中..."} variant="inline" />
              ) : (
                <>
                  <Play aria-hidden="true" size={17} />
                  {selectedCount > 0 ? `生成选中的 ${selectedCount} 章` : "选择章节后生成"}
                </>
              )}
            </button>
          </div>
          <AiStreamFeedback snippets={streamSnippets} />
        </form>
      ) : (
        <p>{productionReady ? "没有可批量生成的章节。" : "可信设定锁定后才能批量生成章节。"}</p>
      )}
    </section>
  );
}

function BatchProgressMeter({
  progress,
  selectedCount,
}: {
  progress: BatchProgressState | null;
  selectedCount: number;
}) {
  const fallbackTotal = selectedCount * BATCH_STAGE_LABELS.length;
  const totalSteps = progress?.totalSteps ?? fallbackTotal;
  const completedSteps = Math.min(progress?.completedSteps ?? 0, Math.max(totalSteps, 0));
  const progressMax = Math.max(totalSteps, 1);
  const progressPercent = Math.min(100, Math.round((completedSteps / progressMax) * 100));
  const activeStageIndex = progress && progress.completedSteps > 0
    ? (progress.completedSteps - 1) % BATCH_STAGE_LABELS.length
    : -1;

  return (
    <div className="workspace-batch-progress">
      <div className="workspace-batch-progress__head">
        <div>
          <span>批量生成进度</span>
          <small>{progress?.currentLabel ?? (selectedCount > 0 ? "等待启动" : "未选择章节")}</small>
        </div>
        <strong>{completedSteps}/{totalSteps} 步</strong>
      </div>
      <div
        aria-label="批量生成进度"
        aria-valuemax={progressMax}
        aria-valuemin={0}
        aria-valuenow={completedSteps}
        className="workspace-batch-progress__bar"
        role="progressbar"
      >
        <span style={{ width: `${progressPercent}%` }} />
      </div>
      <ol className="workspace-batch-stage-strip" aria-label="批量生成阶段">
        {BATCH_STAGE_LABELS.map((label, index) => (
          <li className={index === activeStageIndex ? "is-active" : undefined} key={label}>
            {label}
          </li>
        ))}
      </ol>
    </div>
  );
}

function TriStateCheckbox({
  checked,
  disabled,
  indeterminate,
  label,
  onChange,
}: {
  checked: boolean;
  disabled: boolean;
  indeterminate: boolean;
  label: string;
  onChange: () => void;
}) {
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.indeterminate = indeterminate;
    }
  }, [indeterminate]);

  return (
    <input
      aria-label={label}
      checked={checked}
      disabled={disabled}
      ref={ref}
      type="checkbox"
      onChange={onChange}
    />
  );
}

function chapterStatusCards(chapters: ChapterPayload[]) {
  return [
    { label: "总章数", count: chapters.length, status: "all" },
    { label: "待生产", count: chapters.filter((chapter) => chapter.status === "planned").length, status: "planned" },
    { label: "待审核", count: chapters.filter((chapter) => chapter.status === "awaiting_review").length, status: "awaiting_review" },
    { label: "需修订", count: chapters.filter((chapter) => chapter.status === "needs_revision").length, status: "needs_revision" },
    { label: "已接受", count: chapters.filter((chapter) => chapter.status === "accepted").length, status: "accepted" },
    { label: "生成中", count: chapters.filter((chapter) => chapter.status === "running").length, status: "running" },
  ];
}

function chapterStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    planned: "待生产",
    running: "生成中",
    awaiting_review: "待审阅",
    needs_revision: "需修订",
    accepted: "已接受",
  };
  return labels[status] ?? "未知状态";
}

function targetChapters(wordTargets: WordTargetsPayload): number {
  const chapterWordCount = Math.max(1, wordTargets.chapterWordCount);
  return Math.max(1, Math.ceil(wordTargets.targetWordCount / chapterWordCount));
}

function isSelectableForBatch(chapter: ChapterPayload): boolean {
  return chapter.id !== null && chapter.id !== undefined && ["planned", "needs_revision"].includes(chapter.status);
}

function selectableChapterIdsForSection(section: VolumeSection): number[] {
  return section.chapters.filter(isSelectableForBatch).map((chapter) => chapter.id as number);
}

function toggleIds(current: number[], ids: number[]): number[] {
  if (ids.length === 0) {
    return current;
  }
  const allSelected = ids.every((id) => current.includes(id));
  if (allSelected) {
    return current.filter((id) => !ids.includes(id));
  }
  return [...current, ...ids.filter((id) => !current.includes(id))];
}

function addIds(current: number[], ids: number[]): number[] {
  const missingIds = ids.filter((id) => !current.includes(id));
  return missingIds.length === 0 ? current : [...current, ...missingIds];
}

function removeIds(current: number[], ids: number[]): number[] {
  const next = current.filter((id) => !ids.includes(id));
  return next.length === current.length ? current : next;
}

function firstActionableVolumeKey(volumeSections: VolumeSection[]): string | null {
  const actionable = volumeSections.find((section) =>
    section.chapters.some((chapter) =>
      ["running", "awaiting_review", "needs_revision", "planned"].includes(chapter.status),
    ),
  );
  return actionable?.key ?? null;
}

function volumeStatusSummary(chapters: ChapterPayload[]): string {
  const accepted = chapters.filter((chapter) => chapter.status === "accepted").length;
  const review = chapters.filter((chapter) => chapter.status === "awaiting_review" || chapter.status === "needs_revision").length;
  const running = chapters.filter((chapter) => chapter.status === "running").length;
  if (running > 0) {
    return `${running} 章生成中`;
  }
  if (review > 0) {
    return `${review} 章待处理`;
  }
  if (accepted > 0) {
    return `${accepted}/${chapters.length} 已接受`;
  }
  return chapters.length > 0 ? "待生产" : "无章节";
}

function chapterNumberRange(chapters: ChapterPayload[]): string {
  if (chapters.length === 0) {
    return "暂无章节";
  }
  const numbers = chapters.map((chapter) => chapter.number).sort((left, right) => left - right);
  if (numbers.length === 1) {
    return `第 ${numbers[0]} 章`;
  }
  return `第 ${numbers[0]}-${numbers[numbers.length - 1]} 章`;
}

function heatmapColumnCount(chapterCount: number): number {
  return Math.max(1, Math.min(chapterCount, 12));
}
