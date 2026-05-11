from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from sqlmodel import Session, select

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import Book, BookStatus, ChapterStatus
from mynovel.domain.repositories import list_chapters_for_book


def review_destination(db_path: Path) -> str:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        books = list(
            session.exec(select(Book).order_by(cast(Any, Book.created_at).desc()).limit(20))
        )
        for book in books:
            if book.id is None:
                continue
            if book.status == BookStatus.DRAFT:
                return f"/book/{book.id}/state"
            chapters = list_chapters_for_book(session, book.id)
            for status in (
                ChapterStatus.AWAITING_REVIEW,
                ChapterStatus.NEEDS_REVISION,
                ChapterStatus.RUNNING,
            ):
                chapter = next((item for item in chapters if item.status == status), None)
                if chapter is not None and chapter.id is not None:
                    return f"/chapter/{chapter.id}"
            return f"/book/{book.id}"
    return "/"
