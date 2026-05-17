import { type FormEvent, useState } from "react";
import { BookMarked, ChevronDown, ListTree, PencilLine, WandSparkles } from "lucide-react";

import { AiStreamFeedback } from "@/components/feedback/AiStreamFeedback";
import { AiWaitingIndicator } from "@/components/feedback/AiWaitingIndicator";
import type { BookResponse, ChapterPayload } from "@/lib/types";

type WorkspaceAction = "run-batch" | "word-targets" | "volume-outline" | "volume-revision";

export type VolumeRevisionScope = "all_volumes" | "all_chapters" | "volume_summary" | "volume_chapters";

export type VolumeRevisionPayload = {
  scope: VolumeRevisionScope;
  volumeNumber?: number;
  revisionNotes: string;
};

export type VolumeSection = {
  key: string;
  plan: BookResponse["volumePlans"][number] | null;
  chapters: ChapterPayload[];
};

export function ProjectVolumeOutlineView({
  actionBusy,
  bookId,
  selectedVolumeKey,
  setSelectedVolumeKey,
  streamAction,
  streamSnippets,
  volumeSections,
  wordTargets,
  onGenerateVolumeOutline,
  onReviseVolumeOutline,
}: {
  actionBusy: WorkspaceAction | null;
  bookId: number;
  selectedVolumeKey: string | null;
  setSelectedVolumeKey: (value: string | null) => void;
  streamAction: WorkspaceAction | null;
  streamSnippets: string[];
  volumeSections: VolumeSection[];
  wordTargets: BookResponse["wordTargets"];
  onGenerateVolumeOutline: () => Promise<void>;
  onReviseVolumeOutline: (payload: VolumeRevisionPayload) => Promise<void>;
}) {
  const expandedVolumeKey = selectedVolumeKey;
  const plannedChapterCount = volumeSections.reduce((total, section) => total + section.chapters.length, 0);
  const targetChapterCount = targetChapters(wordTargets);
  const missingChapterCount = Math.max(0, targetChapterCount - plannedChapterCount);

  return (
    <section className="workspace-result-section workspace-volume-workbench" aria-labelledby="volume-outline-title">
      <div className="workspace-section-head workspace-volume-head">
        <div>
          <p className="eyebrow">卷纲规划</p>
          <h2 id="volume-outline-title">卷纲</h2>
        </div>
        <div className="workspace-volume-head__actions">
          {selectedVolumeKey ? (
            <button
              className="workbench-secondary-button"
              disabled={actionBusy !== null}
              type="button"
              onClick={() => setSelectedVolumeKey(null)}
            >
              收起全部
            </button>
          ) : null}
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
      </div>

      <div className="workspace-volume-metrics" aria-label="卷纲目标覆盖">
        <MetricCell label="目标章数" value={`${targetChapterCount} 章`} />
        <MetricCell label="已规划" value={`${plannedChapterCount} 章`} />
        <MetricCell label="规划缺口" value={`${missingChapterCount} 章`} tone={missingChapterCount > 0 ? "warning" : "ready"} />
        <MetricCell label="单章目标" value={`${wordTargets.chapterWordCount} 字`} />
      </div>

      <AiStreamFeedback snippets={streamAction === "volume-outline" ? streamSnippets : []} />

      <AllVolumesRevisionPanel
        actionBusy={actionBusy}
        streamSnippets={streamAction === "volume-revision" ? streamSnippets : []}
        onSubmit={onReviseVolumeOutline}
      />

      <section className="workspace-volume-rows" aria-label="卷列表">
        {volumeSections.map((section, index) => (
          <VolumeRow
            actionBusy={actionBusy}
            bookId={bookId}
            chapterWordCount={wordTargets.chapterWordCount}
            expanded={expandedVolumeKey === section.key}
            index={index}
            key={section.key}
            section={section}
            streamSnippets={streamAction === "volume-revision" ? streamSnippets : []}
            onRevisionSubmit={onReviseVolumeOutline}
            onToggle={() => setSelectedVolumeKey(expandedVolumeKey === section.key ? null : section.key)}
          />
        ))}
      </section>
    </section>
  );
}

