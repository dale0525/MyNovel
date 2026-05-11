import pytest
from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, ChapterStatus, OpenBookBlueprint
from mynovel.domain.repositories import get_latest_canon, list_chapters_for_book
from mynovel.workflows.chapter_pipeline import approve_chapter, run_chapter_pipeline
from mynovel.workflows.open_book import create_draft_book_from_blueprint
from mynovel.workflows.recovery import restore_to_latest_accepted_point
from mynovel.workflows.state_validation import StateDeltaValidationError


def test_approve_chapter_rejects_invalid_state_delta(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="幽谷回声")
        chapter = run_chapter_pipeline(session, _chapter_id(session, book.id, 1))
        chapter.state_delta = {"chapter": 1, "changes": [{"type": "人物状态"}]}
        session.add(chapter)
        session.commit()

        with pytest.raises(StateDeltaValidationError, match="target"):
            approve_chapter(session, chapter.id)


def test_restore_to_latest_accepted_point_clears_unaccepted_chapter_state(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="幽谷回声")
        first = approve_chapter(
            session, run_chapter_pipeline(session, _chapter_id(session, book.id, 1)).id
        )
        second = run_chapter_pipeline(session, _chapter_id(session, book.id, 2))

        result = restore_to_latest_accepted_point(session, book.id)
        chapters = list_chapters_for_book(session, book.id)
        canon = get_latest_canon(session, book.id)

    assert result.restored_to_chapter == first.number
    assert result.reset_chapter_numbers == [second.number]
    assert chapters[0].status == ChapterStatus.ACCEPTED
    assert chapters[1].status == ChapterStatus.PLANNED
    assert chapters[1].draft_text == ""
    assert chapters[1].audit_report == {}
    assert canon is not None
    assert canon.version == 2


def _chapter_id(session: Session, book_id: int, number: int) -> int:
    chapter = [item for item in list_chapters_for_book(session, book_id) if item.number == number][
        0
    ]
    assert chapter.id is not None
    return chapter.id


def _blueprint() -> OpenBookBlueprint:
    return OpenBookBlueprint(
        id=1,
        idea="失忆少女在幽谷中寻找被抹去的王朝真相",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["幽谷回声"],
            "genre": "奇幻连载",
            "audience": "喜欢成长冒险的连载读者",
            "selling_points": ["每章揭开一条旧王朝线索"],
            "protagonist": {"name": "莉拉", "hook": "失忆但能读懂古代符号"},
            "world": {"premise": "幽谷里散落着被抹去王朝的遗迹"},
            "central_conflict": "莉拉必须确认自己与旧王朝覆灭之间的关系。",
            "reader_promises": ["持续发现遗迹"],
            "chapter_directions": [
                {"title": "离开的召唤", "goal": "发现第一枚符号"},
                {"title": "雾谷来信", "goal": "收到第二枚符号的线索"},
            ],
        },
        raw_response="{}",
    )
