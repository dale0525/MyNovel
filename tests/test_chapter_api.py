from http import HTTPStatus
from pathlib import Path

from sqlmodel import Session

from mynovel.api_routes import dispatch_api_get, dispatch_api_post
from mynovel import api_routes
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import Book, BookStatus, Canon, Chapter, ChapterStatus, RunTrace


def test_chapter_detail_returns_review_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = Book(
            title="星港遗梦",
            genre="科幻",
            audience="成人",
            status=BookStatus.PRODUCING,
            premise="领航员追查失落星港的真相。",
        )
        session.add(book)
        session.commit()
        session.refresh(book)
        canon = Canon(
            book_id=book.id or 0,
            version=2,
            content={"characters": [{"name": "岑星"}], "chapter_summaries": []},
        )
        first = Chapter(
            book_id=book.id or 0,
            number=1,
            title="失落灯塔",
            status=ChapterStatus.ACCEPTED,
            final_text="灯塔已经点亮。",
            summary="岑星发现灯塔。",
            word_count=7,
        )
        second = Chapter(
            book_id=book.id or 0,
            number=2,
            title="静默港湾",
            status=ChapterStatus.AWAITING_REVIEW,
            plan={"goal": "进入港湾", "word_budget": 3200},
            context_package={"trusted_state": {"version": 2}},
            draft_text="岑星抵达港湾。",
            revised_text="岑星抵达静默港湾。",
            audit_report={"risk_level": "low", "issues": []},
            state_delta={"chapter": 2, "changes": [{"target": "港湾", "change": "首次出现"}]},
            summary="岑星抵达港湾。",
            reviewer_note="等待人工确认。",
            word_count=10,
        )
        trace = RunTrace(
            book_id=book.id,
            stage="审计",
            prompt_id="chapter_audit",
            metadata_={"chapter": 2},
        )
        sibling_trace = RunTrace(
            book_id=book.id,
            stage="兄弟章节审计",
            prompt_id="chapter_audit",
            metadata_={"chapter": 1},
        )
        session.add_all([canon, first, second, trace, sibling_trace])
        session.commit()
        session.refresh(second)
        chapter_id = second.id or 0

    response = dispatch_api_get(f"/api/chapters/{chapter_id}", "", db_path)

    assert response.status == HTTPStatus.OK
    assert response.body["book"]["title"] == "星港遗梦"
    assert response.body["chapter"]["id"] == chapter_id
    assert response.body["chapter"]["plan"] == {"goal": "进入港湾", "word_budget": 3200}
    assert response.body["chapter"]["draftText"] == "岑星抵达港湾。"
    assert response.body["chapter"]["revisedText"] == "岑星抵达静默港湾。"
    assert [chapter["number"] for chapter in response.body["siblingChapters"]] == [1, 2]
    assert response.body["latestCanon"]["version"] == 2
    assert [trace["stage"] for trace in response.body["traces"]] == ["审计"]
    assert response.body["traces"][0]["promptId"] == "chapter_audit"
    assert [slot["key"] for slot in response.body["stageSlots"]] == [
        "plan",
        "context",
        "draft",
        "delta",
        "audit",
    ]
    assert all(slot["ready"] for slot in response.body["stageSlots"])


def test_unknown_chapter_action_returns_chapter_action_failed(tmp_path: Path) -> None:
    response = dispatch_api_post("/api/chapters/99/unknown", {}, tmp_path / "dev.sqlite")

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["error"]["code"] == "chapter_action_failed"


def test_run_chapter_action_returns_updated_review_payload(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = Book(
            title="星港遗梦",
            genre="科幻",
            audience="成人",
            status=BookStatus.CANON_LOCKED,
        )
        session.add(book)
        session.commit()
        session.refresh(book)
        session.add(Canon(book_id=book.id or 0, version=1, content={"characters": []}))
        chapter = Chapter(
            book_id=book.id or 0,
            number=1,
            title="失落灯塔",
            status=ChapterStatus.PLANNED,
        )
        session.add(chapter)
        session.commit()
        session.refresh(chapter)
        chapter_id = chapter.id or 0

    def mark_running(db_path: Path, chapter_id: int, provider_config=None) -> int:
        with Session(create_engine_for_path(db_path)) as session:
            chapter = session.get(Chapter, chapter_id)
            assert chapter is not None
            chapter.status = ChapterStatus.RUNNING
            session.add(chapter)
            session.commit()
        return chapter_id

    monkeypatch.setattr(api_routes, "queue_chapter_run", mark_running)

    response = dispatch_api_post(f"/api/chapters/{chapter_id}/run", {}, db_path)

    assert response.status == HTTPStatus.ACCEPTED
    assert response.body["chapter"]["id"] == chapter_id
    assert response.body["chapter"]["status"] == "running"
