from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import (
    Book,
    BookStatus,
    BlueprintAcceptance,
    Canon,
    CanonProposalRevision,
    Chapter,
    DeconstructionStudy,
    QualitySnapshot,
    RunTrace,
    StyleAsset,
    VectorEntry,
    VolumePlan,
)


class AbandonBookError(ValueError):
    pass


class DeleteBookError(ValueError):
    pass


def abandon_draft_book_from_form(db_path: Path, form: dict[str, str]) -> None:
    book_id = _parse_book_id(form.get("book_id"))
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = session.get(Book, book_id)
        if book is None:
            raise AbandonBookError("Book not found.")
        if book.status != BookStatus.DRAFT:
            raise AbandonBookError("Only draft books can be abandoned from the canon gate.")
        _delete_book_children(session, book_id)
        session.delete(book)
        session.commit()


def delete_book(db_path: Path, book_id: int) -> None:
    if book_id <= 0:
        raise DeleteBookError("Book id is required.")
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = session.get(Book, book_id)
        if book is None:
            raise DeleteBookError("Book not found.")
        _delete_book_children(session, book_id)
        session.delete(book)
        session.commit()


def _parse_book_id(value: str | None) -> int:
    try:
        book_id = int(value or "0")
    except ValueError as error:
        raise AbandonBookError("Book id is invalid.") from error
    if book_id <= 0:
        raise AbandonBookError("Book id is required.")
    return book_id


def _delete_book_children(session: Session, book_id: int) -> None:
    for model in (
        BlueprintAcceptance,
        Chapter,
        Canon,
        CanonProposalRevision,
        VolumePlan,
        RunTrace,
        VectorEntry,
        StyleAsset,
        DeconstructionStudy,
        QualitySnapshot,
    ):
        for item in session.exec(select(model).where(model.book_id == book_id)):
            session.delete(item)
