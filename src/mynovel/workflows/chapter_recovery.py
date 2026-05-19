from __future__ import annotations

from pathlib import Path
from threading import Lock

from sqlmodel import Session, select

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import Chapter, ChapterStatus, RunTrace, utc_now

_recovery_lock = Lock()
_recovered_db_paths: set[Path] = set()


def recover_interrupted_chapter_jobs_once(db_path: Path) -> int:
    resolved_path = db_path.resolve()
    with _recovery_lock:
        if resolved_path in _recovered_db_paths:
            return 0
        _recovered_db_paths.add(resolved_path)

    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        return recover_interrupted_chapter_jobs(session)


def recover_interrupted_chapter_jobs(session: Session) -> int:
    chapters = list(session.exec(select(Chapter).where(Chapter.status == ChapterStatus.RUNNING)))
    if not chapters:
        return 0

    recovered = 0
    for chapter in chapters:
        if _has_reviewable_output(chapter):
            chapter.status = ChapterStatus.AWAITING_REVIEW
            chapter.reviewer_note = "生成中断：已恢复到待审核，可确认或继续修订。"
        else:
            chapter.status = ChapterStatus.NEEDS_REVISION
            chapter.reviewer_note = "生成中断：应用已重启，可重新生成本章。"
        chapter.updated_at = utc_now()
        session.add(chapter)
        session.add(
            RunTrace(
                book_id=chapter.book_id,
                stage="恢复中断章节",
                cost={"estimated": 0},
                metadata_={
                    "chapter": chapter.number,
                    "status": chapter.status.value,
                    "reason": "startup_recovery",
                },
            )
        )
        recovered += 1
    session.commit()
    return recovered


def _has_reviewable_output(chapter: Chapter) -> bool:
    has_text = bool((chapter.revised_text or chapter.draft_text or chapter.final_text).strip())
    return has_text and bool(chapter.audit_report)
