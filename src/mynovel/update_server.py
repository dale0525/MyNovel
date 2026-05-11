from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

from mynovel import __version__
from mynovel.update import check_for_update, fetch_update_manifest, prepare_update_install
from mynovel.update_views import render_update_page


@dataclass(frozen=True)
class UpdatePageResponse:
    body: str
    status: HTTPStatus = HTTPStatus.OK


def handle_check_update(form: Mapping[str, str]) -> UpdatePageResponse:
    manifest_url = form.get("manifest_url", "")
    try:
        manifest = fetch_update_manifest(manifest_url)
        result = check_for_update(
            __version__,
            manifest,
            skipped_version=form.get("skipped_version") or None,
        )
    except Exception as error:  # noqa: BLE001
        return UpdatePageResponse(
            render_update_page(message=str(error), manifest_url=manifest_url),
            HTTPStatus.BAD_REQUEST,
        )
    return UpdatePageResponse(render_update_page(result, manifest_url=manifest_url))


def handle_stage_update(form: Mapping[str, str], db_path: Path) -> UpdatePageResponse:
    manifest_url = form.get("manifest_url", "")
    try:
        manifest = fetch_update_manifest(manifest_url)
        result = check_for_update(__version__, manifest)
        if not result.available:
            return UpdatePageResponse(
                render_update_page(
                    result,
                    message="当前没有可准备的稳定更新。",
                    manifest_url=manifest_url,
                )
            )
        staged_install = prepare_update_install(manifest, db_path, db_path.parent / "updates")
    except Exception as error:  # noqa: BLE001
        return UpdatePageResponse(
            render_update_page(message=str(error), manifest_url=manifest_url),
            HTTPStatus.BAD_REQUEST,
        )
    return UpdatePageResponse(
        render_update_page(
            result,
            message="更新已下载并准备好；请手动确认安装，不会静默安装。",
            manifest_url=manifest_url,
            staged_install=staged_install,
        )
    )
