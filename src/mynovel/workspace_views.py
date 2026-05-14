from __future__ import annotations

import html
from typing import Any

from mynovel.domain.models import Book, Canon, Chapter, ChapterStatus, RunTrace, VolumePlan
from mynovel.i18n import DEFAULT_LOCALE, t


def render_workspace_focus_card(
    book: Book,
    chapters: list[Chapter],
    active_chapter: Chapter | None,
    canon: Canon | None,
    volume_plans: list[VolumePlan],
    primary_action: str,
    locale: str = DEFAULT_LOCALE,
) -> str:
    accepted = len([chapter for chapter in chapters if chapter.status == ChapterStatus.ACCEPTED])
    review = len(
        [chapter for chapter in chapters if chapter.status in {ChapterStatus.AWAITING_REVIEW, ChapterStatus.NEEDS_REVISION}]
    )
    running = len([chapter for chapter in chapters if chapter.status == ChapterStatus.RUNNING])
    title, copy = _focus_headline(active_chapter, locale)
    return f"""
      <section class="main-panel workspace-focus-card">
        <p class="section-kicker">{t("workspace.current_task", locale)}</p>
        <div class="workspace-focus-head">
          <div>
            <h1>{html.escape(title)}</h1>
            <p>{html.escape(copy)}</p>
          </div>
          <span class="status-pill trusted">{t("book.status_locked" if canon else "trusted_state.not_written", locale)}</span>
        </div>
        <section class="workspace-current-task">
          <div>
            <strong>{t("workspace.task_prompt", locale)}</strong>
            <p>{_focus_detail(active_chapter, locale)}</p>
          </div>
          <div class="workspace-primary-action">{primary_action}</div>
        </section>
        <div class="workspace-kpi-grid">
          <article><strong>{accepted}</strong><span>{t("dashboard.accepted", locale)}</span></article>
          <article><strong>{review}</strong><span>{t("dashboard.reviewing", locale)}</span></article>
          <article><strong>{running}</strong><span>{t("chapter.status_running", locale)}</span></article>
          <article><strong>{len(chapters)}</strong><span>{t("dashboard.chapter_plan", locale)}</span></article>
        </div>
        <section class="workspace-foundation-panel">
          <div class="workspace-section-head">
            <h2>{t("workspace.focus_inputs", locale)}</h2>
            <span>{html.escape(book.genre)} · {html.escape(book.audience)}</span>
          </div>
          <div class="workspace-foundation-grid">
            {_snapshot_card(t("trusted_state.world_rules", locale), _preview_value((canon.content if canon else {}).get("world_rules", [])))}
            {_snapshot_card(t("trusted_state.characters", locale), _preview_value((canon.content if canon else {}).get("characters", [])))}
            {_snapshot_card(t("trusted_state.foreshadowing", locale), _preview_value((canon.content if canon else {}).get("foreshadowing", [])))}
            {_snapshot_card(t("trusted_state.chapter_summaries", locale), _preview_value((canon.content if canon else {}).get("chapter_summaries", [])))}
          </div>
          {_render_volume_plan_snapshot(volume_plans, locale)}
        </section>
      </section>
"""


def render_workspace_result_sidebar(
    canon: Canon | None,
    traces: list[RunTrace],
    project_actions: str,
    word_target_form: str,
    batch_action: str,
    locale: str = DEFAULT_LOCALE,
) -> str:
    return f"""
      <aside class="right-panel workspace-result-sidebar">
        <section class="workspace-result-section">
          <div class="workspace-section-head">
            <h2>{t("workspace.recent_progress", locale)}</h2>
            <span>{t("workspace.ai_progress", locale)}</span>
          </div>
          {_render_trace_feed(traces, locale)}
        </section>
        <section class="workspace-result-section">
          <div class="workspace-section-head">
            <h2>{t("workspace.foundation_summary", locale)}</h2>
            <span>{t("trusted_state.current_version", locale, version=canon.version if canon else 0)}</span>
          </div>
          {_render_foundation_summary(canon, locale)}
        </section>
        <section class="workspace-result-section">
          <h2>{t("workspace.project_actions", locale)}</h2>
          <div class="workspace-action-list">{project_actions}</div>
        </section>
        <section class="workspace-result-section">
          <h2>{t("workspace.word_targets", locale)}</h2>
          {word_target_form}
        </section>
        <section class="workspace-result-section">
          <h2>{t("batch.title", locale)}</h2>
          {batch_action}
        </section>
      </aside>
"""


