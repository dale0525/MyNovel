from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from mynovel.domain.models import Chapter, VolumePlan
from mynovel.domain.repositories import get_active_volume_plan


def get_volume_plan_for_chapter(session: Session, chapter: Chapter) -> VolumePlan | None:
    volume_number = chapter_volume_number(chapter.plan)
    if volume_number is not None:
        plan = session.exec(
            select(VolumePlan)
            .where(VolumePlan.book_id == chapter.book_id)
            .where(VolumePlan.volume_number == volume_number)
            .limit(1)
        ).first()
        if plan is not None:
            return plan
    return get_active_volume_plan(session, chapter.book_id)


def chapter_volume_number(plan: dict[str, Any]) -> int | None:
    value = plan.get("volume_number", plan.get("volumeNumber"))
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
