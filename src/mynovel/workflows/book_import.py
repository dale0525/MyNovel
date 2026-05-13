from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session

from mynovel.domain.models import Book, BookStatus, Canon, Chapter, ChapterStatus
from mynovel.workflows.canon_proposal import sanitize_canon_content


def import_book_json(session: Session, raw_json: str) -> Book:
    payload = _parse_payload(raw_json)
    book_payload = _mapping(payload.get("book"), "book")
    title = _required_text(book_payload.get("title"), "book.title")
    genre = _text(book_payload.get("genre")) or "未分类"
    audience = _text(book_payload.get("audience")) or "未设置"
    premise = _text(book_payload.get("premise")) or None
    chapter_payloads = _chapters(payload.get("chapters"))
    trusted_state = _trusted_state(payload.get("trusted_state"))
    trusted_state_content = (
        sanitize_canon_content(_mapping(trusted_state.get("content"), "trusted_state.content"))
        if trusted_state
        else {}
    )

    book = Book(
        title=title,
        genre=genre,
        audience=audience,
        premise=premise,
        status=_imported_status(trusted_state, chapter_payloads),
    )
    try:
        session.add(book)
        session.flush()
        if book.id is None:
            raise ValueError("Imported book did not receive an id.")

        if trusted_state:
            session.add(
                Canon(
                    book_id=book.id,
                    version=_positive_int(trusted_state.get("version"), 1),
                    content=trusted_state_content,
                )
            )
        for index, chapter_payload in enumerate(chapter_payloads, start=1):
            text = _text(chapter_payload.get("text"))
            number = _positive_int(chapter_payload.get("number"), index)
            title = _text(chapter_payload.get("title")) or f"第 {number:02d} 章"
            session.add(
                Chapter(
                    book_id=book.id,
                    number=number,
                    title=title,
                    status=ChapterStatus.ACCEPTED if text else ChapterStatus.PLANNED,
                    final_text=text,
                    revised_text=text,
                    word_count=_positive_int(chapter_payload.get("word_count"), len(text)),
                )
            )
        session.commit()
        session.refresh(book)
        return book
    except Exception:
        session.rollback()
        raise


def _parse_payload(raw_json: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as error:
        raise ValueError("Project import JSON is invalid.") from error
    return _mapping(payload, "payload")


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object.")
    return value


def _chapters(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("chapters must be a list.")
    return [_mapping(item, "chapter") for item in value]


def _trusted_state(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    return _mapping(value, "trusted_state")


def _required_text(value: object, label: str) -> str:
    text = _text(value)
    if not text:
        raise ValueError(f"{label} is required.")
    return text


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _positive_int(value: object, fallback: int) -> int:
    if not isinstance(value, str | int | float):
        return fallback
    try:
        number = int(value)
    except ValueError:
        return fallback
    return number if number >= 0 else fallback


def _imported_status(
    trusted_state: dict[str, Any],
    chapters: list[dict[str, Any]],
) -> BookStatus:
    if chapters:
        return BookStatus.PRODUCING
    if trusted_state:
        return BookStatus.CANON_LOCKED
    return BookStatus.DRAFT