def _focus_headline(active_chapter: Chapter | None, locale: str) -> tuple[str, str]:
    if active_chapter is None:
        return t("workspace.focus_complete_title", locale), t("workspace.focus_complete_copy", locale)
    if active_chapter.status in {ChapterStatus.AWAITING_REVIEW, ChapterStatus.NEEDS_REVISION}:
        return (
            t("workspace.focus_title_review", locale, number=active_chapter.number),
            t("workspace.focus_copy_review", locale, number=active_chapter.number, title=active_chapter.title),
        )
    if active_chapter.status == ChapterStatus.RUNNING:
        return (
            t("workspace.focus_title_running", locale, number=active_chapter.number),
            t("workspace.focus_copy_running", locale, number=active_chapter.number, title=active_chapter.title),
        )
    return (
        t("workspace.focus_title_run", locale, number=active_chapter.number),
        t("workspace.focus_copy_run", locale, number=active_chapter.number, title=active_chapter.title),
    )


def _focus_detail(active_chapter: Chapter | None, locale: str) -> str:
    if active_chapter is None:
        return t("workspace.focus_detail_complete", locale)
    if active_chapter.status == ChapterStatus.RUNNING:
        return t("workspace.focus_detail_running", locale)
    if active_chapter.status in {ChapterStatus.AWAITING_REVIEW, ChapterStatus.NEEDS_REVISION}:
        return t("workspace.focus_detail_review", locale)
    return t("workspace.focus_detail_run", locale)


def _snapshot_card(title: str, content: str) -> str:
    return (
        '<article class="workspace-snapshot-card">'
        f"<strong>{html.escape(title)}</strong>"
        f"<p>{content}</p>"
        "</article>"
    )


def _render_volume_plan_snapshot(volume_plans: list[VolumePlan], locale: str) -> str:
    if not volume_plans:
        return ""
    plan = volume_plans[0]
    detail_parts = []
    if plan.pacing_curve:
        detail_parts.append(_preview_value(plan.pacing_curve[0]))
    if plan.commitments:
        detail_parts.append(_preview_value(plan.commitments[0]))
    details = "；".join(detail_parts)
    return f"""
      <article class="workspace-volume-plan">
        <strong>{t("workspace.volume_plan", locale)}</strong>
        <p>{html.escape(plan.title)} · {html.escape(_preview_value(plan.core_conflict))}</p>
        {f"<p>{details}</p>" if details else ""}
      </article>
"""


def _render_trace_feed(traces: list[RunTrace], locale: str) -> str:
    if not traces:
        return f"<p>{t('dashboard.no_trace', locale)}</p>"
    items = []
    for trace in traces[-4:][::-1]:
        created = trace.created_at.strftime("%H:%M")
        items.append(
            "<article class='workspace-trace-row'>"
            f"<strong>{html.escape(created)}</strong>"
            f"<span>{html.escape(_trace_stage_label(trace.stage, locale))}</span>"
            "</article>"
        )
    return "".join(items)


def _render_foundation_summary(canon: Canon | None, locale: str) -> str:
    if canon is None:
        return f"<p>{t('trusted_state.missing', locale)}</p>"
    content = canon.content
    items = [
        (t("trusted_state.world_rules", locale), _preview_value(content.get("world_rules", []))),
        (t("trusted_state.characters", locale), _preview_value(content.get("characters", []))),
        (t("trusted_state.foreshadowing", locale), _preview_value(content.get("foreshadowing", []))),
        (t("trusted_state.chapter_summaries", locale), _preview_value(content.get("chapter_summaries", []))),
    ]
    rows = "".join(
        f"<li><strong>{html.escape(title)}</strong><span>{value}</span></li>" for title, value in items
    )
    return f"<ul class='workspace-mini-list'>{rows}</ul>"


def _preview_value(value: Any) -> str:
    if isinstance(value, list):
        visible = [item for item in value if item not in (None, "", [], {})]
        if not visible:
            return "—"
        return "；".join(_preview_value(item) for item in visible[:2])
    if isinstance(value, dict):
        if str(value.get("trigger") or "").strip() and str(value.get("description") or "").strip():
            trigger = html.escape(str(value["trigger"]))
            description = html.escape(str(value["description"]))
            return f"{trigger}：{description}"
        parts = []
        for key, item in value.items():
            if key in {"target_section", "changed_sections", "blocked_sections", "updated_at", "accepted_at"}:
                continue
            label = _label_key(key)
            parts.append(f"{label}：{_preview_value(item)}")
        return "；".join(parts) if parts else "—"
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "—"
        return html.escape(text)
    if value in (None, ""):
        return "—"
    return html.escape(str(value))


def _label_key(key: object) -> str:
    return {
        "background": "背景",
        "change": "变化",
        "chapter": "章节",
        "content": "摘要",
        "description": "说明",
        "detail": "内容",
        "direction": "方向",
        "goal": "目标",
        "name": "名称",
        "rules": "规则",
        "summary": "摘要",
        "title": "标题",
        "trigger": "触发",
    }.get(str(key), str(key))


def _trace_stage_label(stage: str, locale: str) -> str:
    labels = {
        "chapter_pipeline": t("workspace.trace_chapter_pipeline", locale),
        "accept_chapter": t("workspace.trace_accept_chapter", locale),
    }
    return labels.get(stage, stage)
