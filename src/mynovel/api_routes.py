from __future__ import annotations

import json
from collections.abc import Callable
from http import HTTPStatus
from pathlib import Path
from typing import Any

from mynovel.api_errors import ApiResponse, api_error, invalid_json_response
from mynovel.api_provider_config import get_provider_config_json, save_provider_config_json
from mynovel.api_serializers import app_bootstrap_payload


def dispatch_api_get(path: str, query: str, db_path: Path) -> ApiResponse:
    if path == "/api/app/bootstrap":
        return ApiResponse(HTTPStatus.OK, app_bootstrap_payload(db_path))
    if path == "/api/provider-config":
        return get_provider_config_json(db_path)
    return api_error(HTTPStatus.NOT_FOUND, "not_found", "API route not found.")


def dispatch_api_post(path: str, body: dict[str, Any], db_path: Path) -> ApiResponse:
    if path in {"/api/provider-config", "/api/provider-config/validate"}:
        return save_provider_config_json(db_path, body)
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
