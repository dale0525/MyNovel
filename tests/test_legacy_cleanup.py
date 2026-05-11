from pathlib import Path

from sqlmodel import Session, select

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import Book, Canon, Chapter, OpenBookBlueprint, RunTrace, VolumePlan
from mynovel.legacy_cleanup import remove_legacy_placeholder_data


def _placeholder_title() -> str:
    return "".join(("幽", "谷", "回", "声"))


def test_remove_legacy_placeholder_data_removes_seeded_book_and_children(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = Book(
            title=_placeholder_title(),
            genre="奇幻连载",
            audience="成长冒险读者",
            premise="少年罗斯在幽谷边境听见远古召唤，发现自己与失落王朝有关。",
        )
        session.add(book)
        session.commit()
        session.refresh(book)
        assert book.id is not None
        session.add(Chapter(book_id=book.id, number=1, title="召唤"))
        session.add(Canon(book_id=book.id, version=1, content={}))
        session.add(
            VolumePlan(
                book_id=book.id,
                title="第一卷：雾谷回声",
                core_conflict="确认召唤来源。",
            )
        )
        session.add(RunTrace(book_id=book.id, stage="chapter_pipeline"))
        session.add(
            OpenBookBlueprint(
                idea="少年在雾谷边境发现古老召唤符号，被迫踏入失落王朝的遗迹。",
                version=1,
                content={},
                raw_response="{}",
            )
        )
        session.commit()

    remove_legacy_placeholder_data(engine)

    with Session(engine) as session:
        assert list(session.exec(select(Book))) == []
        assert list(session.exec(select(Chapter))) == []
        assert list(session.exec(select(Canon))) == []
        assert list(session.exec(select(VolumePlan))) == []
        assert list(session.exec(select(RunTrace))) == []
        assert list(session.exec(select(OpenBookBlueprint))) == []


def test_remove_legacy_placeholder_data_keeps_user_book_with_same_title(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        session.add(
            Book(
                title=_placeholder_title(),
                genre="自定义题材",
                audience="私人读者",
                premise="这是用户自己的同名项目。",
            )
        )
        session.commit()

    remove_legacy_placeholder_data(engine)

    with Session(engine) as session:
        books = list(session.exec(select(Book)))

    assert len(books) == 1
    assert books[0].premise == "这是用户自己的同名项目。"