function MetricCell({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "ready" | "warning";
}) {
  return (
    <div className={`workspace-volume-metric workspace-volume-metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AllVolumesRevisionPanel({
  actionBusy,
  streamSnippets,
  onSubmit,
}: {
  actionBusy: WorkspaceAction | null;
  streamSnippets: string[];
  onSubmit: (payload: VolumeRevisionPayload) => Promise<void>;
}) {
  const [revisionNotes, setRevisionNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const trimmedNotes = revisionNotes.trim();
  const canSubmit = actionBusy === null && trimmedNotes.length > 0;

  function submitRevision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    setIsSubmitting(true);
    void onSubmit({ scope: "all_volumes", revisionNotes: trimmedNotes }).finally(() => setIsSubmitting(false));
  }

  return (
    <section className="workspace-volume-global-revision" aria-labelledby="volume-global-revision-title">
      <form className="chapter-action-form workspace-volume-revision-form" onSubmit={submitRevision}>
        <label htmlFor="volume-global-revision-notes">
          <span id="volume-global-revision-title">所有卷修改意见</span>
          <textarea
            disabled={actionBusy !== null || isSubmitting}
            id="volume-global-revision-notes"
            placeholder="例如：重排全书卷名，让第二卷转向更强的悬疑升级。"
            rows={4}
            value={revisionNotes}
            onChange={(event) => setRevisionNotes(event.target.value)}
          />
        </label>
        <div className="workspace-volume-revision-actions">
          <button className="workbench-action-button" disabled={!canSubmit || isSubmitting} type="submit">
            {isSubmitting ? (
              <AiWaitingIndicator label="修订卷纲中..." variant="inline" />
            ) : (
              <>
                <PencilLine aria-hidden="true" size={17} />
                根据已生产章节修改所有卷
              </>
            )}
          </button>
          <AiStreamFeedback snippets={streamSnippets} />
        </div>
      </form>
    </section>
  );
}

function VolumeRow({
  actionBusy,
  bookId,
  chapterWordCount,
  expanded,
  index,
  section,
  streamSnippets,
  onRevisionSubmit,
  onToggle,
}: {
  actionBusy: WorkspaceAction | null;
  bookId: number;
  chapterWordCount: number;
  expanded: boolean;
  index: number;
  section: VolumeSection;
  streamSnippets: string[];
  onRevisionSubmit: (payload: VolumeRevisionPayload) => Promise<void>;
  onToggle: () => void;
}) {
  const detailsId = `volume-row-${section.key}`;
  const volumeWords = section.chapters.length * chapterWordCount;
  const summary = `${volumeTitle(section)} ${section.chapters.length} 章 ${volumeStatusSummary(section.chapters)}`;

  return (
    <article className={expanded ? "workspace-volume-row is-expanded" : "workspace-volume-row"}>
      <header className="workspace-volume-row__header">
        <button
          aria-controls={detailsId}
          aria-expanded={expanded}
          aria-label={summary}
          className="workspace-volume-row__summary"
          onClick={onToggle}
          type="button"
        >
          <span className="workspace-volume-row__headline" aria-hidden="true">
            <strong>{volumeTitle(section)}</strong>
            <span>{chapterNumberRange(section.chapters)}</span>
            <span>{section.chapters.length} 章</span>
            <span>{volumeStatusSummary(section.chapters)}</span>
          </span>
          <ChevronDown aria-hidden="true" className="workspace-volume-row__chevron" size={20} />
        </button>
      </header>

      {expanded ? (
        <div className="workspace-volume-row__details" id={detailsId}>
          <VolumeSummary
            chapterWordCount={chapterWordCount}
            index={index}
            section={section}
            volumeWords={volumeWords}
          />
          {section.plan ? <VolumePlanHighlights plan={section.plan} /> : null}
          <VolumeChapterList bookId={bookId} chapters={section.chapters} />
          <SingleVolumeRevisionPanel
            actionBusy={actionBusy}
            section={section}
            streamSnippets={streamSnippets}
            onSubmit={onRevisionSubmit}
          />
        </div>
      ) : null}
    </article>
  );
}

function VolumeSummary({
  chapterWordCount,
  index,
  section,
  volumeWords,
}: {
  chapterWordCount: number;
  index: number;
  section: VolumeSection;
  volumeWords: number;
}) {
  return (
    <section className="workspace-volume-detail" aria-label={`${volumeTitle(section)}概括`}>
      <header className="workspace-volume-detail__head">
        <div>
          <p className="eyebrow">卷概括</p>
          <strong>核心冲突</strong>
          <p>{section.plan?.coreConflict || "这一组章节还没有绑定卷纲。"}</p>
        </div>
        <span>第 {index + 1} 项</span>
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
          <dt>状态</dt>
          <dd>{volumeStatusSummary(section.chapters)}</dd>
        </div>
      </dl>
    </section>
  );
}

function VolumeChapterList({ bookId, chapters }: { bookId: number; chapters: ChapterPayload[] }) {
  if (!chapters.length) {
    return <p className="workspace-volume-empty">这一卷还没有章节规划。</p>;
  }

  return (
    <ol className="workspace-volume-chapter-list" aria-label="本卷章节列表">
      {chapters.map((chapter) => (
        <li key={chapter.id ?? chapter.number}>
          <span className="workspace-volume-chapter-number">第 {chapter.number} 章</span>
          <div>
            {chapter.id === null || chapter.id === undefined ? (
              <strong>第 {chapter.number} 章 · {chapter.title}</strong>
            ) : (
              <a className="workspace-mini-list-link" href={projectChapterHref(bookId, chapter)}>
                第 {chapter.number} 章 · {chapter.title}
              </a>
            )}
            <small>{chapter.summary || "未写入摘要"}</small>
          </div>
          <span className={`workspace-chapter-status workspace-chapter-status--${chapter.status}`}>
            {chapterStatusLabel(chapter.status)} · {chapter.wordCount} 字
          </span>
        </li>
      ))}
    </ol>
  );
}

function SingleVolumeRevisionPanel({
  actionBusy,
  section,
  streamSnippets,
  onSubmit,
}: {
  actionBusy: WorkspaceAction | null;
  section: VolumeSection;
  streamSnippets: string[];
  onSubmit: (payload: VolumeRevisionPayload) => Promise<void>;
}) {
  const [scope, setScope] = useState<Extract<VolumeRevisionScope, "volume_summary" | "volume_chapters">>("volume_chapters");
  const [revisionNotes, setRevisionNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const targetVolume = section.plan ?? null;
  const trimmedNotes = revisionNotes.trim();
  const canSubmit = actionBusy === null && trimmedNotes.length > 0 && targetVolume !== null;

  function submitRevision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    setIsSubmitting(true);
    void onSubmit({ scope, volumeNumber: targetVolume.volumeNumber, revisionNotes: trimmedNotes }).finally(() => setIsSubmitting(false));
  }

  return (
    <section className="workspace-volume-revision" aria-label={`${volumeTitle(section)}修订`}>
      <form className="chapter-action-form workspace-volume-revision-form" onSubmit={submitRevision}>
        <label htmlFor={`volume-${section.key}-revision-notes`}>
          这一卷修改意见
          <textarea
            disabled={actionBusy !== null || isSubmitting || targetVolume === null}
            id={`volume-${section.key}-revision-notes`}
            placeholder="例如：第二章提前设局，第三章把反派压力推到台前。"
            rows={4}
            value={revisionNotes}
            onChange={(event) => setRevisionNotes(event.target.value)}
          />
        </label>
        <div className="workspace-volume-row-revision-controls">
          <div className="workspace-revision-scope" role="group" aria-label="这一卷修订范围">
            <button
              aria-pressed={scope === "volume_summary"}
              disabled={actionBusy !== null || isSubmitting || targetVolume === null}
              type="button"
              onClick={() => setScope("volume_summary")}
            >
              <BookMarked aria-hidden="true" size={16} />
              概括
            </button>
            <button
              aria-pressed={scope === "volume_chapters"}
              disabled={actionBusy !== null || isSubmitting || targetVolume === null}
              type="button"
              onClick={() => setScope("volume_chapters")}
            >
              <ListTree aria-hidden="true" size={16} />
              章节
            </button>
          </div>
          <button className="workbench-action-button" disabled={!canSubmit || isSubmitting} type="submit">
            {isSubmitting ? (
              <AiWaitingIndicator label="修订卷纲中..." variant="inline" />
            ) : (
              <>
                <PencilLine aria-hidden="true" size={17} />
                让 AI 修改这一卷
              </>
            )}
          </button>
          <AiStreamFeedback snippets={streamSnippets} />
        </div>
      </form>
    </section>
  );
}

function VolumePlanHighlights({ plan }: { plan: BookResponse["volumePlans"][number] }) {
  const groups = [
    { label: "节奏", items: compactPlanItems(plan.pacingCurve) },
    { label: "关键转折", items: compactPlanItems(plan.keyTurns) },
    { label: "兑现", items: compactPlanItems(plan.payoffDistribution) },
    { label: "承诺", items: compactPlanItems(plan.commitments) },
  ].filter((group) => group.items.length > 0);

  if (groups.length === 0) {
    return null;
  }

  return (
    <dl className="workspace-volume-highlights" aria-label="卷纲要点">
      {groups.map((group) => (
        <div key={group.label}>
          <dt>{group.label}</dt>
          <dd>
            {group.items.map((item, index) => (
              <span key={`${group.label}-${index}-${item}`}>{item}</span>
            ))}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function volumePlanSections(
  volumePlans: BookResponse["volumePlans"],
  chapters: ChapterPayload[],
): VolumeSection[] {
  const sortedChapters = [...chapters].sort((left, right) => left.number - right.number);
  const plannedVolumeNumbers = new Set(volumePlans.map((plan) => plan.volumeNumber));
  if (volumePlans.length === 0) {
    return [{ key: "unassigned", plan: null, chapters: sortedChapters }];
  }

  const plannedSections = [...volumePlans]
    .sort((left, right) => left.volumeNumber - right.volumeNumber)
    .map((plan) => {
      const matchedChapters = sortedChapters.filter(
        (chapter) => {
          const volumeNumber = chapterVolumeNumber(chapter, plannedVolumeNumbers);
          return volumeNumber === plan.volumeNumber;
        },
      );
      return {
        key: String(plan.id ?? plan.volumeNumber),
        plan,
        chapters: matchedChapters,
      };
    });
  const unassignedChapters = sortedChapters.filter((chapter) => {
    const volumeNumber = chapterVolumeNumber(chapter, plannedVolumeNumbers);
    return volumeNumber === null || !plannedVolumeNumbers.has(volumeNumber);
  });
  return unassignedChapters.length
    ? [...plannedSections, { key: "unassigned", plan: null, chapters: unassignedChapters }]
    : plannedSections;
}

function chapterVolumeNumber(chapter: ChapterPayload, plannedVolumeNumbers?: Set<number>): number | null {
  if (typeof chapter.volumeNumber === "number" && Number.isFinite(chapter.volumeNumber)) {
    const volumeNumber = Math.trunc(chapter.volumeNumber);
    return volumeNumber > 0 ? volumeNumber : null;
  }
  if (plannedVolumeNumbers?.has(1) && chapter.number >= 1 && chapter.number <= 10) {
    return 1;
  }
  return null;
}

export function volumeTitle(section: VolumeSection): string {
  if (section.plan) {
    const fallback = volumeNumberLabel(section.plan.volumeNumber);
    const title = String(section.plan.title || "").trim();
    if (!title || isGenericVolumeTitle(title, section.plan.volumeNumber)) {
      const defaultTitle = defaultVolumeTitle(section.plan.volumeNumber);
      return defaultTitle ? `${fallback} · ${defaultTitle}` : fallback;
    }
    return `${fallback} · ${title}`;
  }
  return "未分卷章节";
}

function volumeNumberLabel(volumeNumber: number): string {
  const chineseNumbers = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"];
  if (volumeNumber > 0 && volumeNumber <= 10) {
    return `第${chineseNumbers[volumeNumber]}卷`;
  }
  return `第 ${volumeNumber} 卷`;
}

function isGenericVolumeTitle(title: string, volumeNumber: number): boolean {
  const normalized = title.replace(/\s+/g, "");
  return new Set([
    `第${volumeNumber}卷`,
    volumeNumberLabel(volumeNumber).replace(/\s+/g, ""),
  ]).has(normalized);
}

function defaultVolumeTitle(volumeNumber: number): string {
  return volumeNumber === 1 ? "开篇卷" : "";
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

function targetChapters(wordTargets: BookResponse["wordTargets"]): number {
  const chapterWordCount = Math.max(1, wordTargets.chapterWordCount);
  return Math.max(1, Math.ceil(wordTargets.targetWordCount / chapterWordCount));
}

function projectChapterHref(bookId: number, chapter: ChapterPayload): string {
  return `/books/${bookId}/chapters/${chapter.id}`;
}

function compactPlanItems(items: unknown[]): string[] {
  return items.map(planItemLabel).filter((item) => item.length > 0).slice(0, 3);
}

function planItemLabel(item: unknown): string {
  if (typeof item === "string") {
    return item.trim();
  }
  if (typeof item === "number" || typeof item === "boolean") {
    return String(item);
  }
  if (!isRecord(item)) {
    return "";
  }
  const firstValue = Object.values(item).find(
    (value) => typeof value === "string" || typeof value === "number" || typeof value === "boolean",
  );
  return firstValue === undefined ? "" : String(firstValue).trim();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
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
