from __future__ import annotations

import json
from collections.abc import Callable
from http import HTTPStatus
from pathlib import Path
from typing import Any

from mynovel.api_errors import ApiResponse, api_error, invalid_json_response
from mynovel.api_open_book import (
    accept_blueprint_json,
    create_open_book_blueprint_json,
    get_blueprint_json,
    retry_blueprint_json,
    revise_blueprint_json,
)
from mynovel.api_provider_config import get_provider_config_json, save_provider_config_json
from mynovel.api_serializers import app_bootstrap_payload, books_payload
from mynovel.api_serializers import book_detail_payload


def dispatch_api_get(path: str, query: str, db_path: Path) -> ApiResponse:
    if path == "/api/app/bootstrap":
        return ApiResponse(HTTPStatus.OK, app_bootstrap_payload(db_path))
    if path == "/api/books":
        return ApiResponse(HTTPStatus.OK, books_payload(db_path))
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


def _parse_blueprint_action_api_path(path: str) -> tuple[int, str] | None:
    parts = path.strip("/").split("/")
    if len(parts) != 4 or parts[:2] != ["api", "blueprints"]:
        return None
    try:
        blueprint_id = int(parts[2])
    except ValueError:
        blueprint_id = 0
    return blueprint_id, parts[3]
