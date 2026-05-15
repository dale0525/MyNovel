from __future__ import annotations

import json
from collections.abc import Callable
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from mynovel.api_errors import ApiResponse, api_error, invalid_json_response
from mynovel.api_open_book import (
    accept_blueprint_json,
    create_open_book_blueprint_json,
    get_blueprint_json,
    retry_blueprint_json,
    revise_blueprint_json,
)
from mynovel.api_provider_config import get_provider_config_json, save_provider_config_json
from mynovel.api_serializers import (
    app_bootstrap_payload,
    book_detail_payload,
    books_payload,
    canon_proposal_revision_payload,
    trusted_state_payload,
)
from mynovel.canon_proposal_server import handle_create_canon_proposal_revision
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.workflows.canon_proposal import (
    apply_canon_proposal_revision,
    discard_canon_proposal_revision,
    set_canon_proposal_section_lock,
)
from mynovel.workflows.open_book import lock_canon_foundation
from sqlmodel import Session


def dispatch_api_get(path: str, query: str, db_path: Path) -> ApiResponse:
    if path == "/api/app/bootstrap":
        return ApiResponse(HTTPStatus.OK, app_bootstrap_payload(db_path))
    if path == "/api/books":
        return ApiResponse(HTTPStatus.OK, books_payload(db_path))
    book_state_id = _parse_book_state_api_path(path)
    if book_state_id is not None:
        payload = trusted_state_payload(db_path, book_state_id, _revision_id_from_query(query))
        if payload is None:
            return api_error(HTTPStatus.NOT_FOUND, "book_not_found", "Book not found.")
        return ApiResponse(HTTPStatus.OK, payload)
    book_id = _parse_book_api_path(path)
    if book_id is not None:
        payload = book_detail_payload(db_path, book_id)
        if payload is None:
            return api_error(HTTPStatus.NOT_FOUND, "book_not_found", "Book not found.")
        return ApiResponse(HTTPStatus.OK, payload)
    blueprint_id = _parse_blueprint_api_path(path)
    if blueprint_id is not None:
        return get_blueprint_json(db_path, blueprint_id)
    if path == "/api/provider-config":
        return get_provider_config_json(db_path)
    return api_error(HTTPStatus.NOT_FOUND, "not_found", "API route not found.")


def dispatch_api_post(path: str, body: dict[str, Any], db_path: Path) -> ApiResponse:
    if path in {"/api/provider-config", "/api/provider-config/validate"}:
        return save_provider_config_json(db_path, body)
    if path == "/api/open-book":
        return create_open_book_blueprint_json(db_path, body)
    state_lock_book_id = _parse_book_state_lock_api_path(path)
    if state_lock_book_id is not None:
        return _lock_book_state_json(db_path, state_lock_book_id)
    canon_proposal_action = _parse_book_canon_proposal_action_api_path(path)
    if canon_proposal_action is not None:
        book_id, action = canon_proposal_action
        return _canon_proposal_action_json(db_path, book_id, action, body)
    blueprint_action = _parse_blueprint_action_api_path(path)
    if blueprint_action is not None:
        blueprint_id, action = blueprint_action
        if action == "retry":
            return retry_blueprint_json(db_path, blueprint_id)
        if action == "revise":
            return revise_blueprint_json(db_path, blueprint_id, body)
        if action == "accept":
            return accept_blueprint_json(db_path, blueprint_id, body)
    return api_error(HTTPStatus.NOT_FOUND, "not_found", "API route not found.")


