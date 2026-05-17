import { type FormEvent } from "react";
import { AlertCircle, CheckCircle2, CircleDashed, Clock3, ListChecks, Play, RotateCcw } from "lucide-react";

import { AiStreamFeedback } from "@/components/feedback/AiStreamFeedback";
import { AiWaitingIndicator } from "@/components/feedback/AiWaitingIndicator";
import type { ChapterPayload, WordTargetsPayload } from "@/lib/types";
import { volumeTitle, type VolumeSection } from "@/features/books/VolumeOutlinePanel";

type WorkspaceAction = "run-batch" | "word-targets" | "volume-outline" | "volume-revision";

export function ProjectChapterListView({
  actionBusy,
  batchLimit,
  batchReady,
  bookId,
  chapters,
  productionReady,
  setBatchLimit,
  streamAction,
  streamSnippets,
  volumeSections,
  wordTargets,
  onRunBatchProduction,
}: {
  actionBusy: WorkspaceAction | null;
  batchLimit: number;
  batchReady: boolean;
  bookId: number;
  chapters: ChapterPayload[];
  productionReady: boolean;
  setBatchLimit: (value: number) => void;
  streamAction: WorkspaceAction | null;
  streamSnippets: string[];
  volumeSections: VolumeSection[];
  wordTargets: WordTargetsPayload;
  onRunBatchProduction: (event: FormEvent<HTMLFormElement>) => Promise<void>;
}) {
  const sortedChapters = [...chapters].sort((left, right) => left.number - right.number);
  const statusCards = chapterStatusCards(sortedChapters);
  const targetChapterCount = targetChapters(wordTargets);
  const missingChapterCount = Math.max(0, targetChapterCount - sortedChapters.length);
  const progress = Math.min(100, Math.round((sortedChapters.length / targetChapterCount) * 100));

  return (
    <section className="workspace-result-section workspace-chapter-board" aria-labelledby="chapter-list-title">
      <div className="workspace-section-head">
        <div>
          <p className="eyebrow">章节列表</p>
          <h2 id="chapter-list-title">章节</h2>
        </div>
        <a className="workbench-secondary-link" href={`/books/${bookId}/volumes`}>
          查看卷纲
        </a>
      </div>

      <div className="workspace-chapter-overview" aria-label="章节规划覆盖">
        <div className="workspace-chapter-progress">
          <p className="eyebrow">覆盖进度</p>
          <strong>{sortedChapters.length}/{targetChapterCount} 章</strong>
          <span>全书 {wordTargets.targetWordCount} 字 · 单章 {wordTargets.chapterWordCount} 字</span>
          <div className="workspace-chapter-progress__bar" aria-hidden="true">
            <span style={{ width: `${progress}%` }} />
          </div>
        </div>
        <div className="workspace-chapter-gap">
          <span>规划缺口</span>
          <strong>{missingChapterCount} 章</strong>
        </div>
      </div>

      <div className="workspace-chapter-status-grid" aria-label="章节状态统计">
        {statusCards.map((card) => {
          const Icon = card.icon;
          return (
            <div className="workspace-chapter-stat" key={card.label}>
              <Icon aria-hidden="true" size={17} />
              <span>{card.label}</span>
              <strong>{card.count}</strong>
            </div>
          );
        })}
      </div>

      <div className="workspace-chapter-command" aria-labelledby="batch-production-title">
        <div>
          <p className="eyebrow">批量生产</p>
          <h3 id="batch-production-title">批量操作</h3>
        </div>
        {batchReady ? (
          <form className="chapter-action-form book-workspace-batch-form" onSubmit={(event) => void onRunBatchProduction(event)}>
            <label>
              生成章节数
              <input
                max={10}
                min={1}
                type="number"
                value={batchLimit}
                onChange={(event) => setBatchLimit(clampedPositiveInt(event.target.value, 1, 10))}
              />
            </label>
            <button className="workbench-action-button" disabled={actionBusy !== null} type="submit">
              {actionBusy === "run-batch" ? (
                <AiWaitingIndicator label="提交批量中..." variant="inline" />
              ) : (
                <>
                  <Play aria-hidden="true" size={17} />
                  批量生成
                </>
              )}
            </button>
            <AiStreamFeedback snippets={streamAction === "run-batch" ? streamSnippets : []} />
          </form>
        ) : (
          <p>{productionReady ? "没有可批量生成的章节。" : "可信设定锁定后才能批量生成章节。"}</p>
        )}
      </div>

      <ol className="workspace-chapter-list" aria-label="章节列表">
        {sortedChapters.map((chapter) => (
          <li key={chapter.id ?? chapter.number} className="workspace-chapter-row">
            <div className="workspace-chapter-row__body">
              {chapter.id === null || chapter.id === undefined ? (
                <strong>第 {chapter.number} 章 · {chapter.title}</strong>
              ) : (
                <a className="workspace-mini-list-link" href={`/books/${bookId}/chapters/${chapter.id}`}>
                  第 {chapter.number} 章 · {chapter.title}
                </a>
              )}
              <small>{chapterSubline(volumeSections, chapter)}</small>
            </div>
            <span className={`workspace-chapter-status workspace-chapter-status--${chapter.status}`}>
              {chapterStatusLabel(chapter.status)} · {chapter.wordCount} 字
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function chapterStatusCards(chapters: ChapterPayload[]) {
  return [
    { label: "总章数", count: chapters.length, icon: ListChecks },
    { label: "待生产", count: chapters.filter((chapter) => chapter.status === "planned").length, icon: CircleDashed },
    { label: "待审核", count: chapters.filter((chapter) => chapter.status === "awaiting_review").length, icon: Clock3 },
    { label: "需修订", count: chapters.filter((chapter) => chapter.status === "needs_revision").length, icon: AlertCircle },
    { label: "已接受", count: chapters.filter((chapter) => chapter.status === "accepted").length, icon: CheckCircle2 },
    { label: "生成中", count: chapters.filter((chapter) => chapter.status === "running").length, icon: RotateCcw },
  ];
}

function volumeLabelForChapter(volumeSections: VolumeSection[], chapter: ChapterPayload): string {
  const matched = volumeSections.find((section) =>
    section.chapters.some((item) => item.id === chapter.id && item.number === chapter.number),
  );
  if (!matched?.plan) {
    return "";
  }
  return volumeTitle(matched);
}

function chapterSubline(volumeSections: VolumeSection[], chapter: ChapterPayload): string {
  const volumeLabel = volumeLabelForChapter(volumeSections, chapter);
  const summary = chapter.summary || "未写入摘要";
  return volumeLabel ? `${volumeLabel} · ${summary}` : summary;
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

function clampedPositiveInt(value: string, min: number, max?: number): number {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return min;
  }
  const withMin = Math.max(min, parsed);
  return max === undefined ? withMin : Math.min(withMin, max);
}

function targetChapters(wordTargets: WordTargetsPayload): number {
  const chapterWordCount = Math.max(1, wordTargets.chapterWordCount);
  return Math.max(1, Math.ceil(wordTargets.targetWordCount / chapterWordCount));
}
