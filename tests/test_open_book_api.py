from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from threading import Barrier, BrokenBarrierError, Thread
from typing import Any

import pytest
from sqlmodel import Session, select

import mynovel.api_open_book as api_open_book
import mynovel.blueprint_jobs as blueprint_jobs
from mynovel.api_routes import dispatch_api_get, dispatch_api_post
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import (
    Book,
    BlueprintStatus,
    BlueprintAcceptance,
    OpenBookBlueprint,
    ProviderConfig,
    ProviderConfigValidation,
)
from mynovel.domain.repositories import (
    add_open_book_blueprint,
    get_open_book_blueprint,
    list_open_book_blueprints,
    save_provider_config,
    save_provider_config_validation,
)
from mynovel.provider_config_validation import provider_model_fingerprint


def test_open_book_requires_validated_provider(tmp_path: Path) -> None:
    response = dispatch_api_post("/api/open-book", {"idea": "一座会遗忘人的图书馆"}, tmp_path / "dev.sqlite")

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["error"]["code"] == "provider_not_configured"


def test_open_book_requires_idea_after_provider_validation(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    _save_validated_provider(db_path)

    response = dispatch_api_post("/api/open-book", {"idea": "   "}, db_path)

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["error"]["code"] == "idea_required"


def test_open_book_creates_blueprint_job_and_returns_redirect(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    _save_validated_provider(db_path)
    started: list[int] = []
    monkeypatch.setattr("mynovel.api_open_book.start_blueprint_job", lambda _db, blueprint_id, _config: started.append(blueprint_id))

    response = dispatch_api_post(
        "/api/open-book",
        {
            "idea": "失意档案员重建禁书图书馆",
            "genre": "奇幻",
            "audience": "成人",
        },
        db_path,
    )

    assert response.status == HTTPStatus.ACCEPTED
    blueprint_id = response.body["blueprintId"]
    assert response.body["redirectTo"] == f"/blueprints/{blueprint_id}"
    assert started == [blueprint_id]
    with Session(create_engine_for_path(db_path)) as session:
        blueprint = get_open_book_blueprint(session, blueprint_id)
    assert blueprint is not None
    assert blueprint.status == BlueprintStatus.PENDING
    assert blueprint.idea.startswith("一句灵感：失意档案员重建禁书图书馆")
    assert "- 题材：奇幻" in blueprint.idea


def test_get_blueprint_returns_json_status_content_and_errors(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    blueprint_id = _save_blueprint(
        db_path,
        status=BlueprintStatus.FAILED,
        content={"title_options": ["长夜档案"]},
        parse_error="invalid json",
        error_message="model returned prose",
    )

    response = dispatch_api_get(f"/api/blueprints/{blueprint_id}", "", db_path)

    assert response.status == HTTPStatus.OK
    assert response.body["blueprint"] == {
        "id": blueprint_id,
        "parentId": None,
        "idea": "一座图书馆",
        "version": 1,
        "status": "failed",
        "instruction": None,
        "content": {"title_options": ["长夜档案"]},
        "parseError": "invalid json",
        "errorMessage": "model returned prose",
    }


def test_get_blueprint_filters_legacy_internal_content_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    blueprint_id = _save_blueprint(
        db_path,
        status=BlueprintStatus.SUCCEEDED,
        content={"title_options": ["长夜档案"], "accepted_book_id": 42},
    )

    response = dispatch_api_get(f"/api/blueprints/{blueprint_id}", "", db_path)

    assert response.status == HTTPStatus.OK
    assert response.body["blueprint"]["content"] == {"title_options": ["长夜档案"]}


def test_get_blueprint_missing_returns_json_404(tmp_path: Path) -> None:
    response = dispatch_api_get("/api/blueprints/404", "", tmp_path / "dev.sqlite")

    assert response.status == HTTPStatus.NOT_FOUND
    assert response.body["error"]["code"] == "blueprint_not_found"


def test_retry_blueprint_resets_and_starts_job(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "dev.sqlite"
    _save_validated_provider(db_path)
    blueprint_id = _save_blueprint(
        db_path,
        status=BlueprintStatus.FAILED,
        content={"broken": True},
        parse_error="bad json",
        error_message="bad json",
    )
    started: list[int] = []
    monkeypatch.setattr("mynovel.api_open_book.start_blueprint_job", lambda _db, blueprint_id, _config: started.append(blueprint_id))

    response = dispatch_api_post(f"/api/blueprints/{blueprint_id}/retry", {}, db_path)

    assert response.status == HTTPStatus.ACCEPTED
    assert response.body["blueprintId"] == blueprint_id
    assert started == [blueprint_id]
    with Session(create_engine_for_path(db_path)) as session:
        blueprint = get_open_book_blueprint(session, blueprint_id)
    assert blueprint is not None
    assert blueprint.status == BlueprintStatus.PENDING
    assert blueprint.content == {}
    assert blueprint.parse_error is None
    assert blueprint.error_message is None


def test_retry_rejects_second_attempt_after_first_reset(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "dev.sqlite"
    _save_validated_provider(db_path)
    blueprint_id = _save_blueprint(db_path, status=BlueprintStatus.FAILED)
    started: list[int] = []
    monkeypatch.setattr("mynovel.api_open_book.start_blueprint_job", lambda _db, blueprint_id, _config: started.append(blueprint_id))

    first = dispatch_api_post(f"/api/blueprints/{blueprint_id}/retry", {}, db_path)
    second = dispatch_api_post(f"/api/blueprints/{blueprint_id}/retry", {}, db_path)

    assert first.status == HTTPStatus.ACCEPTED
    assert second.status == HTTPStatus.BAD_REQUEST
    assert second.body["error"]["code"] == "blueprint_action_invalid"
    assert started == [blueprint_id]


def test_retry_rejects_running_blueprint_without_starting_job(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    _save_validated_provider(db_path)
    blueprint_id = _save_blueprint(db_path, status=BlueprintStatus.RUNNING)
    started: list[int] = []
    monkeypatch.setattr("mynovel.api_open_book.start_blueprint_job", lambda _db, blueprint_id, _config: started.append(blueprint_id))

    response = dispatch_api_post(f"/api/blueprints/{blueprint_id}/retry", {}, db_path)

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["error"]["code"] == "blueprint_action_invalid"
    assert started == []
    with Session(create_engine_for_path(db_path)) as session:
        blueprint = get_open_book_blueprint(session, blueprint_id)
    assert blueprint is not None
    assert blueprint.status == BlueprintStatus.RUNNING


def test_revise_blueprint_requires_revision_notes(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    _save_validated_provider(db_path)
    blueprint_id = _save_blueprint(db_path, status=BlueprintStatus.SUCCEEDED)

    response = dispatch_api_post(
        f"/api/blueprints/{blueprint_id}/revise",
        {"revisionNotes": "  "},
        db_path,
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["error"]["code"] == "revision_required"


def test_revise_blueprint_creates_revision_job(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "dev.sqlite"
    _save_validated_provider(db_path)
    blueprint_id = _save_blueprint(db_path, status=BlueprintStatus.SUCCEEDED)
    started: list[int] = []
    monkeypatch.setattr("mynovel.api_open_book.start_blueprint_job", lambda _db, blueprint_id, _config: started.append(blueprint_id))

    response = dispatch_api_post(
        f"/api/blueprints/{blueprint_id}/revise",
        {"revisionNotes": "主角更疯一点"},
        db_path,
    )

    assert response.status == HTTPStatus.ACCEPTED
    revision_id = response.body["blueprintId"]
    assert response.body["redirectTo"] == f"/blueprints/{revision_id}"
    assert started == [revision_id]
    with Session(create_engine_for_path(db_path)) as session:
        revision = get_open_book_blueprint(session, revision_id)
    assert revision is not None
    assert revision.parent_id == blueprint_id
    assert revision.version == 2
    assert revision.instruction == "主角更疯一点"


def test_revision_job_filters_legacy_internal_content_from_previous_blueprint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    parent_id = _save_blueprint(
        db_path,
        status=BlueprintStatus.SUCCEEDED,
        content={"title_options": ["长夜档案"], "accepted_book_id": 42},
    )
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        revision = add_open_book_blueprint(
            session,
            OpenBookBlueprint(
                parent_id=parent_id,
                idea="一座图书馆",
                version=2,
                status=BlueprintStatus.PENDING,
                instruction="加强悬疑感",
            ),
        )
        assert revision.id is not None
        revision_id = revision.id
    captured_previous: list[dict[str, Any] | None] = []

    async def request_blueprint(
        _provider_config: ProviderConfig,
        _idea: str,
        previous_blueprint: dict[str, Any] | None,
        _revision_notes: str | None,
    ) -> str:
        captured_previous.append(previous_blueprint)
        return _valid_blueprint_json()

    monkeypatch.setattr(blueprint_jobs, "request_blueprint", request_blueprint)

    blueprint_jobs.run_blueprint_job(
        db_path,
        revision_id,
        ProviderConfig(
            llm_base_url="https://api.example.test/v1",
            llm_api_key="sk-test",
            llm_model="gpt-test",
            embedding_base_url="https://api.example.test/v1",
            embedding_model="text-embedding-test",
        ),
    )

    assert captured_previous == [{"title_options": ["长夜档案"]}]


def test_revise_rejects_failed_blueprint_without_creating_revision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    _save_validated_provider(db_path)
    blueprint_id = _save_blueprint(db_path, status=BlueprintStatus.FAILED)
    started: list[int] = []
    monkeypatch.setattr("mynovel.api_open_book.start_blueprint_job", lambda _db, blueprint_id, _config: started.append(blueprint_id))

    response = dispatch_api_post(
        f"/api/blueprints/{blueprint_id}/revise",
        {"revisionNotes": "主角更疯一点"},
        db_path,
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["error"]["code"] == "blueprint_action_invalid"
    assert started == []
    with Session(create_engine_for_path(db_path)) as session:
        blueprints = list_open_book_blueprints(session)
    assert [blueprint.id for blueprint in blueprints] == [blueprint_id]


def test_revise_missing_blueprint_does_not_fallback_to_existing_blueprint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    _save_validated_provider(db_path)
    existing_id = _save_blueprint(db_path, status=BlueprintStatus.SUCCEEDED)
    started: list[int] = []
    monkeypatch.setattr("mynovel.api_open_book.start_blueprint_job", lambda _db, blueprint_id, _config: started.append(blueprint_id))

    response = dispatch_api_post(
        "/api/blueprints/999/revise",
        {"revisionNotes": "主角更疯一点"},
        db_path,
    )

    assert response.status == HTTPStatus.NOT_FOUND
    assert response.body["error"]["code"] == "blueprint_not_found"
    assert started == []
    with Session(create_engine_for_path(db_path)) as session:
        blueprints = list_open_book_blueprints(session)
    assert [blueprint.id for blueprint in blueprints] == [existing_id]


def test_accept_blueprint_returns_book_redirect(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    blueprint_id = _save_blueprint(
        db_path,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜档案"],
            "genre": "奇幻",
            "audience": "成人",
            "premise": "档案员追查禁书真相。",
        },
    )

    response = dispatch_api_post(
        f"/api/blueprints/{blueprint_id}/accept",
        {"selectedTitle": "长夜档案"},
        db_path,
    )

    assert response.status == HTTPStatus.OK
    assert response.body["bookId"] > 0
    assert response.body["redirectTo"] == f"/books/{response.body['bookId']}"


def test_accept_blueprint_is_idempotent_for_same_blueprint(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    blueprint_id = _save_blueprint(
        db_path,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜档案"],
            "genre": "奇幻",
            "audience": "成人",
            "premise": "档案员追查禁书真相。",
        },
    )

    first = dispatch_api_post(
        f"/api/blueprints/{blueprint_id}/accept",
        {"selectedTitle": "长夜档案"},
        db_path,
    )
    second = dispatch_api_post(
        f"/api/blueprints/{blueprint_id}/accept",
        {"selectedTitle": "长夜档案"},
        db_path,
    )

    assert first.status == HTTPStatus.OK
    assert second.status == HTTPStatus.OK
    assert second.body["bookId"] == first.body["bookId"]
    payload_response = dispatch_api_get(f"/api/blueprints/{blueprint_id}", "", db_path)
    with Session(create_engine_for_path(db_path)) as session:
        books = list(session.exec(select(Book)))
        blueprint = get_open_book_blueprint(session, blueprint_id)
        acceptance = session.get(BlueprintAcceptance, blueprint_id)
    assert len(books) == 1
    assert blueprint is not None
    assert acceptance is not None
    assert acceptance.book_id == first.body["bookId"]
    assert "accepted_book_id" not in blueprint.content
    assert "accepted_book_id" not in payload_response.body["blueprint"]["content"]


def test_accept_blueprint_reuses_and_migrates_legacy_content_marker(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        existing_book = Book(
            title="长夜档案",
            genre="奇幻",
            audience="成人",
            premise="档案员追查禁书真相。",
        )
        session.add(existing_book)
        session.commit()
        session.refresh(existing_book)
        assert existing_book.id is not None
        blueprint = add_open_book_blueprint(
            session,
            OpenBookBlueprint(
                idea="一座图书馆",
                status=BlueprintStatus.SUCCEEDED,
                content={
                    "title_options": ["长夜档案"],
                    "genre": "奇幻",
                    "audience": "成人",
                    "premise": "档案员追查禁书真相。",
                    "accepted_book_id": existing_book.id,
                },
            ),
        )
        assert blueprint.id is not None
        blueprint_id = blueprint.id
        existing_book_id = existing_book.id

    response = dispatch_api_post(
        f"/api/blueprints/{blueprint_id}/accept",
        {"selectedTitle": "长夜档案"},
        db_path,
    )

    assert response.status == HTTPStatus.OK
    assert response.body["bookId"] == existing_book_id
    with Session(create_engine_for_path(db_path)) as session:
        books = list(session.exec(select(Book)))
        acceptance = session.get(BlueprintAcceptance, blueprint_id)
    assert len(books) == 1
    assert acceptance is not None
    assert acceptance.book_id == existing_book_id


def test_accept_blueprint_rolls_back_when_transactional_creation_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    blueprint_id = _save_blueprint(
        db_path,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜档案"],
            "genre": "奇幻",
            "audience": "成人",
            "premise": "档案员追查禁书真相。",
        },
    )
    original_create = api_open_book.create_draft_book_from_blueprint_in_session
    fail_once = True

    def fail_after_creating_book(*args, **kwargs):
        nonlocal fail_once
        book = original_create(*args, **kwargs)
        if fail_once:
            fail_once = False
            raise RuntimeError("simulated transactional acceptance failure")
        return book

    monkeypatch.setattr(
        api_open_book,
        "create_draft_book_from_blueprint_in_session",
        fail_after_creating_book,
    )

    with pytest.raises(RuntimeError, match="simulated transactional acceptance failure"):
        dispatch_api_post(
            f"/api/blueprints/{blueprint_id}/accept",
            {"selectedTitle": "长夜档案"},
            db_path,
        )
    with Session(create_engine_for_path(db_path)) as session:
        assert list(session.exec(select(Book))) == []
        assert session.get(BlueprintAcceptance, blueprint_id) is None

    second = dispatch_api_post(
        f"/api/blueprints/{blueprint_id}/accept",
        {"selectedTitle": "长夜档案"},
        db_path,
    )

    assert second.status == HTTPStatus.OK
    with Session(create_engine_for_path(db_path)) as session:
        books = list(session.exec(select(Book)))
        acceptance = session.get(BlueprintAcceptance, blueprint_id)
    assert len(books) == 1
    assert acceptance is not None
    assert acceptance.book_id == second.body["bookId"]


def test_legacy_accept_helper_records_acceptance_and_reuses_book(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    blueprint_id = _save_blueprint(
        db_path,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜档案"],
            "genre": "奇幻",
            "audience": "成人",
            "premise": "档案员追查禁书真相。",
        },
    )

    first = api_open_book.accept_blueprint_form_safely(
        db_path,
        {"blueprint_id": str(blueprint_id), "selected_title": "长夜档案"},
    )
    second = api_open_book.accept_blueprint_form_safely(
        db_path,
        {"blueprint_id": str(blueprint_id), "selected_title": "长夜档案"},
    )

    assert first.id == second.id
    with Session(create_engine_for_path(db_path)) as session:
        books = list(session.exec(select(Book)))
        acceptance = session.get(BlueprintAcceptance, blueprint_id)
    assert len(books) == 1
    assert acceptance is not None
    assert acceptance.book_id == first.id


def test_concurrent_accept_blueprint_creates_one_book(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "dev.sqlite"
    blueprint_id = _save_blueprint(
        db_path,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜档案"],
            "genre": "奇幻",
            "audience": "成人",
            "premise": "档案员追查禁书真相。",
        },
    )
    original_create = api_open_book.create_draft_book_from_blueprint_in_session
    barrier = Barrier(2, timeout=1.0)

    def create_after_both_requests_reach_create(*args, **kwargs):
        try:
            barrier.wait()
        except BrokenBarrierError:
            pass
        return original_create(*args, **kwargs)

    monkeypatch.setattr(
        api_open_book,
        "create_draft_book_from_blueprint_in_session",
        create_after_both_requests_reach_create,
    )
    responses: list[dict[str, Any]] = []

    def accept_blueprint() -> None:
        response = dispatch_api_post(
            f"/api/blueprints/{blueprint_id}/accept",
            {"selectedTitle": "长夜档案"},
            db_path,
        )
        responses.append({"status": response.status, "body": response.body})

    threads = [Thread(target=accept_blueprint), Thread(target=accept_blueprint)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert [response["status"] for response in responses] == [HTTPStatus.OK, HTTPStatus.OK]
    book_ids = {response["body"]["bookId"] for response in responses}
    with Session(create_engine_for_path(db_path)) as session:
        books = list(session.exec(select(Book)))
        blueprint = get_open_book_blueprint(session, blueprint_id)
        acceptance = session.get(BlueprintAcceptance, blueprint_id)
    assert len(book_ids) == 1
    assert len(books) == 1
    assert blueprint is not None
    assert acceptance is not None
    assert acceptance.book_id in book_ids
    assert "accepted_book_id" not in blueprint.content


def _save_validated_provider(db_path: Path) -> None:
    config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_api_key="sk-test",
        llm_model="gpt-test",
        embedding_base_url="https://api.example.test/v1",
        embedding_model="text-embedding-test",
        rerank_base_url="https://rerank.example.test/v1",
        rerank_model="rerank-test",
    )
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        save_provider_config(session, config)
        save_provider_config_validation(
            session,
            ProviderConfigValidation(
                llm_fingerprint=provider_model_fingerprint(config, "llm"),
                embedding_fingerprint=provider_model_fingerprint(config, "embedding"),
                rerank_fingerprint=provider_model_fingerprint(config, "rerank"),
            ),
        )


def _save_blueprint(
    db_path: Path,
    *,
    status: BlueprintStatus,
    content: dict | None = None,
    parse_error: str | None = None,
    error_message: str | None = None,
) -> int:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        blueprint = add_open_book_blueprint(
            session,
            OpenBookBlueprint(
                idea="一座图书馆",
                status=status,
                content=content or {},
                parse_error=parse_error,
                error_message=error_message,
            ),
        )
        assert blueprint.id is not None
        return blueprint.id


def _valid_blueprint_json() -> str:
    return """
{
  "title_options": ["长夜档案"],
  "genre": "奇幻",
  "audience": "成人",
  "selling_points": ["禁书悬疑"],
  "protagonist": {"name": "林既明"},
  "world": {"summary": "禁书会吞噬记忆"},
  "central_conflict": "档案员追查禁书真相。",
  "reader_promises": ["真相反转"],
  "chapter_directions": [
    {"title": "第1章", "goal": "发现禁书"},
    {"title": "第2章", "goal": "确认代价"},
    {"title": "第3章", "goal": "遭遇追捕"},
    {"title": "第4章", "goal": "进入密库"},
    {"title": "第5章", "goal": "结识盟友"},
    {"title": "第6章", "goal": "发现旧案"},
    {"title": "第7章", "goal": "误信敌人"},
    {"title": "第8章", "goal": "夺回线索"},
    {"title": "第9章", "goal": "揭开背叛"},
    {"title": "第10章", "goal": "立下目标"}
  ]
}
"""
