import json

import pytest
from sqlmodel import Session, select

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import Book, ChapterStatus
from mynovel.domain.repositories import get_latest_canon, list_chapters_for_book
from mynovel.workflows.book_import import import_book_json


def test_import_book_json_creates_project_from_export_payload(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "dev.sqlite")
    create_db_and_tables(engine)
    payload = {
        "book": {
            "title": "雾港书局",
            "genre": "奇幻",
            "audience": "连载读者",
            "premise": "少女追查石门背后的旧文明。",
        },
        "trusted_state": {
            "version": 3,
            "content": {"world_rules": [{"name": "石语魔法"}]},
        },
        "chapters": [
            {"number": 1, "title": "召唤", "text": "石门发出低鸣。", "word_count": 8},
            {"number": 2, "title": "穿越迷雾", "text": "雾中出现旧路。"},
        ],
    }

    with Session(engine) as session:
        book = import_book_json(session, json.dumps(payload, ensure_ascii=False))

        canon = get_latest_canon(session, book.id or 0)
        chapters = list_chapters_for_book(session, book.id or 0)

    assert book.title == "雾港书局"
    assert book.premise == "少女追查石门背后的旧文明。"
    assert canon is not None
    assert canon.version == 3
    assert canon.content["world_rules"][0]["name"] == "石语魔法"
    assert [chapter.title for chapter in chapters] == ["召唤", "穿越迷雾"]
    assert all(chapter.status == ChapterStatus.ACCEPTED for chapter in chapters)
    assert chapters[0].final_text == "石门发出低鸣。"
    assert chapters[0].word_count == 8
    assert chapters[1].word_count == len("雾中出现旧路。")


def test_import_book_json_rejects_payload_without_book_title(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "dev.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        with pytest.raises(ValueError, match="title"):
            import_book_json(session, json.dumps({"book": {"title": ""}}))


def test_import_book_json_strips_canon_proposal_metadata(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "dev.sqlite")
    create_db_and_tables(engine)
    payload = {
        "book": {"title": "雾港书局", "genre": "奇幻", "audience": "连载读者"},
        "trusted_state": {
            "version": 1,
            "content": {
                "world_rules": [{"name": "石语魔法"}],
                "_canon_proposal": {"section_locks": {"world_rules": True}},
                "canon_proposal_revisions": [{"changed_sections": {"characters": []}}],
                "unknown_internal": ["not trusted state"],
                "accepted_chapters": [{"chapter": 1, "title": "召唤"}],
                "resources": [{"name": "石钥匙", "detail": "打开旧门"}],
            },
        },
    }

    with Session(engine) as session:
        book = import_book_json(session, json.dumps(payload, ensure_ascii=False))
        canon = get_latest_canon(session, book.id or 0)

    assert "_canon_proposal" not in book.constraints
    assert canon is not None
    assert "_canon_proposal" not in canon.content
    assert "canon_proposal_revisions" not in canon.content
    assert "unknown_internal" not in canon.content
    assert canon.content["accepted_chapters"] == [{"chapter": 1, "title": "召唤"}]
    assert canon.content["resources"] == [{"name": "石钥匙", "detail": "打开旧门"}]


def test_import_book_json_rolls_back_invalid_trusted_state(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "dev.sqlite")
    create_db_and_tables(engine)
    payload = {
        "book": {"title": "雾港书局", "genre": "奇幻", "audience": "连载读者"},
        "trusted_state": {"version": 1, "content": []},
    }

    with Session(engine) as session:
        with pytest.raises(ValueError, match="trusted_state.content"):
            import_book_json(session, json.dumps(payload, ensure_ascii=False))

        assert session.exec(select(Book)).all() == []
