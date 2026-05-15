from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any

from mynovel.api_errors import ApiResponse, api_error
from mynovel.api_serializers import app_bootstrap_payload


def dispatch_api_get(path: str, query: str, db_path: Path) -> ApiResponse:
    if path == "/api/app/bootstrap":
        return ApiResponse(HTTPStatus.OK, app_bootstrap_payload(db_path))
    return api_error(HTTPStatus.NOT_FOUND, "not_found", "API route not found.")


def dispatch_api_post(path: str, body: dict[str, Any], db_path: Path) -> ApiResponse:
    return api_error(HTTPStatus.NOT_FOUND, "not_found", "API route not found.")
