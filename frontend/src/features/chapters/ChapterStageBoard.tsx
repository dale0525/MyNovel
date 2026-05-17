import type { ChapterStageSlotPayload, RunTracePayload } from "@/lib/types";

type ChapterStageBoardProps = {
  slots: ChapterStageSlotPayload[];
  traces: RunTracePayload[];
};

export function ChapterStageBoard({ slots, traces }: ChapterStageBoardProps) {
  const recentTrace = traces.at(-1);

  return (
    <section className="chapter-stage-board workbench-panel" aria-labelledby="chapter-stage-board-title">
      <div className="workspace-section-head">
        <div>
          <p className="eyebrow">运行流程</p>
          <h2 id="chapter-stage-board-title">生产阶段</h2>
        </div>
        <span>{recentTrace ? `最近：${recentTrace.stage}` : "暂无运行记录"}</span>
      </div>
      <div className="chapter-stage-chain">
        {slots.map((slot) => (
          <article
            className={slot.ready ? "chapter-stage-card is-ready" : "chapter-stage-card"}
            data-slot={slot.key}
            key={slot.key}
          >
            <span>{slot.ready ? "已产出" : "待产出"}</span>
            <strong>{slot.label}</strong>
            <p>{slot.summary || "待产出"}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
