from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any

from mynovel.domain.models import Book, BookStatus, Canon, Chapter, ChapterStatus, RunTrace, VolumePlan
from mynovel.i18n import DEFAULT_LOCALE, t
from mynovel.word_target_views import render_word_target_form


@dataclass(frozen=True)
class WorkspaceTaskSummary:
    chapter: Chapter | None
    state: str
    title: str
    copy: str
    detail: str


def build_workspace_task_summary(
    chapter: Chapter | None,
    locale: str = DEFAULT_LOCALE,
) -> WorkspaceTaskSummary:
    if chapter is None:
        return WorkspaceTaskSummary(
            chapter=None,
            state="complete",
            title=t("workspace.focus_complete_title", locale),
            copy=t("workspace.focus_complete_copy", locale),
            detail=t("workspace.focus_detail_complete", locale),
        )
    if chapter.status in {ChapterStatus.AWAITING_REVIEW, ChapterStatus.NEEDS_REVISION}:
        return WorkspaceTaskSummary(
            chapter=chapter,
            state="review",
            title=t("workspace.focus_title_review", locale, number=chapter.number),
            copy=t("workspace.focus_copy_review", locale, number=chapter.number, title=chapter.title),
            detail=t("workspace.focus_detail_review", locale),
        )
    if chapter.status == ChapterStatus.RUNNING:
        return WorkspaceTaskSummary(
            chapter=chapter,
            state="running",
            title=t("workspace.focus_title_running", locale, number=chapter.number),
            copy=t("workspace.focus_copy_running", locale, number=chapter.number, title=chapter.title),
            detail=t("workspace.focus_detail_running", locale),
        )
    return WorkspaceTaskSummary(
        chapter=chapter,
        state="run",
        title=t("workspace.focus_title_run", locale, number=chapter.number),
        copy=t("workspace.focus_copy_run", locale, number=chapter.number, title=chapter.title),
        detail=t("workspace.focus_detail_run", locale),
    )


def render_workspace_focus_card(
    book: Book,
    chapters: list[Chapter],
    task: WorkspaceTaskSummary,
    canon: Canon | None,
    volume_plans: list[VolumePlan],
    locale: str = DEFAULT_LOCALE,
) -> str:
    accepted = len([chapter for chapter in chapters if chapter.status == ChapterStatus.ACCEPTED])
    review = len(
        [
            chapter
            for chapter in chapters
            if chapter.status in {ChapterStatus.AWAITING_REVIEW, ChapterStatus.NEEDS_REVISION}
        ]
    )
    running = len([chapter for chapter in chapters if chapter.status == ChapterStatus.RUNNING])
    return f"""
      <section class="main-panel workspace-focus-card">
        <p class="section-kicker">{t("workspace.current_task", locale)}</p>
        <div class="workspace-focus-head">
          <div>
            <h1>{html.escape(task.title)}</h1>
            <p>{html.escape(task.copy)}</p>
          </div>
          <span class="status-pill trusted">{t("book.status_locked" if canon else "trusted_state.not_written", locale)}</span>
        </div>
        <section class="workspace-current-task">
          <div>
            <strong>{t("workspace.task_prompt", locale)}</strong>
            <p>{html.escape(task.detail)}</p>
          </div>
          <div class="workspace-primary-action">{_render_workspace_primary_action(task, locale)}</div>
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
            <span>{html.escape(t("workspace.book_meta", locale, genre=book.genre, audience=book.audience))}</span>
          </div>
          <div class="workspace-foundation-grid">
            {_snapshot_card(t("trusted_state.world_rules", locale), _preview_value((canon.content if canon else {}).get("world_rules", []), locale))}
            {_snapshot_card(t("trusted_state.characters", locale), _preview_value((canon.content if canon else {}).get("characters", []), locale))}
            {_snapshot_card(t("trusted_state.foreshadowing", locale), _preview_value((canon.content if canon else {}).get("foreshadowing", []), locale))}
            {_snapshot_card(t("trusted_state.chapter_summaries", locale), _preview_value((canon.content if canon else {}).get("chapter_summaries", []), locale))}
          </div>
          {_render_volume_plan_snapshot(volume_plans, locale)}
        </section>
      </section>
"""


