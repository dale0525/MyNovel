from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from urllib.parse import unquote

STABLE_CONTENT_TYPES = {
    ".js": "text/javascript",
}


@dataclass(frozen=True)
class StaticResponse:
    status: HTTPStatus
    content_type: str
    body: bytes


def resolve_spa_response(path: str, dist_dir: Path) -> StaticResponse:
    if _is_asset_path(path):
        return _resolve_asset_response(path, dist_dir)
    return _resolve_index_response(dist_dir)


def _is_asset_path(path: str) -> bool:
    return unquote(path).startswith("/assets/")


def _resolve_asset_response(path: str, dist_dir: Path) -> StaticResponse:
    asset_root = (dist_dir / "assets").resolve()
    asset_path = (dist_dir / unquote(path).lstrip("/")).resolve()
    try:
        asset_path.relative_to(asset_root)
    except ValueError:
        return _not_found_response()
    if not asset_path.is_file():
        return _not_found_response()
    content_type = _asset_content_type(asset_path)
    return StaticResponse(HTTPStatus.OK, content_type, asset_path.read_bytes())


def _asset_content_type(asset_path: Path) -> str:
    return (
        STABLE_CONTENT_TYPES.get(asset_path.suffix.lower())
        or mimetypes.guess_type(asset_path.name)[0]
        or "application/octet-stream"
    )


def _resolve_index_response(dist_dir: Path) -> StaticResponse:
    index_path = dist_dir / "index.html"
    if not index_path.is_file():
        message = "React frontend is not built. Run `pixi run preview`."
        return StaticResponse(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "text/plain; charset=utf-8",
            message.encode("utf-8"),
        )
    return StaticResponse(
        HTTPStatus.OK,
        "text/html; charset=utf-8",
        index_path.read_bytes(),
    )


def _not_found_response() -> StaticResponse:
    return StaticResponse(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"Not found")
