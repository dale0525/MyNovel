from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from sqlmodel import Session

from mynovel.api_routes import dispatch_api_get, dispatch_api_post
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import (
    BlueprintStatus,
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
