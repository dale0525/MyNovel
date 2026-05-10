from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.workflows.open_book import create_draft_book


def test_create_draft_book(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book(session, idea="废土修仙", genre="xianxia", audience="web readers")

    assert book.id is not None
    assert book.title == "Untitled"
