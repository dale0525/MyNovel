from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.word_targets import update_book_word_targets


def save_book_word_targets_from_form(form: dict[str, str], db_path: Path) -> int:
    book_id = int(form.get("book_id", "0") or "0")
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = update_book_word_targets(
            session,
            book_id,
            target_word_count=form.get("target_word_count", ""),
            chapter_word_count=form.get("chapter_word_count", ""),
            update_existing_chapters=form.get("update_existing_chapters") == "1",
        )
        return book.id or 0
