import pytest
from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, ChapterStatus, OpenBookBlueprint
from mynovel.domain.repositories import list_chapters_for_book, list_volume_plans_for_book
from mynovel.workflows.open_book import (
    create_draft_book,
    create_draft_book_from_blueprint,
    lock_canon_foundation,
)


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


def test_create_draft_book_from_blueprint_keeps_target_word_counts(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    blueprint = OpenBookBlueprint(
        idea="\n".join(
            [
                "一句灵感：失意档案员重建禁书馆",
                "可选偏好：",
                "- 全书目标字数：300000 字",
                "- 单章目标字数：3200 字",
            ]
        ),
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜图书馆"],
            "genre": "玄幻",
            "audience": "男频网文读者",
            "chapter_directions": [{"title": "残页", "goal": "得到残页。"}],
        },
        raw_response="{}",
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(
            session,
            blueprint,
            selected_title="长夜图书馆",
        )

    assert book.constraints["target_word_count"] == 300000
    assert book.constraints["chapter_word_count"] == 3200
    assert book.constraints["selling_points"] == []
    assert book.constraints["reader_promises"] == []

    with Session(engine) as session:
        chapters = list_chapters_for_book(session, book.id)

    assert chapters[0].plan["word_budget"] == 3200
    assert chapters[-1].plan["word_budget"] == 3200


def test_create_draft_book_from_blueprint_creates_volume_plan(tmp_path) -> None:
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
            "central_conflict": "守住禁书馆并找回失落王朝的真相。",
            "reader_promises": ["每章揭开一页禁书", "主角身份逐步反转"],
            "volume_plan": {
                "title": "禁书馆重启",
                "core_conflict": "主角必须在追捕者到来前恢复禁书馆。",
                "pacing_curve": ["开局钩子", "中段反转", "卷末危机"],
                "payoff_distribution": ["第3章揭示禁书规则", "第8章兑现身份线索"],
                "key_turns": ["禁书馆开门", "追捕者锁定主角"],
                "commitments": ["持续禁书谜题", "关系信任逐章推进"],
            },
        },
        raw_response="{}",
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, blueprint, selected_title="长夜图书馆")
        volume_plans = list_volume_plans_for_book(session, book.id)

    assert len(volume_plans) == 1
    assert volume_plans[0].title == "禁书馆重启"
    assert volume_plans[0].core_conflict == "主角必须在追捕者到来前恢复禁书馆。"
    assert volume_plans[0].pacing_curve == ["开局钩子", "中段反转", "卷末危机"]
    assert volume_plans[0].commitments == ["持续禁书谜题", "关系信任逐章推进"]


def test_create_draft_book_from_blueprint_can_leave_foundation_waiting_for_review(
    tmp_path,
) -> None:
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
            "chapter_directions": [{"title": "残页召唤", "goal": "主角得到第一张残页。"}],
        },
        raw_response="{}",
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(
            session,
            blueprint,
            selected_title="长夜图书馆",
            lock_foundation=False,
        )
        chapters = list_chapters_for_book(session, book.id)

    assert book.title == "长夜图书馆"
    assert book.status.value == "draft"
    assert chapters[0].number == 1
    assert chapters[0].status == ChapterStatus.PLANNED


def test_lock_canon_foundation_allows_chapter_production_after_review(tmp_path) -> None:
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
        book = create_draft_book_from_blueprint(
            session,
            blueprint,
            selected_title="长夜图书馆",
            lock_foundation=False,
        )
        locked = lock_canon_foundation(session, book.id)

    assert locked.status.value == "canon_locked"


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
