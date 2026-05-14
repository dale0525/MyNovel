from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Sequence

from mynovel.i18n import DEFAULT_LOCALE, t


@dataclass(frozen=True)
class StatusStage:
    key: str
    label: str
    title: str
    detail: str
    state: str = "pending"


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


def render_status_stage(stage: StatusStage) -> str:
    return (
        f'<article class="status-stage {html.escape(stage.state, quote=True)}" data-stage="{html.escape(stage.key, quote=True)}">'
        f'<p class="status-stage-label">{html.escape(stage.label)}</p>'
        f"<strong>{html.escape(stage.title)}</strong>"
        f"<span>{html.escape(stage.detail)}</span>"
        "</article>"
    )
