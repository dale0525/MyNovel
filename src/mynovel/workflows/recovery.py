from __future__ import annotations

from dataclasses import dataclass, field

from sqlmodel import Session

from mynovel.domain.models import BookStatus, ChapterStatus, RunTrace, utc_now
from mynovel.domain.repositories import get_book, list_chapters_for_book


@dataclass(frozen=True)
class RecoveryResult:
    book_id: int
    restored_to_chapter: int
    reset_chapter_numbers: list[int] = field(default_factory=list)


def restore_to_latest_accepted_point(session: Session, book_id: int) -> RecoveryResult:
    book = get_book(session, book_id)
    if book is None:
        raise ValueError("Book does not exist.")

    chapters = list_chapters_for_book(session, book_id)
    accepted_numbers = [
        chapter.number for chapter in chapters if chapter.status == ChapterStatus.ACCEPTED
    ]
    restored_to = max(accepted_numbers) if accepted_numbers else 0
    reset_numbers: list[int] = []

    for chapter in chapters:
        if chapter.status == ChapterStatus.ACCEPTED or chapter.number <= restored_to:
            continue
        if not _has_recoverable_state(chapter):
            continue
        chapter.status = ChapterStatus.PLANNED
        chapter.context_package = {}
        chapter.draft_text = ""
        chapter.revised_text = ""
        chapter.final_text = ""
        chapter.audit_report = {}
        chapter.state_delta = {}
        chapter.summary = ""
        chapter.reviewer_note = None
        chapter.word_count = 0
        chapter.updated_at = utc_now()
        session.add(chapter)
        reset_numbers.append(chapter.number)

    book.status = BookStatus.PRODUCING if restored_to else BookStatus.CANON_LOCKED
    session.add(book)
    session.add(
        RunTrace(
            book_id=book_id,
            stage="恢复到最近批准点",
            model=None,
            cost={"estimated": 0},
            metadata_={"restored_to_chapter": restored_to, "reset_chapters": reset_numbers},
        )
    )
    session.commit()
    return RecoveryResult(
        book_id=book_id,
        restored_to_chapter=restored_to,
        reset_chapter_numbers=reset_numbers,
    )


def _has_recoverable_state(chapter) -> bool:
    return (
        chapter.status != ChapterStatus.PLANNED
        or bool(chapter.context_package)
        or bool(chapter.draft_text)
        or bool(chapter.revised_text)
        or bool(chapter.final_text)
        or bool(chapter.audit_report)
        or bool(chapter.state_delta)
        or bool(chapter.summary)
        or bool(chapter.reviewer_note)
        or bool(chapter.word_count)
    )
