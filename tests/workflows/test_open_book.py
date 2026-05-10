import pytest
from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, OpenBookBlueprint
from mynovel.workflows.open_book import create_draft_book, create_draft_book_from_blueprint


def test_create_draft_book(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book(session, idea="废土修仙", genre="xianxia", audience="web readers")

    assert book.id is not None
    assert book.title == "Untitled"


def test_create_draft_book_uses_selected_title(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book(
            session,
            title="长夜图书馆",
            idea="废土修仙",
            genre="xianxia",
            audience="web readers",
        )

    assert book.title == "长夜图书馆"


def test_create_draft_book_from_blueprint_uses_selected_title(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    blueprint = OpenBookBlueprint(
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜图书馆", "禁书归途"],
            "genre": "玄幻",
            "audience": "男频网文读者",
        },
        raw_response="{}",
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(
            session,
            blueprint,
            selected_title="禁书归途",
        )

    assert book.title == "禁书归途"
    assert book.genre == "玄幻"
    assert book.audience == "男频网文读者"


def test_create_draft_book_from_blueprint_requires_selected_title(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    blueprint = OpenBookBlueprint(
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜图书馆"],
            "genre": "玄幻",
            "audience": "男频网文读者",
        },
        raw_response="{}",
    )

    with Session(engine) as session:
        with pytest.raises(ValueError, match="Title selection is required"):
            create_draft_book_from_blueprint(session, blueprint, selected_title="")


def test_create_draft_book_from_blueprint_rejects_unknown_title(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    blueprint = OpenBookBlueprint(
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜图书馆"],
            "genre": "玄幻",
            "audience": "男频网文读者",
        },
        raw_response="{}",
    )

    with Session(engine) as session:
        with pytest.raises(ValueError, match="Title selection must be one of the candidates"):
            create_draft_book_from_blueprint(session, blueprint, selected_title="禁书归途")
