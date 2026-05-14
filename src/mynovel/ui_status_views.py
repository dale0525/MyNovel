from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Sequence

from mynovel.domain.models import Book, Chapter, ChapterStatus
from mynovel.i18n import DEFAULT_LOCALE, t
from mynovel.workspace_views import build_workspace_task_summary


@dataclass(frozen=True)
class StatusStage:
    key: str
    label: str
    title: str
    detail: str
    state: str = "pending"


@dataclass(frozen=True)
class ReviewSemantics:
    can_accept: bool
    inspector_title: str
    completion_fallback: str
    state_empty_detail: str
    current_title: str
    current_detail: str
    ai_title: str
    ai_detail: str
    decision_title: str
    decision_detail: str
    decision_empty: str
    action_copy: str


def build_global_status_stages(locale: str = DEFAULT_LOCALE) -> tuple[StatusStage, ...]:
    return (
        StatusStage(
            key="current",
            label=t("status_strip.current_label", locale),
            title=t("status_strip.current_title", locale),
            detail=t("status_strip.current_detail", locale),
            state="current",
        ),
        StatusStage(
            key="ai",
            label=t("status_strip.ai_label", locale),
            title=t("status_strip.ai_title", locale),
            detail=t("status_strip.ai_detail", locale),
            state="working",
        ),
        StatusStage(
            key="decision",
            label=t("status_strip.decision_label", locale),
            title=t("status_strip.decision_title", locale),
            detail=t("status_strip.decision_detail", locale),
            state="decision",
        ),
    )


def build_workspace_status_stages(
    book: Book,
    chapter: Chapter | None,
    locale: str = DEFAULT_LOCALE,
) -> tuple[StatusStage, ...]:
    task = build_workspace_task_summary(chapter, locale)
    return (
        StatusStage(
            key="current-task",
            label=t("status_strip.current_label", locale),
            title=task.title,
            detail=task.detail,
            state="current",
        ),
        StatusStage(
            key="ai-progress",
            label=t("status_strip.ai_label", locale),
            title=t("status_strip.workspace_ai_title", locale),
            detail=t("status_strip.workspace_ai_detail", locale, title=book.title),
            state="working",
        ),
        StatusStage(
            key="decision",
            label=t("status_strip.decision_label", locale),
            title=t("status_strip.workspace_decision_title", locale),
            detail=t("status_strip.workspace_decision_detail", locale),
            state="decision",
        ),
    )


def build_running_chapter_status_stages(
    chapter: Chapter,
    locale: str = DEFAULT_LOCALE,
) -> tuple[StatusStage, ...]:
    return (
        StatusStage(
            key="current-task",
            label=t("status_strip.current_label", locale),
            title=t("running_board.status_strip_current", locale, number=chapter.number),
            detail=t("running_board.status_strip_current_detail", locale),
            state="current",
        ),
        StatusStage(
            key="ai-progress",
            label=t("status_strip.ai_label", locale),
            title=t("running_board.status_strip_ai_title", locale),
            detail=t("running_board.status_strip_ai_detail", locale),
            state="working",
        ),
        StatusStage(
            key="decision",
            label=t("status_strip.decision_label", locale),
            title=t("running_board.status_strip_decision_title", locale),
            detail=t("running_board.status_strip_decision_detail", locale),
            state="decision",
        ),
    )


def build_review_semantics(
    chapter: Chapter,
    locale: str = DEFAULT_LOCALE,
) -> ReviewSemantics:
    if chapter.status == ChapterStatus.NEEDS_REVISION:
        return ReviewSemantics(
            can_accept=False,
            inspector_title=t("review.inspector_revision_title", locale),
            completion_fallback=t(
                "review.summary_completion_revision_fallback",
                locale,
                number=chapter.number,
            ),
            state_empty_detail=t("review.state_panel_empty_revision", locale),
            current_title=t("status_strip.review_revision_current_title", locale),
            current_detail=t("status_strip.review_revision_current_detail", locale),
            ai_title=t("status_strip.review_revision_ai_title", locale),
            ai_detail=t("status_strip.review_revision_ai_detail", locale),
            decision_title=t("status_strip.review_revision_decision_title", locale),
            decision_detail=t("status_strip.review_revision_decision_detail", locale),
            decision_empty=t("review.summary_decisions_revision_empty", locale),
            action_copy=t("review.decision_note_revision_copy", locale),
        )
    return ReviewSemantics(
        can_accept=True,
        inspector_title=t("review.inspector_accept_title", locale),
        completion_fallback=t("review.summary_completion_fallback", locale, number=chapter.number),
        state_empty_detail=t("review.state_panel_empty_accept", locale),
        current_title=t("status_strip.review_current_title", locale),
        current_detail=t("status_strip.review_current_detail", locale),
        ai_title=t("status_strip.review_ai_title", locale),
        ai_detail=t("status_strip.review_ai_detail", locale),
        decision_title=t("status_strip.review_decision_title", locale),
        decision_detail=t("status_strip.review_decision_detail", locale),
        decision_empty=t("review.summary_decisions_empty", locale),
        action_copy=t("review.decision_note_copy", locale),
    )


def build_review_status_stages(
    chapter: Chapter,
    locale: str = DEFAULT_LOCALE,
) -> tuple[StatusStage, ...]:
    semantics = build_review_semantics(chapter, locale)
    return (
        StatusStage(
            key="current-task",
            label=t("status_strip.current_label", locale),
            title=semantics.current_title,
            detail=semantics.current_detail,
            state="current",
        ),
        StatusStage(
            key="ai-progress",
            label=t("status_strip.ai_label", locale),
            title=semantics.ai_title,
            detail=semantics.ai_detail,
            state="working",
        ),
        StatusStage(
            key="decision",
            label=t("status_strip.decision_label", locale),
            title=semantics.decision_title,
            detail=semantics.decision_detail,
            state="decision",
        ),
    )


def render_global_status_strip(
    locale: str = DEFAULT_LOCALE,
    stages: Sequence[StatusStage] | None = None,
) -> str:
    items = stages or build_global_status_stages(locale)
    return (
        f'<section class="global-status-strip" aria-label="{html.escape(t("status_strip.aria_label", locale), quote=True)}">'
        f'{"".join(render_status_stage(stage) for stage in items)}'
        "</section>"
    )


def render_workspace_status_strip(
    book: Book,
    chapter: Chapter | None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    return render_global_status_strip(locale, build_workspace_status_stages(book, chapter, locale))


def render_running_chapter_status_strip(
    chapter: Chapter,
    locale: str = DEFAULT_LOCALE,
) -> str:
    return render_global_status_strip(locale, build_running_chapter_status_stages(chapter, locale))


def render_review_status_strip(
    chapter: Chapter,
    locale: str = DEFAULT_LOCALE,
) -> str:
    return render_global_status_strip(locale, build_review_status_stages(chapter, locale))


def render_status_stage(stage: StatusStage) -> str:
    return (
        f'<article class="status-stage {html.escape(stage.state, quote=True)}" data-stage="{html.escape(stage.key, quote=True)}">'
        f'<p class="status-stage-label">{html.escape(stage.label)}</p>'
        f"<strong>{html.escape(stage.title)}</strong>"
        f"<span>{html.escape(stage.detail)}</span>"
        "</article>"
    )
