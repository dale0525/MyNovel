from pathlib import Path

import pytest
from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import (
    BlueprintStatus,
    CanonProposalRevision,
    CanonProposalRevisionStatus,
    ChapterStatus,
    OpenBookBlueprint,
)
from mynovel.domain.repositories import (
    add_canon_proposal_revision,
    get_canon_proposal_revision,
    get_latest_canon,
    list_chapters_for_book,
    list_volume_plans_for_book,
)
from mynovel.workflows.canon_proposal import (
    CANON_PROPOSAL_KEY,
    content_hash,
    locks_hash,
    section_locks_for_book,
)
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


def test_create_draft_book_from_blueprint_does_not_use_range_as_chapter_title(tmp_path) -> None:
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
            "chapter_directions": [
                {"chapter": "第1-3章：引子", "direction": "林墨接到第一份异常档案。"}
            ],
        },
        raw_response="{}",
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, blueprint, selected_title="长夜图书馆")
        chapters = list_chapters_for_book(session, book.id)

    assert chapters[0].title == "第 01 章"
    assert chapters[0].plan["goal"] == "林墨接到第一份异常档案。"


def test_create_draft_book_from_blueprint_keeps_blueprint_objects_readable_in_canon(
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
            "world": {"name": "街尾蛇城", "rules": "历史守恒"},
            "protagonist": {"name": "林墨", "role": "档案修复师", "trait": "触觉共感"},
        },
        raw_response="{}",
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, blueprint, selected_title="长夜图书馆")
        canon = get_latest_canon(session, book.id)

    assert canon is not None
    assert canon.book_id == book.id
    assert canon.content["world_rules"] == [{"name": "街尾蛇城", "rules": "历史守恒"}]
    assert canon.content["characters"] == [
        {"name": "林墨", "role": "档案修复师", "trait": "触觉共感"}
    ]


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


def test_lock_canon_foundation_marks_pending_proposal_revisions_stale(tmp_path: Path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    blueprint = OpenBookBlueprint(
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={"title_options": ["长夜图书馆"], "genre": "玄幻", "audience": "男频网文读者"},
        raw_response="{}",
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(
            session,
            blueprint,
            selected_title="长夜图书馆",
            lock_foundation=False,
        )
        canon = get_latest_canon(session, book.id or 0)
        assert canon is not None
        revision = add_canon_proposal_revision(
            session,
            CanonProposalRevision(
                book_id=book.id or 0,
                base_canon_version=canon.version,
                base_content_hash=content_hash(canon.content),
                base_locks_hash=locks_hash(section_locks_for_book(book)),
                target_section="characters",
                instruction="主角改成外冷内热",
                allowed_sections=["characters"],
                locked_sections=[],
                changed_sections={"characters": [{"name": "林烬"}]},
                summary="已调整人物。",
            ),
        )
        book.constraints = {
            **book.constraints,
            CANON_PROPOSAL_KEY: {
                "section_locks": {"characters": False},
                "last_revision": {"summary": "草稿摘要"},
            },
        }
        canon.content = {
            **canon.content,
            "_canon_proposal": {"should": "not survive"},
            "unknown_internal": ["not trusted state"],
            "accepted_chapters": [{"chapter": 1, "title": "离开的召唤"}],
            "resources": [{"name": "古地图", "detail": "通往幽谷"}],
        }
        session.add(book)
        session.add(canon)
        session.commit()

        locked = lock_canon_foundation(session, book.id)
        stale_revision = get_canon_proposal_revision(session, revision.id or 0)
        locked_canon = get_latest_canon(session, book.id or 0)

    assert locked.status.value == "canon_locked"
    assert CANON_PROPOSAL_KEY not in locked.constraints
    assert stale_revision is not None
    assert stale_revision.status == CanonProposalRevisionStatus.STALE
    assert locked_canon is not None
    assert "_canon_proposal" not in locked_canon.content
    assert "unknown_internal" not in locked_canon.content
    assert locked_canon.content["factions"] == []
    assert locked_canon.content["state_history"] == []
    assert locked_canon.content["accepted_chapters"] == [{"chapter": 1, "title": "离开的召唤"}]
    assert locked_canon.content["resources"] == [{"name": "古地图", "detail": "通往幽谷"}]


def test_create_draft_book_from_blueprint_initializes_factions_section(tmp_path: Path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    blueprint = OpenBookBlueprint(
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={"title_options": ["长夜图书馆"], "genre": "玄幻", "audience": "男频网文读者"},
        raw_response="{}",
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(
            session,
            blueprint,
            selected_title="长夜图书馆",
            lock_foundation=False,
        )
        canon = get_latest_canon(session, book.id or 0)

    assert canon is not None
    assert canon.content["factions"] == []