def render_workspace_result_sidebar(
    book: Book,
    task: WorkspaceTaskSummary,
    canon: Canon | None,
    traces: list[RunTrace],
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
          <div class="workspace-action-list">{_render_workspace_project_actions(book, locale)}</div>
        </section>
        <section class="workspace-result-section">
          <h2>{t("workspace.word_targets", locale)}</h2>
          {render_word_target_form(book)}
        </section>
        <section class="workspace-result-section">
          <h2>{t("batch.title", locale)}</h2>
          {_render_batch_action(book, task.chapter, locale)}
        </section>
      </aside>
"""


def _render_workspace_primary_action(task: WorkspaceTaskSummary, locale: str) -> str:
    chapter = task.chapter
    if chapter is None:
        return (
            '<a class="button secondary" href="/review">'
            f"{t('workspace.open_review_queue', locale)}</a>"
        )
    if task.state in {"review", "running"}:
        return f"<a class='button' href='/chapter/{chapter.id}'>{t('workspace.open_current_chapter', locale)}</a>"
    return f"""
      <form method="post" action="/run-chapter" class="compact-form">
        <input type="hidden" name="chapter_id" value="{chapter.id}">
        <button type="submit">{t("action.run_chapter", locale)}</button>
      </form>
"""


def _render_workspace_project_actions(book: Book, locale: str) -> str:
    return f"""
      <a class="button secondary" href="/book/{book.id}/state">{t("trusted_state.open", locale)}</a>
      <a class="button secondary" href="/book/{book.id}/quality">{t("quality.open", locale)}</a>
      <a class="button secondary" href="/book/{book.id}/export.md">{t("export.markdown", locale)}</a>
      <a class="button secondary" href="/book/{book.id}/export.json">{t("export.json", locale)}</a>
"""


def _render_batch_action(book: Book, chapter: Chapter | None, locale: str) -> str:
    if book.status == BookStatus.PAUSED:
        return f"<p>{t('batch.paused', locale)}</p>"
    if chapter is None or book.id is None:
        return f"<p>{t('dashboard.all_done', locale)}</p>"
    return f"""
      <form method="post" action="/run-chapter-batch" class="compact-form">
        <input type="hidden" name="book_id" value="{book.id}">
        <label>{t("batch.limit", locale)}<input name="limit" type="number" min="1" max="10" value="2"></label>
        <button type="submit">{t("batch.run", locale)}</button>
      </form>
"""


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
        detail_parts.append(_preview_value(plan.pacing_curve[0], locale))
    if plan.commitments:
        detail_parts.append(_preview_value(plan.commitments[0], locale))
    details = _join_preview_parts(detail_parts, locale)
    return f"""
      <article class="workspace-volume-plan">
        <strong>{t("workspace.volume_plan", locale)}</strong>
        <p>{html.escape(plan.title)} · {_preview_value(plan.core_conflict, locale)}</p>
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
        (t("trusted_state.world_rules", locale), _preview_value(content.get("world_rules", []), locale)),
        (t("trusted_state.characters", locale), _preview_value(content.get("characters", []), locale)),
        (t("trusted_state.foreshadowing", locale), _preview_value(content.get("foreshadowing", []), locale)),
        (t("trusted_state.chapter_summaries", locale), _preview_value(content.get("chapter_summaries", []), locale)),
    ]
    rows = "".join(
        f"<li><strong>{html.escape(title)}</strong><span>{value}</span></li>" for title, value in items
    )
    return f"<ul class='workspace-mini-list'>{rows}</ul>"


def _preview_value(value: Any, locale: str) -> str:
    if isinstance(value, list):
        visible = [item for item in value if item not in (None, "", [], {})]
        if not visible:
            return _empty_value(locale)
        return _join_preview_parts([_preview_value(item, locale) for item in visible[:2]], locale)
    if isinstance(value, dict):
        if str(value.get("trigger") or "").strip() and str(value.get("description") or "").strip():
            return _preview_pair(
                _preview_value(value["trigger"], locale),
                _preview_value(value["description"], locale),
                locale,
            )
        parts = []
        for key, item in value.items():
            if key in {"target_section", "changed_sections", "blocked_sections", "updated_at", "accepted_at"}:
                continue
            parts.append(_preview_pair(_label_key(key, locale), _preview_value(item, locale), locale))
        return _join_preview_parts(parts, locale) if parts else _empty_value(locale)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return _empty_value(locale)
        return html.escape(text)
    if value in (None, ""):
        return _empty_value(locale)
    return html.escape(str(value))


def _empty_value(locale: str) -> str:
    return html.escape(t("workspace.empty_value", locale))


def _join_preview_parts(parts: list[str], locale: str) -> str:
    visible = [part for part in parts if part]
    if not visible:
        return ""
    return t("workspace.preview_joiner", locale).join(visible)


def _preview_pair(left: str, right: str, locale: str) -> str:
    return t("workspace.preview_pair", locale, left=left, right=right)


def _label_key(key: object, locale: str) -> str:
    names = {
        "background": "workspace.label.background",
        "change": "workspace.label.change",
        "chapter": "workspace.label.chapter",
        "content": "workspace.label.content",
        "description": "workspace.label.description",
        "detail": "workspace.label.detail",
        "direction": "workspace.label.direction",
        "goal": "workspace.label.goal",
        "name": "workspace.label.name",
        "rules": "workspace.label.rules",
        "summary": "workspace.label.summary",
        "title": "workspace.label.title",
        "trigger": "workspace.label.trigger",
    }
    translation_key = names.get(str(key))
    if translation_key is None:
        return html.escape(str(key))
    return t(translation_key, locale)


def _trace_stage_label(stage: str, locale: str) -> str:
    labels = {
        "chapter_pipeline": t("workspace.trace_chapter_pipeline", locale),
        "accept_chapter": t("workspace.trace_accept_chapter", locale),
    }
    return labels.get(stage, stage)
