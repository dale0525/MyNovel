from pathlib import Path

from sqlmodel import Session, select

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.dev_seed import ensure_dev_demo_data
from mynovel.domain.models import Book, Canon, Chapter, ChapterStatus, OpenBookBlueprint
from mynovel.domain.repositories import get_provider_config


def test_dev_demo_seed_creates_full_reviewable_pipeline(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)

    ensure_dev_demo_data(db_path)

    with Session(engine) as session:
        book = session.exec(select(Book)).one()
        chapters = list(session.exec(select(Chapter).order_by(Chapter.number)))
        canon = session.exec(select(Canon).order_by(Canon.version)).first()
        blueprint = session.exec(select(OpenBookBlueprint)).first()
        provider_config = get_provider_config(session)

    assert book.title == "幽谷回声"
    assert provider_config is not None
    assert blueprint is not None
    assert canon is not None
    assert len(chapters) == 10
    assert chapters[0].status == ChapterStatus.ACCEPTED
    assert chapters[1].status == ChapterStatus.AWAITING_REVIEW
    assert chapters[2].status == ChapterStatus.RUNNING
    assert chapters[-1].status == ChapterStatus.PLANNED
