from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session

from mynovel.domain.models import BookStatus, Chapter, ChapterStatus, RunTrace
from mynovel.domain.repositories import get_book, get_latest_canon, list_chapters_for_book
from mynovel.workflows.chapter_pipeline import ChapterModelClient, run_chapter_pipeline


@dataclass(frozen=True)
class ChapterBatchResult:
    book_id: int
    requested_limit: int
    completed_chapter_numbers: list[int] = field(default_factory=list)
    paused: bool = False
    paused_chapter_number: int | None = None
    pause_reason: str | None = None
    trusted_state_version: int = 0


def run_chapter_batch(
    session: Session,
    book_id: int,
    limit: int,
    model_client: ChapterModelClient | None = None,
    model_name: str | None = None,
) -> ChapterBatchResult:
    if limit < 1:
        raise ValueError("Batch limit must be at least 1.")
    book = get_book(session, book_id)
    if book is None:
        raise ValueError("Book does not exist.")

    completed: list[int] = []
    pause_reason: str | None = None
    paused_chapter: Chapter | None = None

    for chapter in _next_batch_candidates(session, book_id)[:limit]:
        if chapter.id is None:
            continue
        reviewed = run_chapter_pipeline(
            session,
            chapter.id,
            model_client=model_client,
            model_name=model_name,
        )
        completed.append(reviewed.number)

        pause_reason = _blocking_pause_reason(reviewed)
        if pause_reason:
            paused_chapter = reviewed
            _pause_book(session, book_id, reviewed, pause_reason, model_name)
            break

    latest = get_latest_canon(session, book_id)
    return ChapterBatchResult(
        book_id=book_id,
        requested_limit=limit,
        completed_chapter_numbers=completed,
        paused=paused_chapter is not None,
        paused_chapter_number=paused_chapter.number if paused_chapter else None,
        pause_reason=pause_reason,
        trusted_state_version=latest.version if latest else 0,
    )


def _next_batch_candidates(session: Session, book_id: int) -> list[Chapter]:
    return [
        chapter
        for chapter in list_chapters_for_book(session, book_id)
        if chapter.status in {ChapterStatus.PLANNED, ChapterStatus.RUNNING, ChapterStatus.NEEDS_REVISION}
    ]


def _blocking_pause_reason(chapter: Chapter) -> str | None:
    if chapter.status == ChapterStatus.NEEDS_REVISION:
        return "章节生产失败，需要人工处理"
    if _has_high_risk_audit(chapter.audit_report):
        return "高风险章节需要人工审核"
    if _has_major_state_change(chapter.state_delta):
        return "重大变化需要人工审核"
    return None


def _has_high_risk_audit(audit_report: dict[str, Any]) -> bool:
    if str(audit_report.get("risk_level", "")).lower() == "high":
        return True
    for issue in audit_report.get("issues", []):
        if not isinstance(issue, dict):
            continue
        severity = str(issue.get("severity", "")).lower()
        if severity == "high" and not issue.get("resolved"):
            return True
    return False


def _has_major_state_change(state_delta: dict[str, Any]) -> bool:
    for change in state_delta.get("changes", []):
        if not isinstance(change, dict):
            continue
        impact = str(change.get("impact", "")).lower()
        if impact in {"major", "critical", "high"}:
            return True
        text = " ".join(str(change.get(key, "")) for key in ("type", "target", "change"))
        if any(
            term in text
            for term in ("角色死亡", "人物死亡", "死亡", "牺牲", "退场", "核心设定", "改写设定")
        ):
            return True
    return False


def _pause_book(
    session: Session,
    book_id: int,
    chapter: Chapter,
    reason: str,
    model_name: str | None,
) -> None:
    book = get_book(session, book_id)
    if book is not None:
        book.status = BookStatus.PAUSED
        session.add(book)
    session.add(
        RunTrace(
            book_id=book_id,
            stage="批量生产暂停",
            model=model_name,
            cost={"estimated": 0},
            metadata_={
                "chapter": chapter.number,
                "status": chapter.status.value,
                "reason": reason,
                "retryable": chapter.status == ChapterStatus.NEEDS_REVISION,
            },
        )
    )
    session.commit()
