from http import HTTPStatus
from pathlib import Path

from sqlmodel import Session, select

from mynovel.canon_proposal_server import (
    handle_apply_canon_proposal_revision,
    handle_create_canon_proposal_revision,
    handle_discard_canon_proposal_revision,
    handle_toggle_canon_proposal_section_lock,
    is_canon_proposal_post_path,
    load_pending_canon_proposal_revision_for_book,
    stream_revise_and_apply_canon_proposal,
)
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import (
    Book,
    BookStatus,
    Canon,
    CanonProposalRevision,
    CanonProposalRevisionStatus,
    ProviderConfig,
)
from mynovel.domain.repositories import (
    add_book,
    add_canon,
    add_canon_proposal_revision,
    get_book,
    get_canon_proposal_revision,
    save_provider_config,
)
from mynovel.workflows.canon_proposal import content_hash, locks_hash, section_locks_for_book


class FakeCanonProposalModelClient:
    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        assert stage == "canon_proposal_revision"
        assert messages
        assert response_format == "json"
        return (
            '{"target_section":"characters",'
            '"changed_sections":{"characters":[{"name":"林烬","trait":"外冷内热"}]},'
            '"blocked_sections":[],"summary":"已调整人物。","risks":[]}'
        )


class FailingCanonProposalModelClient:
    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        raise RuntimeError("provider unavailable")


class StreamingCanonProposalModelClient:
    def stream_complete(self, stage: str, messages: list[dict[str, str]], response_format: str):
        assert stage == "canon_proposal_revision"
        assert messages
        assert response_format == "json"
        yield '{"target_section":"characters",'
        yield '"changed_sections":{"characters":[{"name":"林烬","trait":"外冷内热"}]},'
        yield '"blocked_sections":[],"summary":"已调整人物。","risks":[]}'


def _create_draft_book_with_canon(db_path: Path) -> tuple[int, int]:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(session, Book(title="长夜图书馆", genre="奇幻", audience="连载读者"))
        canon = add_canon(
            session,
            Canon(
                book_id=book.id or 0,
                version=1,
                content={"characters": [{"name": "林烬"}], "state_history": []},
            ),
        )
        return book.id or 0, canon.id or 0


def _add_pending_revision(db_path: Path, book_id: int) -> int:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = get_book(session, book_id)
        canon = session.exec(select(Canon).where(Canon.book_id == book_id)).first()
        assert book is not None
        assert canon is not None
        revision = add_canon_proposal_revision(
            session,
            CanonProposalRevision(
                book_id=book_id,
                base_canon_version=canon.version,
                base_content_hash=content_hash(canon.content),
                base_locks_hash=locks_hash(section_locks_for_book(book)),
                target_section="characters",
                instruction="主角改成外冷内热",
                allowed_sections=["characters"],
                locked_sections=[],
                changed_sections={"characters": [{"name": "林烬", "trait": "外冷内热"}]},
                summary="已调整人物。",
            ),
        )
        return revision.id or 0


def test_canon_proposal_post_path_matches_only_proposal_actions() -> None:
    assert is_canon_proposal_post_path("/canon-proposal-lock")
    assert is_canon_proposal_post_path("/canon-proposal-revise")
    assert is_canon_proposal_post_path("/canon-proposal-apply")
    assert is_canon_proposal_post_path("/canon-proposal-discard")
    assert not is_canon_proposal_post_path("/open-book")
    assert not is_canon_proposal_post_path("/books/import")


