from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any

from mynovel import __version__
from mynovel.api_errors import ApiResponse, api_error
from mynovel.update import check_for_update, prepare_update_install
from mynovel.update_security import fetch_safe_update_manifest


def check_update_json(body: dict[str, Any]) -> ApiResponse:
    manifest_url = _optional_text(body, "manifestUrl", "manifest_url") or ""
    try:
        manifest = fetch_safe_update_manifest(manifest_url)
        result = check_for_update(
            __version__,
            manifest,
            skipped_version=_optional_text(body, "skippedVersion", "skipped_version"),
        )
    except Exception as error:  # noqa: BLE001
        return api_error(HTTPStatus.BAD_REQUEST, "update_action_failed", str(error))
    return ApiResponse(HTTPStatus.OK, {"result": _update_result_payload(result)})


def stage_update_json(db_path: Path, body: dict[str, Any]) -> ApiResponse:
    manifest_url = _optional_text(body, "manifestUrl", "manifest_url") or ""
    try:
        manifest = fetch_safe_update_manifest(manifest_url)
        result = check_for_update(__version__, manifest)
        if not result.available:
            return ApiResponse(HTTPStatus.OK, {"result": _update_result_payload(result)})
        staged_install = prepare_update_install(
            manifest,
            db_path,
            db_path.parent / "updates",
            current_version=__version__,
        )
    except Exception as error:  # noqa: BLE001
        return api_error(HTTPStatus.BAD_REQUEST, "update_action_failed", str(error))
    return ApiResponse(
        HTTPStatus.OK,
        {
            "result": _update_result_payload(result),
            "stagedInstall": {
                "planPath": str(staged_install.plan_path),
                "payload": staged_install.payload,
            },
        },
    )


def _update_result_payload(result) -> dict[str, Any]:
    return {
        "available": result.available,
        "version": result.version,
        "url": result.url,
        "sha256": result.sha256,
        "notes": result.notes,
        "publishedAt": result.published_at,
        "sizeLabel": result.size_label,
    }


def _optional_text(body: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = body.get(key)
        if value is None:
            continue
        text = str(value).strip()
        return text or None
    return None
