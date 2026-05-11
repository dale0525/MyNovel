from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, OpenBookBlueprint
from mynovel.domain.repositories import add_open_book_blueprint, list_open_book_blueprints
from mynovel.workflows.open_book_blueprint import (
    build_blueprint_messages,
    create_blueprint_job,
    parse_blueprint_json,
)


def test_parse_blueprint_json_requires_open_book_fields() -> None:
    blueprint = parse_blueprint_json(
        """
        {
          "title_options": ["长夜图书馆", "禁书归途"],
          "genre": "玄幻",
          "audience": "男频网文读者",
          "selling_points": ["禁书体系", "升级节奏"],
          "protagonist": {"name": "林烬", "hook": "失意档案员"},
          "world": {"premise": "书籍可以封印神明"},
          "central_conflict": "主角必须重建被毁的禁书馆",
          "reader_promises": ["每章有新禁书", "持续解锁世界真相"],
          "chapter_directions": ["得到残页", "发现追杀者"]
        }
        """
    )

    assert blueprint["genre"] == "玄幻"
    assert blueprint["title_options"][0] == "长夜图书馆"


def test_build_blueprint_messages_include_revision_context() -> None:
    messages = build_blueprint_messages(
        idea="失意档案员重建禁书馆",
        previous_blueprint={"genre": "玄幻", "central_conflict": "重建禁书馆"},
        revision_notes="主角更疯一点",
    )

    joined = "\n".join(message["content"] for message in messages)

    assert "失意档案员重建禁书馆" in joined
    assert "主角更疯一点" in joined
    assert "previous_blueprint" in joined


def test_build_blueprint_messages_ask_ai_to_fill_missing_open_book_context() -> None:
    messages = build_blueprint_messages(idea="一句灵感：失意档案员重建禁书馆")

    joined = "\n".join(message["content"] for message in messages)

    assert "没有明确题材、目标读者或卖点" in joined
    assert "自行生成" in joined


def test_blueprint_versions_round_trip_through_sqlite(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        add_open_book_blueprint(
            session,
            OpenBookBlueprint(
                idea="失意档案员重建禁书馆",
                version=1,
                instruction=None,
                content={"genre": "玄幻"},
                raw_response='{"genre":"玄幻"}',
            ),
        )
        add_open_book_blueprint(
            session,
            OpenBookBlueprint(
                idea="失意档案员重建禁书馆",
                version=2,
                instruction="主角更疯一点",
                content={"genre": "玄幻", "protagonist": {"hook": "疯批"}},
                raw_response='{"genre":"玄幻"}',
            ),
        )
        blueprints = list_open_book_blueprints(session)

    assert [blueprint.version for blueprint in blueprints] == [2, 1]
    assert blueprints[0].instruction == "主角更疯一点"


def test_create_blueprint_job_persists_pending_status(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        job = create_blueprint_job(
            session,
            idea="失意档案员重建禁书馆",
            version=1,
            instruction=None,
            parent_id=None,
        )

    assert job.id is not None
    assert job.status == BlueprintStatus.PENDING
    assert job.raw_response == ""
    assert job.content == {}
