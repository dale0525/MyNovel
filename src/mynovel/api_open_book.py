from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from threading import Lock
from typing import Any

from sqlmodel import Session

from mynovel.api_errors import ApiResponse, api_error
from mynovel.api_serializers import blueprint_payload, is_provider_config_validated
from mynovel.blueprint_acceptance import (
    BlueprintNotFoundError,
    BlueprintNotReadyError,
    BlueprintTitleSelectionError,
)
from mynovel.blueprint_jobs import reset_blueprint_for_retry, start_blueprint_job
from mynovel.blueprint_revision import create_revision_blueprint_job, revision_notes_from_form
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintAcceptance, BlueprintStatus, Book
from mynovel.domain.repositories import (
    get_book,
    get_open_book_blueprint,
    get_provider_config,
    get_provider_config_validation,
)
from mynovel.word_targets import book_idea_from_form
from mynovel.workflows.open_book import create_draft_book_from_blueprint_in_session
from mynovel.workflows.open_book_blueprint import create_blueprint_job


_blueprint_action_locks_guard = Lock()
_blueprint_action_locks: dict[int, Lock] = {}


class BlueprintAcceptanceInProgressError(RuntimeError):
    pass


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
    with _blueprint_action_lock(blueprint_id):
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
    form = _string_form(
        {
            **body,
            "blueprint_id": blueprint_id,
            "selected_title": body.get("selectedTitle", body.get("selected_title", "")),
        }
    )
    try:
        book = accept_blueprint_form_safely(db_path, form)
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
    except BlueprintAcceptanceInProgressError:
        return _acceptance_in_progress_response()
    book_id = book.id or 0
    return _accepted_book_response(book_id)


def accept_blueprint_form_safely(db_path: Path, form: dict[str, str]) -> Book:
    try:
        blueprint_id = int(form.get("blueprint_id", "0") or "0")
    except ValueError as error:
        raise BlueprintNotFoundError("Blueprint not found.") from error
    with _blueprint_action_lock(blueprint_id):
        return _accept_blueprint_form_transactionally(db_path, blueprint_id, form)


def _accept_blueprint_form_transactionally(
    db_path: Path,
    blueprint_id: int,
    form: dict[str, str],
) -> Book:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        existing_book_id = _accepted_book_id_in_session(session, blueprint_id)
        if existing_book_id is not None:
            book = get_book(session, existing_book_id)
            if book is not None:
                return book

        acceptance = session.get(BlueprintAcceptance, blueprint_id)
        if acceptance is not None and acceptance.book_id is None:
            raise BlueprintAcceptanceInProgressError("Blueprint acceptance is already in progress.")

        blueprint = get_open_book_blueprint(session, blueprint_id)
        if blueprint is None:
            raise BlueprintNotFoundError("Blueprint not found.")
        if blueprint.status != BlueprintStatus.SUCCEEDED:
            raise BlueprintNotReadyError("Blueprint is not ready.")

        try:
            book = create_draft_book_from_blueprint_in_session(
                session,
                blueprint,
                selected_title=form.get("selected_title", ""),
                lock_foundation=False,
            )
            if book.id is None:
                raise ValueError("Book must be persisted before recording acceptance.")
            session.add(BlueprintAcceptance(blueprint_id=blueprint_id, book_id=book.id))
            session.commit()
            session.refresh(book)
            return book
        except ValueError as error:
            session.rollback()
            raise BlueprintTitleSelectionError(blueprint) from error
        except Exception:
            session.rollback()
            raise


def _accepted_book_id_in_session(session: Session, blueprint_id: int) -> int | None:
    acceptance = session.get(BlueprintAcceptance, blueprint_id)
    if acceptance is not None:
        if acceptance.book_id is None or acceptance.book_id <= 0:
            return None
        if get_book(session, acceptance.book_id) is None:
            return None
        return acceptance.book_id

    blueprint = get_open_book_blueprint(session, blueprint_id)
    if blueprint is None:
        return None
    raw_book_id = blueprint.content.get("accepted_book_id")
    if not isinstance(raw_book_id, int) or raw_book_id <= 0:
        return None
    if get_book(session, raw_book_id) is None:
        return None

    session.add(BlueprintAcceptance(blueprint_id=blueprint_id, book_id=raw_book_id))
    session.commit()
    return raw_book_id


def _blueprint_action_lock(blueprint_id: int) -> Lock:
    with _blueprint_action_locks_guard:
        lock = _blueprint_action_locks.get(blueprint_id)
        if lock is None:
            lock = Lock()
            _blueprint_action_locks[blueprint_id] = lock
        return lock


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


def _acceptance_in_progress_response() -> ApiResponse:
    return api_error(
        HTTPStatus.CONFLICT,
        "blueprint_acceptance_in_progress",
        "蓝图接受正在处理中，请稍后再试。",
    )


def _blueprint_not_found() -> ApiResponse:
    return api_error(HTTPStatus.NOT_FOUND, "blueprint_not_found", "蓝图不存在。")
