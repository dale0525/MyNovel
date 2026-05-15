from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any


@dataclass(frozen=True)
class ApiResponse:
    status: HTTPStatus
    body: dict[str, Any]


def api_error(
    status: HTTPStatus,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> ApiResponse:
    return ApiResponse(status, {"error": {"code": code, "message": message, "details": details or {}}})
