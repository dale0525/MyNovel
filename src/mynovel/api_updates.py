from __future__ import annotations

from http import HTTPStatus
import json
import platform
from pathlib import Path
import subprocess
import sys
from typing import Any

from mynovel import __version__
from mynovel.api_errors import ApiResponse, api_error
from mynovel.update import check_for_update, prepare_update_install
from mynovel.update_security import fetch_safe_update_manifest

DEFAULT_UPDATE_REPOSITORY_URL = "https://github.com/dale0525/MyNovel"
SUPPORTED_UPDATE_PLATFORMS = frozenset({"macos-arm64", "macos-x64", "windows-x64"})


def update_defaults_json() -> ApiResponse:
    update_platform = detect_update_platform()
    return ApiResponse(
        HTTPStatus.OK,
        {
            "currentVersion": __version__,
            "platform": update_platform,
            "manifestUrl": default_update_manifest_url(update_platform),
        },
    )


def check_update_json(body: dict[str, Any]) -> ApiResponse:
    try:
        manifest_url = _manifest_url_from_body(body)
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
    try:
        manifest_url = _manifest_url_from_body(body)
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


def reveal_staged_update_json(db_path: Path, body: dict[str, Any]) -> ApiResponse:
    try:
        plan_path = _optional_text(body, "planPath", "plan_path")
        if not plan_path:
            raise ValueError("Update install plan path is required.")
        opened_path = reveal_staged_update_location(db_path, Path(plan_path))
    except Exception as error:  # noqa: BLE001
        return api_error(HTTPStatus.BAD_REQUEST, "update_action_failed", str(error))
    return ApiResponse(HTTPStatus.OK, {"openedPath": str(opened_path)})


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


def reveal_staged_update_location(db_path: Path, plan_path: Path) -> Path:
    updates_root = (db_path.parent / "updates").resolve()
    resolved_plan = plan_path.expanduser().resolve()
    if not _is_relative_to(resolved_plan, updates_root):
        raise ValueError("Update install plan is outside the update workspace.")
    payload = json.loads(resolved_plan.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Update install plan is invalid.")
    artifact_path = payload.get("artifact_path")
    if not isinstance(artifact_path, str) or not artifact_path.strip():
        raise ValueError("Update install plan does not include an artifact path.")
    resolved_artifact = Path(artifact_path).expanduser().resolve()
    if not _is_relative_to(resolved_artifact, updates_root):
        raise ValueError("Update artifact is outside the update workspace.")
    if not resolved_artifact.exists():
        raise ValueError("Update artifact does not exist.")
    artifact_dir = resolved_artifact.parent
    open_update_artifact_location(artifact_dir)
    return artifact_dir


def open_update_artifact_location(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    if sys.platform == "win32":
        subprocess.Popen(["explorer", str(path)])
        return
    subprocess.Popen(["xdg-open", str(path)])


def detect_update_platform() -> str:
    if sys.platform == "darwin":
        machine = platform.machine().strip().lower()
        if machine in {"arm64", "aarch64"}:
            return "macos-arm64"
        return "macos-x64"
    if sys.platform == "win32":
        return "windows-x64"
    return "unsupported"


def default_update_manifest_url(update_platform: str) -> str | None:
    if update_platform not in SUPPORTED_UPDATE_PLATFORMS:
        return None
    return f"{DEFAULT_UPDATE_REPOSITORY_URL}/releases/latest/download/update-{update_platform}.json"


def _manifest_url_from_body(body: dict[str, Any]) -> str:
    manifest_url = _optional_text(body, "manifestUrl", "manifest_url")
    if manifest_url:
        return manifest_url
    default_url = default_update_manifest_url(detect_update_platform())
    if default_url:
        return default_url
    raise ValueError("Current platform does not have an update manifest.")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _optional_text(body: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = body.get(key)
        if value is None:
            continue
        text = str(value).strip()
        return text or None
    return None