def test_toggle_canon_proposal_section_lock_redirects_and_persists(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id, _canon_id = _create_draft_book_with_canon(db_path)

    response = handle_toggle_canon_proposal_section_lock(
        {"book_id": str(book_id), "section": "world_rules", "locked": "1"},
        db_path,
    )

    assert response.redirect_to == f"/books/{book_id}/state#world"
    engine = create_engine_for_path(db_path)
    with Session(engine) as session:
        book = get_book(session, book_id)
        assert book is not None
        assert section_locks_for_book(book)["world_rules"] is True


def test_canon_proposal_handlers_reject_invalid_section_and_locked_book(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id, _canon_id = _create_draft_book_with_canon(db_path)

    invalid = handle_toggle_canon_proposal_section_lock(
        {"book_id": str(book_id), "section": "unknown", "locked": "1"},
        db_path,
    )

    assert invalid.status == HTTPStatus.BAD_REQUEST

    engine = create_engine_for_path(db_path)
    with Session(engine) as session:
        book = get_book(session, book_id)
        assert book is not None
        book.status = BookStatus.CANON_LOCKED
        session.add(book)
        session.commit()

    locked = handle_create_canon_proposal_revision(
        {
            "book_id": str(book_id),
            "target_section": "characters",
            "instruction": "主角改成外冷内热",
        },
        db_path,
        model_client=FakeCanonProposalModelClient(),
    )

    assert locked.status == HTTPStatus.BAD_REQUEST


def test_load_pending_canon_proposal_revision_for_book_returns_same_book_pending(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id, _canon_id = _create_draft_book_with_canon(db_path)
    revision_id = _add_pending_revision(db_path, book_id)

    revision = load_pending_canon_proposal_revision_for_book(db_path, book_id, revision_id)

    assert revision is not None
    assert revision.id == revision_id


def test_load_pending_canon_proposal_revision_ignores_cross_book_and_non_pending(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id, _canon_id = _create_draft_book_with_canon(db_path)
    other_book_id, _other_canon_id = _create_draft_book_with_canon(db_path)
    revision_id = _add_pending_revision(db_path, book_id)

    assert (
        load_pending_canon_proposal_revision_for_book(db_path, other_book_id, revision_id) is None
    )

    engine = create_engine_for_path(db_path)
    with Session(engine) as session:
        revision = get_canon_proposal_revision(session, revision_id)
        assert revision is not None
        revision.status = CanonProposalRevisionStatus.DISCARDED
        session.add(revision)
        session.commit()

    assert load_pending_canon_proposal_revision_for_book(db_path, book_id, revision_id) is None


def test_create_canon_proposal_revision_with_fake_client_redirects_to_preview(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id, _canon_id = _create_draft_book_with_canon(db_path)

    response = handle_create_canon_proposal_revision(
        {
            "book_id": str(book_id),
            "target_section": "characters",
            "instruction": "主角改成外冷内热",
        },
        db_path,
        model_client=FakeCanonProposalModelClient(),
    )

    assert response.redirect_to is not None
    assert response.redirect_to.startswith(f"/books/{book_id}/state?revision_id=")
    assert response.redirect_to.endswith("#characters")


def test_create_canon_proposal_revision_without_fake_client_redirects_to_running_job(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id, _canon_id = _create_draft_book_with_canon(db_path)
    engine = create_engine_for_path(db_path)
    with Session(engine) as session:
        save_provider_config(
            session,
            ProviderConfig(
                llm_base_url="https://api.example.test/v1",
                llm_api_key="sk-test",
                llm_model="gpt-test",
                embedding_use_llm_credentials=True,
                embedding_base_url="https://api.example.test/v1",
                embedding_model="embedding-test",
                rerank_use_llm_credentials=True,
                rerank_base_url="",
                rerank_model="rerank-test",
            ),
        )

    response = handle_create_canon_proposal_revision(
        {
            "book_id": str(book_id),
            "target_section": "characters",
            "instruction": "补全人物设定",
        },
        db_path,
        start_background=False,
    )

    assert response.redirect_to is not None
    assert response.redirect_to.startswith(f"/books/{book_id}/state?revision_id=")
    assert response.redirect_to.endswith("#canon-revision-job")

    revision_id = int(response.redirect_to.split("revision_id=", 1)[1].split("#", 1)[0])
    revision = load_pending_canon_proposal_revision_for_book(db_path, book_id, revision_id)

    assert revision is not None
    assert revision.status == CanonProposalRevisionStatus.RUNNING


def test_create_canon_proposal_revision_requires_provider_config_without_client(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id, _canon_id = _create_draft_book_with_canon(db_path)

    response = handle_create_canon_proposal_revision(
        {
            "book_id": str(book_id),
            "target_section": "characters",
            "instruction": "主角改成外冷内热",
        },
        db_path,
    )

    assert response.status == HTTPStatus.BAD_REQUEST

    engine = create_engine_for_path(db_path)
    with Session(engine) as session:
        save_provider_config(
            session,
            ProviderConfig(
                llm_base_url="https://api.example.test/v1",
                llm_model="gpt-test",
                embedding_base_url="",
                embedding_model="",
            ),
        )

    incomplete = handle_create_canon_proposal_revision(
        {
            "book_id": str(book_id),
            "target_section": "characters",
            "instruction": "主角改成外冷内热",
        },
        db_path,
    )

    assert incomplete.status == HTTPStatus.BAD_REQUEST


def test_create_canon_proposal_revision_returns_bad_gateway_for_model_failure(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id, _canon_id = _create_draft_book_with_canon(db_path)

    response = handle_create_canon_proposal_revision(
        {
            "book_id": str(book_id),
            "target_section": "characters",
            "instruction": "主角改成外冷内热",
        },
        db_path,
        model_client=FailingCanonProposalModelClient(),
    )

    assert response.status == HTTPStatus.BAD_GATEWAY
    assert "provider unavailable" in response.body


def test_stream_revise_and_apply_canon_proposal_yields_chunks_and_persists(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id, _canon_id = _create_draft_book_with_canon(db_path)

    events = list(
        stream_revise_and_apply_canon_proposal(
            {
                "book_id": str(book_id),
                "target_section": "characters",
                "instruction": "主角改成外冷内热",
            },
            db_path,
            model_client=StreamingCanonProposalModelClient(),
        )
    )

    assert [event["type"] for event in events] == [
        "started",
        "chunk",
        "chunk",
        "chunk",
        "applying",
        "done",
    ]
    assert events[1]["text"] == '{"target_section":"characters",'
    assert events[-1]["message"] == "AI 修改已写入设定。"
    assert events[-1]["state"]["canonSections"][1]["content"] == [
        {"name": "林烬", "trait": "外冷内热"}
    ]

    engine = create_engine_for_path(db_path)
    with Session(engine) as session:
        canon = session.exec(select(Canon).where(Canon.book_id == book_id)).first()
        assert canon is not None
        assert canon.content["characters"] == [{"name": "林烬", "trait": "外冷内热"}]


def test_apply_and_discard_canon_proposal_revision_handlers(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id, _canon_id = _create_draft_book_with_canon(db_path)
    apply_revision_id = _add_pending_revision(db_path, book_id)

    applied = handle_apply_canon_proposal_revision(
        {"book_id": str(book_id), "revision_id": str(apply_revision_id)},
        db_path,
    )

    assert applied.redirect_to == f"/books/{book_id}/state#characters"
    engine = create_engine_for_path(db_path)
    with Session(engine) as session:
        revision = get_canon_proposal_revision(session, apply_revision_id)
        assert revision is not None
        assert revision.status == CanonProposalRevisionStatus.APPLIED

    discard_revision_id = _add_pending_revision(db_path, book_id)
    discarded = handle_discard_canon_proposal_revision(
        {"book_id": str(book_id), "revision_id": str(discard_revision_id)},
        db_path,
    )

    assert discarded.redirect_to == f"/books/{book_id}/state#characters"
    with Session(engine) as session:
        revision = get_canon_proposal_revision(session, discard_revision_id)
        assert revision is not None
        assert revision.status == CanonProposalRevisionStatus.DISCARDED


def test_load_pending_canon_proposal_revision_returns_none_for_unknown_stale_and_applied(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id, _canon_id = _create_draft_book_with_canon(db_path)

    assert load_pending_canon_proposal_revision_for_book(db_path, book_id, 999) is None

    stale_revision_id = _add_pending_revision(db_path, book_id)
    engine = create_engine_for_path(db_path)
    with Session(engine) as session:
        canon = session.exec(select(Canon).where(Canon.book_id == book_id)).first()
        assert canon is not None
        canon.content = {"characters": [{"name": "已变更"}], "state_history": []}
        session.add(canon)
        session.commit()

    assert (
        load_pending_canon_proposal_revision_for_book(db_path, book_id, stale_revision_id) is None
    )

    applied_revision_id = _add_pending_revision(db_path, book_id)
    with Session(engine) as session:
        revision = get_canon_proposal_revision(session, applied_revision_id)
        assert revision is not None
        revision.status = CanonProposalRevisionStatus.APPLIED
        session.add(revision)
        session.commit()

    assert (
        load_pending_canon_proposal_revision_for_book(db_path, book_id, applied_revision_id) is None
    )
