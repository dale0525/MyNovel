import json

from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, CanonProposalRevision, OpenBookBlueprint
from mynovel.domain.repositories import get_latest_canon, list_chapters_for_book
from mynovel.workflows.book_export import export_book_json, export_book_markdown
from mynovel.workflows.chapter_pipeline import approve_chapter, run_chapter_pipeline
from mynovel.workflows.open_book import create_draft_book_from_blueprint


def test_export_book_markdown_includes_only_accepted_chapters_in_order(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapters = list_chapters_for_book(session, book.id)
        first = approve_chapter(session, run_chapter_pipeline(session, chapters[0].id).id)
        second = run_chapter_pipeline(session, chapters[1].id)

        markdown = export_book_markdown(book, list_chapters_for_book(session, book.id))

    assert markdown.startswith("# 长夜图书馆")
    assert f"## 第 01 章 {first.title}" in markdown
    assert first.final_text in markdown
    assert second.title not in markdown


def test_export_book_json_includes_metadata_trusted_state_and_accepted_chapters(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = list_chapters_for_book(session, book.id)[0]
        accepted = approve_chapter(session, run_chapter_pipeline(session, chapter.id).id)
        canon = get_latest_canon(session, book.id)

        payload = json.loads(
            export_book_json(book, canon, list_chapters_for_book(session, book.id))
        )

    assert payload["book"]["title"] == "长夜图书馆"
    assert payload["trusted_state"]["version"] == 2
    assert payload["chapters"] == [
        {
            "number": accepted.number,
            "title": accepted.title,
            "text": accepted.final_text,
            "word_count": accepted.word_count,
        }
    ]


def test_export_book_json_does_not_include_canon_proposal_metadata(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        book.constraints = {
            **book.constraints,
            "_canon_proposal": {
                "section_locks": {"characters": True},
                "last_revision": {"summary": "草稿修订"},
            },
        }
        session.add(book)
        session.commit()
        canon = get_latest_canon(session, book.id or 0)
        assert canon is not None
        canon.content = {
            **canon.content,
            "_canon_proposal": {"should": "not export"},
            "canon_proposal_revisions": [{"summary": "DO_NOT_EXPORT_INTERNAL"}],
            "unknown_internal": ["not trusted state"],
            "accepted_chapters": [{"chapter": 1, "title": "离开的召唤"}],
            "resources": [{"name": "古地图", "detail": "通往幽谷"}],
        }
        session.add(canon)
        session.add(
            CanonProposalRevision(
                book_id=book.id or 0,
                base_canon_version=canon.version,
                base_content_hash="content",
                base_locks_hash="locks",
                target_section="characters",
                instruction="主角改成外冷内热",
                changed_sections={"characters": [{"name": "DO_NOT_EXPORT_PREVIEW"}]},
                summary="DO_NOT_EXPORT_REVISION",
            )
        )
        session.commit()

        payload_text = export_book_json(book, canon, list_chapters_for_book(session, book.id or 0))
        payload = json.loads(payload_text)

    assert "_canon_proposal" not in payload_text
    assert "last_revision" not in payload_text
    assert "DO_NOT_EXPORT_PREVIEW" not in payload_text
    assert "DO_NOT_EXPORT_REVISION" not in payload_text
    assert "DO_NOT_EXPORT_INTERNAL" not in payload_text
    assert payload["trusted_state"]["content"].get("characters") is not None
    assert "unknown_internal" not in payload["trusted_state"]["content"]
    assert payload["trusted_state"]["content"]["accepted_chapters"] == [
        {"chapter": 1, "title": "离开的召唤"}
    ]
    assert payload["trusted_state"]["content"]["resources"] == [
        {"name": "古地图", "detail": "通往幽谷"}
    ]


def _blueprint() -> OpenBookBlueprint:
    return OpenBookBlueprint(
        id=1,
        idea="失忆少女在幽谷中寻找被抹去的王朝真相",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜图书馆"],
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