def read_api_json_body(
    content_length: str | None,
    read: Callable[[int], bytes],
) -> tuple[dict[str, Any], ApiResponse | None]:
    try:
        length = int("0" if content_length is None else content_length)
        if length < 0:
            raise ValueError
        raw_body = b"" if length == 0 else read(length)
        if len(raw_body) != length:
            raise ValueError
        body = {} if length == 0 else json.loads(raw_body.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return {}, invalid_json_response()
    if not isinstance(body, dict):
        return {}, invalid_json_response()
    return body, None


def _parse_blueprint_api_path(path: str) -> int | None:
    parts = path.strip("/").split("/")
    if len(parts) != 3 or parts[:2] != ["api", "blueprints"]:
        return None
    try:
        return int(parts[2])
    except ValueError:
        return 0


def _parse_book_api_path(path: str) -> int | None:
    parts = path.strip("/").split("/")
    if len(parts) != 3 or parts[:2] != ["api", "books"]:
        return None
    try:
        return int(parts[2])
    except ValueError:
        return 0


def _parse_book_state_api_path(path: str) -> int | None:
    parts = path.strip("/").split("/")
    if len(parts) != 4 or parts[:2] != ["api", "books"] or parts[3] != "state":
        return None
    try:
        return int(parts[2])
    except ValueError:
        return 0


def _parse_book_state_lock_api_path(path: str) -> int | None:
    parts = path.strip("/").split("/")
    if len(parts) != 5 or parts[:2] != ["api", "books"] or parts[3:] != ["state", "lock"]:
        return None
    try:
        return int(parts[2])
    except ValueError:
        return 0


def _parse_book_canon_proposal_action_api_path(path: str) -> tuple[int, str] | None:
    parts = path.strip("/").split("/")
    if len(parts) != 5 or parts[:2] != ["api", "books"] or parts[3] != "canon-proposals":
        return None
    try:
        book_id = int(parts[2])
    except ValueError:
        book_id = 0
    return book_id, parts[4]


def _parse_blueprint_action_api_path(path: str) -> tuple[int, str] | None:
    parts = path.strip("/").split("/")
    if len(parts) != 4 or parts[:2] != ["api", "blueprints"]:
        return None
    try:
        blueprint_id = int(parts[2])
    except ValueError:
        blueprint_id = 0
    return blueprint_id, parts[3]


def _revision_id_from_query(query: str) -> int | None:
    parsed = parse_qs(query, keep_blank_values=False)
    values = parsed.get("revisionId") or parsed.get("revision_id")
    raw_value = values[0] if values else None
    return _int_value(raw_value)


def _lock_book_state_json(db_path: Path, book_id: int) -> ApiResponse:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    try:
        with Session(engine) as session:
            lock_canon_foundation(session, book_id)
    except ValueError as error:
        return api_error(
            HTTPStatus.BAD_REQUEST,
            "trusted_state_lock_failed",
            str(error),
        )
    payload = trusted_state_payload(db_path, book_id)
    if payload is None:
        return api_error(HTTPStatus.NOT_FOUND, "book_not_found", "Book not found.")
    payload["redirectTo"] = f"/books/{book_id}"
    return ApiResponse(HTTPStatus.OK, payload)


def _canon_proposal_action_json(
    db_path: Path,
    book_id: int,
    action: str,
    body: dict[str, Any],
) -> ApiResponse:
    if action == "apply":
        return _apply_canon_proposal_revision_json(db_path, book_id, body)
    if action == "discard":
        return _discard_canon_proposal_revision_json(db_path, book_id, body)
    if action == "revise":
        return _revise_canon_proposal_json(db_path, book_id, body)
    if action == "lock":
        return _toggle_canon_proposal_section_lock_json(db_path, book_id, body)
    return api_error(HTTPStatus.NOT_FOUND, "not_found", "API route not found.")


def _apply_canon_proposal_revision_json(
    db_path: Path,
    book_id: int,
    body: dict[str, Any],
) -> ApiResponse:
    revision_id = _body_int(body, "revisionId", "revision_id")
    try:
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            revision = apply_canon_proposal_revision(session, book_id, revision_id or 0)
    except ValueError as error:
        return _canon_proposal_action_error(error)
    return ApiResponse(HTTPStatus.OK, {"revision": canon_proposal_revision_payload(revision)})


def _discard_canon_proposal_revision_json(
    db_path: Path,
    book_id: int,
    body: dict[str, Any],
) -> ApiResponse:
    revision_id = _body_int(body, "revisionId", "revision_id")
    try:
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            revision = discard_canon_proposal_revision(session, book_id, revision_id or 0)
    except ValueError as error:
        return _canon_proposal_action_error(error)
    return ApiResponse(HTTPStatus.OK, {"revision": canon_proposal_revision_payload(revision)})


def _toggle_canon_proposal_section_lock_json(
    db_path: Path,
    book_id: int,
    body: dict[str, Any],
) -> ApiResponse:
    section = str(body.get("section") or "")
    locked = _body_bool(body, "locked")
    if locked is None:
        return _canon_proposal_action_error(ValueError("Canon proposal lock value must be boolean."))
    try:
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            set_canon_proposal_section_lock(session, book_id, section, locked)
    except ValueError as error:
        return _canon_proposal_action_error(error)
    payload = trusted_state_payload(db_path, book_id)
    if payload is None:
        return api_error(HTTPStatus.NOT_FOUND, "book_not_found", "Book not found.")
    return ApiResponse(HTTPStatus.OK, payload)


def _revise_canon_proposal_json(
    db_path: Path,
    book_id: int,
    body: dict[str, Any],
) -> ApiResponse:
    response = handle_create_canon_proposal_revision(
        {
            "book_id": str(book_id),
            "target_section": str(body.get("targetSection") or body.get("target_section") or ""),
            "instruction": str(body.get("instruction") or ""),
        },
        db_path,
    )
    if response.status != HTTPStatus.OK or response.redirect_to is None:
        return api_error(
            response.status,
            "canon_proposal_action_failed",
            response.body or "Canon proposal action failed.",
        )
    revision_id = _revision_id_from_redirect(response.redirect_to)
    redirect_to = f"/books/{book_id}/state"
    if revision_id is not None:
        redirect_to = f"{redirect_to}?revisionId={revision_id}"
    return ApiResponse(
        HTTPStatus.ACCEPTED,
        {"revisionId": revision_id, "redirectTo": redirect_to},
    )


def _revision_id_from_redirect(redirect_to: str) -> int | None:
    if "revision_id=" not in redirect_to:
        return None
    raw_value = redirect_to.split("revision_id=", 1)[1].split("#", 1)[0].split("&", 1)[0]
    return _int_value(raw_value)


def _canon_proposal_action_error(error: ValueError) -> ApiResponse:
    return api_error(
        HTTPStatus.BAD_REQUEST,
        "canon_proposal_action_failed",
        str(error),
    )


def _body_int(body: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = _int_value(body.get(key))
        if value is not None:
            return value
    return None


def _body_bool(body: dict[str, Any], *keys: str) -> bool | None:
    for key in keys:
        if key not in body:
            continue
        value = body.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
        return None
    return None


def _int_value(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
