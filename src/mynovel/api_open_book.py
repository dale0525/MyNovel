from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any

from sqlmodel import Session

from mynovel.api_errors import ApiResponse, api_error
from mynovel.api_serializers import blueprint_payload, is_provider_config_validated
from mynovel.blueprint_acceptance import (
    BlueprintNotFoundError,
    BlueprintNotReadyError,
    BlueprintTitleSelectionError,
    accept_blueprint_for_foundation_review,
)
from mynovel.blueprint_jobs import reset_blueprint_for_retry, start_blueprint_job
from mynovel.blueprint_revision import create_revision_blueprint_job, revision_notes_from_form
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus
from mynovel.domain.repositories import (
    get_book,
    get_open_book_blueprint,
    get_provider_config,
    get_provider_config_validation,
)
from mynovel.word_targets import book_idea_from_form
from mynovel.workflows.open_book_blueprint import create_blueprint_job


def create_open_book_blueprint_json(db_path: Path, body: dict[str, Any]) -> ApiResponse:
    provider_config = _validated_provider_config(db_path)
    if provider_config is None:
        return api_error(
            HTTPStatus.BAD_REQUEST,
            "provider_not_configured",
            "请先完成模型连接验证。",
        )

    idea = book_idea_from_form(_string_form(body))
    if not idea:
        return api_error(HTTPStatus.BAD_REQUEST, "idea_required", "请先写下故事灵感。")

    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        blueprint = create_blueprint_job(
            session,
            idea=idea,
            version=1,
            instruction=None,
            parent_id=None,
        )
        blueprint_id = blueprint.id
    if blueprint_id is None:
        return api_error(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "blueprint_create_failed",
            "蓝图任务创建失败。",
        )
    start_blueprint_job(db_path, blueprint_id, provider_config)
    return _accepted_blueprint_response(blueprint_id)


def get_blueprint_json(db_path: Path, blueprint_id: int) -> ApiResponse:
    if blueprint_id <= 0:
        return _blueprint_not_found()
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        blueprint = get_open_book_blueprint(session, blueprint_id)
        if blueprint is None:
            return _blueprint_not_found()
        return ApiResponse(HTTPStatus.OK, {"blueprint": blueprint_payload(blueprint)})


def retry_blueprint_json(db_path: Path, blueprint_id: int) -> ApiResponse:
    provider_config = _validated_provider_config(db_path)
    if provider_config is None:
        return api_error(
            HTTPStatus.BAD_REQUEST,
            "provider_not_configured",
            "请先完成模型连接验证。",
        )
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        blueprint = get_open_book_blueprint(session, blueprint_id)
        if blueprint is None:
            return _blueprint_not_found()
        if blueprint.status != BlueprintStatus.FAILED:
            return _invalid_blueprint_action("只有失败的蓝图可以重试。")
        reset_blueprint_for_retry(session, blueprint)
    start_blueprint_job(db_path, blueprint_id, provider_config)
    return _accepted_blueprint_response(blueprint_id)


def revise_blueprint_json(db_path: Path, blueprint_id: int, body: dict[str, Any]) -> ApiResponse:
    provider_config = _validated_provider_config(db_path)
    if provider_config is None:
        return api_error(
            HTTPStatus.BAD_REQUEST,
            "provider_not_configured",
            "请先完成模型连接验证。",
        )
    form = _string_form(
        {
            **body,
            "blueprint_id": blueprint_id,
            "revision_notes": body.get("revisionNotes", body.get("revision_notes", "")),
            "revision_preset": body.get("revisionPreset", body.get("revision_preset", "")),
        }
    )
    revision_notes = revision_notes_from_form(form)
    if not revision_notes:
        return api_error(HTTPStatus.BAD_REQUEST, "revision_required", "请填写修订方向。")

    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        parent = get_open_book_blueprint(session, blueprint_id)
        if parent is None:
            return _blueprint_not_found()
        if parent.status != BlueprintStatus.SUCCEEDED:
            return _invalid_blueprint_action("只有已生成的蓝图可以修订。")
        try:
            blueprint = create_revision_blueprint_job(
                session,
                form,
                [],
                revision_notes,
            )
        except ValueError:
            return _blueprint_not_found()
        revision_id = blueprint.id
    if revision_id is None:
        return api_error(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "blueprint_create_failed",
            "蓝图修订任务创建失败。",
        )
    start_blueprint_job(db_path, revision_id, provider_config)
    return _accepted_blueprint_response(revision_id)


def accept_blueprint_json(db_path: Path, blueprint_id: int, body: dict[str, Any]) -> ApiResponse:
    existing_book_id = _accepted_book_id(db_path, blueprint_id)
    if existing_book_id is not None:
        return _accepted_book_response(existing_book_id)

    form = _string_form(
        {
            **body,
            "blueprint_id": blueprint_id,
            "selected_title": body.get("selectedTitle", body.get("selected_title", "")),
        }
    )
    try:
        book = accept_blueprint_for_foundation_review(db_path, form)
    except BlueprintNotFoundError:
        return _blueprint_not_found()
    except BlueprintNotReadyError:
        return api_error(HTTPStatus.BAD_REQUEST, "blueprint_not_ready", "蓝图尚未生成完成。")
    except BlueprintTitleSelectionError:
        return api_error(
            HTTPStatus.BAD_REQUEST,
            "blueprint_title_required",
            "请选择一个蓝图书名。",
        )
    book_id = book.id or 0
    if book_id > 0:
        _record_accepted_book_id(db_path, blueprint_id, book_id)
    return _accepted_book_response(book_id)


def _accepted_book_id(db_path: Path, blueprint_id: int) -> int | None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        blueprint = get_open_book_blueprint(session, blueprint_id)
        if blueprint is None:
            return None
        raw_book_id = blueprint.content.get("accepted_book_id")
        if not isinstance(raw_book_id, int) or raw_book_id <= 0:
            return None
        if get_book(session, raw_book_id) is None:
            return None
        return raw_book_id


def _record_accepted_book_id(db_path: Path, blueprint_id: int, book_id: int) -> None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        blueprint = get_open_book_blueprint(session, blueprint_id)
        if blueprint is None:
            return
        blueprint.content = {**blueprint.content, "accepted_book_id": book_id}
        session.add(blueprint)
        session.commit()


def _validated_provider_config(db_path: Path):
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        config = get_provider_config(session)
        validation = get_provider_config_validation(session)
        if not is_provider_config_validated(config, validation):
            return None
        return config


def _string_form(body: dict[str, Any]) -> dict[str, str]:
    return {key: "" if value is None else str(value).strip() for key, value in body.items()}


def _accepted_blueprint_response(blueprint_id: int) -> ApiResponse:
    return ApiResponse(
        HTTPStatus.ACCEPTED,
        {"blueprintId": blueprint_id, "redirectTo": f"/blueprints/{blueprint_id}"},
    )


def _accepted_book_response(book_id: int) -> ApiResponse:
    return ApiResponse(HTTPStatus.OK, {"bookId": book_id, "redirectTo": f"/books/{book_id}"})


def _invalid_blueprint_action(message: str) -> ApiResponse:
    return api_error(HTTPStatus.BAD_REQUEST, "blueprint_action_invalid", message)


def _blueprint_not_found() -> ApiResponse:
    return api_error(HTTPStatus.NOT_FOUND, "blueprint_not_found", "蓝图不存在。")
