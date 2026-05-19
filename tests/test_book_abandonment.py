from pathlib import Path
from http import HTTPStatus

import pytest
from sqlmodel import Session, select

from mynovel.api_routes import dispatch_api_post
from mynovel.book_abandonment import AbandonBookError, abandon_draft_book_from_form
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import (
    Book,
    BookStatus,
    BlueprintAcceptance,
    Canon,
    CanonProposalRevision,
    Chapter,
)
from mynovel.domain.repositories import add_book


def test_abandon_draft_book_deletes_book_and_foundation_children(tmp_path: Path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(session, Book(title="长夜图书馆", genre="奇幻", audience="连载读者"))
        book_id = book.id or 0
        session.add(BlueprintAcceptance(blueprint_id=7, book_id=book_id))
        session.add(Canon(book_id=book_id, version=1, content={"characters": []}))
        session.add(Chapter(book_id=book_id, number=1, title="召唤"))
        session.add(
            CanonProposalRevision(
                book_id=book_id,
                base_canon_version=1,
                base_content_hash="content",
                base_locks_hash="locks",
                target_section="characters",
                instruction="补全人物",
            )
        )
        session.commit()

    abandon_draft_book_from_form(db_path, {"book_id": str(book_id)})

    with Session(engine) as session:
        assert session.get(Book, book_id) is None
        assert session.get(BlueprintAcceptance, 7) is None
        assert session.exec(select(Canon).where(Canon.book_id == book_id)).all() == []
        assert session.exec(select(Chapter).where(Chapter.book_id == book_id)).all() == []
        assert (
            session.exec(
                select(CanonProposalRevision).where(CanonProposalRevision.book_id == book_id)
            ).all()
            == []
        )


def test_abandon_book_rejects_locked_foundation(tmp_path: Path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(
            session,
            Book(
                title="长夜图书馆",
                genre="奇幻",
                audience="连载读者",
                status=BookStatus.CANON_LOCKED,
            ),
        )
        book_id = book.id or 0

    with pytest.raises(AbandonBookError):
        abandon_draft_book_from_form(db_path, {"book_id": str(book_id)})

    with Session(engine) as session:
        assert session.get(Book, book_id) is not None


def test_delete_book_api_deletes_project_and_children(tmp_path: Path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(
            session,
            Book(
                title="长夜图书馆",
                genre="奇幻",
                audience="连载读者",
                status=BookStatus.PRODUCING,
            ),
        )
        book_id = book.id or 0
        session.add(Canon(book_id=book_id, version=1, content={"characters": []}))
        session.add(Chapter(book_id=book_id, number=1, title="召唤"))
        session.commit()

    response = dispatch_api_post(f"/api/books/{book_id}/delete", {}, db_path)

    assert response.status == HTTPStatus.OK
    assert response.body == {"redirectTo": "/"}
    with Session(engine) as session:
        assert session.get(Book, book_id) is None
        assert session.exec(select(Canon).where(Canon.book_id == book_id)).all() == []
        assert session.exec(select(Chapter).where(Chapter.book_id == book_id)).all() == []
