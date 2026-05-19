from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
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
    book_payload,
    book_detail_payload,
    books_payload,
    canon_proposal_revision_payload,
    chapter_review_payload,
    deconstruction_study_payload,
    quality_payload,
    style_asset_payload,
    trusted_state_payload,
)
from mynovel.api_updates import (
    check_update_json,
    reveal_staged_update_json,
    stage_update_json,
    update_defaults_json,
)
from mynovel.book_abandonment import DeleteBookError, delete_book
from mynovel.canon_proposal_server import (
    handle_create_canon_proposal_revision,
    stream_revise_and_apply_canon_proposal,
)
from mynovel.chapter_batch_payload import parse_chapter_batch_ids
from mynovel.chapter_server import queue_chapter_batch_run, queue_chapter_repair, queue_chapter_run
from mynovel.llm_streams import (
    stream_create_open_book_blueprint,
    stream_generate_volume_outline,
    stream_repair_chapter,
    stream_retry_blueprint,
    stream_revise_volume_outline,
    stream_revise_blueprint,
    stream_run_chapter,
    stream_run_chapter_batch,
)
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.repositories import (
    get_book,
    get_chapter,
    get_latest_canon,
    get_provider_config,
    list_chapters_for_book,
)
from mynovel.workflows.canon_proposal import (
    CANON_PROPOSAL_COMPLETION_INSTRUCTION,
    apply_canon_proposal_revision,
    canon_proposal_completion_target,
    discard_canon_proposal_revision,
    section_locks_for_book,
    set_canon_proposal_section_lock,
)
from mynovel.workflows.book_export import export_book_json, export_book_markdown
from mynovel.workflows.book_import import import_book_json
from mynovel.workflows.chapter_pipeline import (
    approve_chapter,
    apply_manual_chapter_edit,
    export_chapter_text,
    return_chapter_for_revision,
)
from mynovel.workflows.open_book import lock_canon_foundation
from mynovel.workflows.quality_enhancement import (
    create_style_asset,
    deconstruct_reference_text,
    generate_quality_snapshot,
)
from mynovel.word_targets import update_book_word_targets
from sqlmodel import Session


@dataclass(frozen=True)
class ApiStreamResponse:
    events: Iterable[dict[str, Any]]
    status: HTTPStatus = HTTPStatus.OK
    content_type: str = "application/x-ndjson; charset=utf-8"


def dispatch_api_get(path: str, query: str, db_path: Path) -> ApiResponse:
    if path == "/api/app/bootstrap":
        return ApiResponse(HTTPStatus.OK, app_bootstrap_payload(db_path))
    if path == "/api/books":
        return ApiResponse(HTTPStatus.OK, books_payload(db_path))
    book_export = _parse_book_export_api_path(path)
    if book_export is not None:
        book_id, export_format = book_export
        return _export_book_json(db_path, book_id, export_format)
    if path == "/api/updates":
        return update_defaults_json()
    book_quality_id = _parse_book_quality_api_path(path)
    if book_quality_id is not None:
        payload = quality_payload(db_path, book_quality_id)
        if payload is None:
            return api_error(HTTPStatus.NOT_FOUND, "book_not_found", "Book not found.")
        return ApiResponse(HTTPStatus.OK, payload)
    book_state_id = _parse_book_state_api_path(path)
    if book_state_id is not None:
        payload = trusted_state_payload(db_path, book_state_id, _revision_id_from_query(query))
        if payload is None:
            return api_error(HTTPStatus.NOT_FOUND, "book_not_found", "Book not found.")
        return ApiResponse(HTTPStatus.OK, payload)
    book_detail_id = _parse_book_api_path(path)
    if book_detail_id is not None:
        payload = book_detail_payload(db_path, book_detail_id)
        if payload is None:
            return api_error(HTTPStatus.NOT_FOUND, "book_not_found", "Book not found.")
        return ApiResponse(HTTPStatus.OK, payload)
    blueprint_id = _parse_blueprint_api_path(path)
    if blueprint_id is not None:
        return get_blueprint_json(db_path, blueprint_id)
    if path == "/api/provider-config":
        return get_provider_config_json(db_path)
    chapter_export_id = _parse_chapter_export_api_path(path)
    if chapter_export_id is not None:
        return _export_chapter_text_json(db_path, chapter_export_id)
    chapter_id = _parse_chapter_api_path(path)
    if chapter_id is not None:
        payload = chapter_review_payload(db_path, chapter_id)
        if payload is None:
            return api_error(HTTPStatus.NOT_FOUND, "chapter_not_found", "Chapter not found.")
        return ApiResponse(HTTPStatus.OK, payload)
    return api_error(HTTPStatus.NOT_FOUND, "not_found", "API route not found.")


def dispatch_api_post(path: str, body: dict[str, Any], db_path: Path) -> ApiResponse:
    if path in {"/api/provider-config", "/api/provider-config/validate"}:
        return save_provider_config_json(db_path, body)
    if path == "/api/open-book":
        return create_open_book_blueprint_json(db_path, body)
    if path == "/api/books/import":
        return _import_book_json(db_path, body)
    delete_book_id = _parse_book_delete_api_path(path)
    if delete_book_id is not None:
        return _delete_book_json(db_path, delete_book_id)
    book_word_targets_id = _parse_book_word_targets_api_path(path)
    if book_word_targets_id is not None:
        return _update_book_word_targets_json(db_path, book_word_targets_id, body)
    if path == "/api/updates/check":
        return check_update_json(body)
    if path == "/api/updates/stage":
        return stage_update_json(db_path, body)
    if path == "/api/updates/reveal":
        return reveal_staged_update_json(db_path, body)
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
    quality_action = _parse_book_quality_action_api_path(path)
    if quality_action is not None:
        book_id, action = quality_action
        return _quality_action_json(db_path, book_id, action, body)
    book_chapter_action = _parse_book_chapter_action_api_path(path)
    if book_chapter_action is not None:
        book_id, action = book_chapter_action
        if action == "run-batch":
            return _run_chapter_batch_json(db_path, book_id, body)
        return _chapter_action_error(ValueError("Unknown chapter action."))
    chapter_action = _parse_chapter_action_api_path(path)
    if chapter_action is not None:
        chapter_id, action = chapter_action
        return _chapter_action_json(db_path, chapter_id, action, body)
    return api_error(HTTPStatus.NOT_FOUND, "not_found", "API route not found.")


def dispatch_api_post_stream(
    path: str,
    body: dict[str, Any],
    db_path: Path,
) -> ApiStreamResponse | ApiResponse | None:
    if path == "/api/open-book/stream":
        return ApiStreamResponse(stream_create_open_book_blueprint(db_path, body))
    volume_outline_action = _parse_book_volume_outline_action_api_path(path)
    if volume_outline_action is not None:
        book_id, action = volume_outline_action
        if action == "generate-stream":
            return ApiStreamResponse(stream_generate_volume_outline(db_path, book_id))
        if action == "revise-stream":
            return ApiStreamResponse(stream_revise_volume_outline(db_path, book_id, body))
    blueprint_action = _parse_blueprint_action_api_path(path)
    if blueprint_action is not None:
        blueprint_id, action = blueprint_action
        if action == "retry-stream":
            return ApiStreamResponse(stream_retry_blueprint(db_path, blueprint_id))
        if action == "revise-stream":
            return ApiStreamResponse(stream_revise_blueprint(db_path, blueprint_id, body))
    book_chapter_action = _parse_book_chapter_action_api_path(path)
    if book_chapter_action is not None:
        book_id, action = book_chapter_action
        if action == "run-batch-stream":
            return ApiStreamResponse(stream_run_chapter_batch(db_path, book_id, body))
    chapter_action = _parse_chapter_action_api_path(path)
    if chapter_action is not None:
        chapter_id, action = chapter_action
        if action == "run-stream":
            return ApiStreamResponse(stream_run_chapter(db_path, chapter_id))
        if action == "repair-stream":
            return ApiStreamResponse(stream_repair_chapter(db_path, chapter_id, body))
    canon_proposal_action = _parse_book_canon_proposal_action_api_path(path)
    if canon_proposal_action is None:
        return None
    book_id, action = canon_proposal_action
    if action != "revise-stream":
        return None
    return _revise_canon_proposal_stream_response(db_path, book_id, body)


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


def _parse_book_quality_api_path(path: str) -> int | None:
    parts = path.strip("/").split("/")
    if len(parts) != 4 or parts[:2] != ["api", "books"] or parts[3] != "quality":
        return None
    try:
        return int(parts[2])
    except ValueError:
        return 0


def _parse_book_export_api_path(path: str) -> tuple[int, str] | None:
    parts = path.strip("/").split("/")
    if len(parts) != 4 or parts[:2] != ["api", "books"]:
        return None
    if parts[3] == "export.md":
        export_format = "markdown"
    elif parts[3] == "export.json":
        export_format = "json"
    else:
        return None
    try:
        book_id = int(parts[2])
    except ValueError:
        book_id = 0
    return book_id, export_format


def _parse_book_word_targets_api_path(path: str) -> int | None:
    parts = path.strip("/").split("/")
    if len(parts) != 4 or parts[:2] != ["api", "books"] or parts[3] != "word-targets":
        return None
    try:
        return int(parts[2])
    except ValueError:
        return 0


def _parse_book_delete_api_path(path: str) -> int | None:
    parts = path.strip("/").split("/")
    if len(parts) != 4 or parts[:2] != ["api", "books"] or parts[3] != "delete":
        return None
    try:
        return int(parts[2])
    except ValueError:
        return 0


def _parse_chapter_api_path(path: str) -> int | None:
    parts = path.strip("/").split("/")
    if len(parts) != 3 or parts[:2] != ["api", "chapters"]:
        return None
    try:
        return int(parts[2])
    except ValueError:
        return 0


def _parse_chapter_export_api_path(path: str) -> int | None:
    parts = path.strip("/").split("/")
    if len(parts) != 4 or parts[:2] != ["api", "chapters"] or parts[3] != "export.txt":
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


def _parse_book_chapter_action_api_path(path: str) -> tuple[int, str] | None:
    parts = path.strip("/").split("/")
    if len(parts) != 5 or parts[:2] != ["api", "books"] or parts[3] != "chapters":
        return None
    try:
        book_id = int(parts[2])
    except ValueError:
        book_id = 0
    return book_id, parts[4]


def _parse_book_volume_outline_action_api_path(path: str) -> tuple[int, str] | None:
    parts = path.strip("/").split("/")
    if len(parts) != 5 or parts[:2] != ["api", "books"] or parts[3] != "volume-outline":
        return None
    try:
        book_id = int(parts[2])
    except ValueError:
        book_id = 0
    return book_id, parts[4]


def _parse_book_quality_action_api_path(path: str) -> tuple[int, str] | None:
    parts = path.strip("/").split("/")
    if parts[:2] != ["api", "books"]:
        return None
    if len(parts) == 4:
        action = parts[3]
    elif len(parts) == 5 and parts[3] == "quality":
        action = {
            "style-assets": "style-assets",
            "deconstruct-reference": "deconstruction-studies",
            "snapshots": "quality-snapshots",
        }.get(parts[4], "")
    else:
        return None
    if action not in {"style-assets", "deconstruction-studies", "quality-snapshots"}:
        return None
    try:
        book_id = int(parts[2])
    except ValueError:
        book_id = 0
    return book_id, action


def _parse_chapter_action_api_path(path: str) -> tuple[int, str] | None:
    parts = path.strip("/").split("/")
    if len(parts) != 4 or parts[:2] != ["api", "chapters"]:
        return None
    try:
        chapter_id = int(parts[2])
    except ValueError:
        chapter_id = 0
    return chapter_id, parts[3]


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
        return _canon_proposal_action_error(
            ValueError("Canon proposal lock value must be boolean.")
        )
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
    if _body_bool(body, "autoComplete", "auto_complete") is True:
        form_response = _canon_proposal_auto_complete_form(db_path, book_id)
        if isinstance(form_response, ApiResponse):
            return form_response
        form = form_response
    else:
        form = {
            "book_id": str(book_id),
            "target_section": str(body.get("targetSection") or body.get("target_section") or ""),
            "instruction": str(body.get("instruction") or ""),
        }
    response = handle_create_canon_proposal_revision(
        form,
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


def _revise_canon_proposal_stream_response(
    db_path: Path,
    book_id: int,
    body: dict[str, Any],
) -> ApiStreamResponse | ApiResponse:
    if _body_bool(body, "autoComplete", "auto_complete") is True:
        form_response = _canon_proposal_auto_complete_form(db_path, book_id)
        if isinstance(form_response, ApiResponse):
            return form_response
        form = form_response
    else:
        form = {
            "book_id": str(book_id),
            "target_section": str(body.get("targetSection") or body.get("target_section") or ""),
            "instruction": str(body.get("instruction") or ""),
        }
    return ApiStreamResponse(stream_revise_and_apply_canon_proposal(form, db_path))


def _canon_proposal_auto_complete_form(
    db_path: Path,
    book_id: int,
) -> dict[str, str] | ApiResponse:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = get_book(session, book_id)
        if book is None:
            return api_error(HTTPStatus.NOT_FOUND, "book_not_found", "Book not found.")
        canon = get_latest_canon(session, book_id)
        if canon is None:
            return _canon_proposal_action_error(ValueError("Trusted state proposal is required."))
        target_section = canon_proposal_completion_target(
            canon.content, section_locks_for_book(book)
        )
    if target_section is None:
        return _canon_proposal_action_error(ValueError("No editable missing canon section."))
    return {
        "book_id": str(book_id),
        "target_section": target_section,
        "instruction": CANON_PROPOSAL_COMPLETION_INSTRUCTION,
    }


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


def _import_book_json(db_path: Path, body: dict[str, Any]) -> ApiResponse:
    raw_json = _optional_text(body, "projectJson", "project_json") or ""
    try:
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            book = import_book_json(session, raw_json)
            payload_book = book_payload(book)
    except ValueError as error:
        return api_error(HTTPStatus.BAD_REQUEST, "import_failed", str(error))
    book_id = book.id or 0
    payload = {"book": payload_book, "redirectTo": f"/books/{book_id}"}
    return ApiResponse(HTTPStatus.OK, payload)


def _delete_book_json(db_path: Path, book_id: int) -> ApiResponse:
    try:
        delete_book(db_path, book_id)
    except DeleteBookError as error:
        return api_error(HTTPStatus.BAD_REQUEST, "book_delete_failed", str(error))
    return ApiResponse(HTTPStatus.OK, {"redirectTo": "/"})


def _update_book_word_targets_json(
    db_path: Path,
    book_id: int,
    body: dict[str, Any],
) -> ApiResponse:
    try:
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            update_book_word_targets(
                session,
                book_id,
                target_word_count=body.get("targetWordCount", body.get("target_word_count")),
                chapter_word_count=body.get("chapterWordCount", body.get("chapter_word_count")),
                update_existing_chapters=_body_bool(
                    body,
                    "updateExistingChapters",
                    "update_existing_chapters",
                )
                is True,
            )
    except ValueError as error:
        return api_error(HTTPStatus.BAD_REQUEST, "word_target_failed", str(error))
    payload = book_detail_payload(db_path, book_id)
    if payload is None:
        return api_error(HTTPStatus.NOT_FOUND, "book_not_found", "Book not found.")
    return ApiResponse(HTTPStatus.OK, payload)


def _quality_action_json(
    db_path: Path,
    book_id: int,
    action: str,
    body: dict[str, Any],
) -> ApiResponse:
    if action == "style-assets":
        return _create_style_asset_json(db_path, book_id, body)
    if action == "deconstruction-studies":
        return _create_deconstruction_study_json(db_path, book_id, body)
    if action == "quality-snapshots":
        return _create_quality_snapshot_json(db_path, book_id)
    return api_error(HTTPStatus.NOT_FOUND, "not_found", "API route not found.")


def _create_style_asset_json(db_path: Path, book_id: int, body: dict[str, Any]) -> ApiResponse:
    try:
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            asset = create_style_asset(
                session,
                book_id,
                _optional_text(body, "name") or "",
                _optional_text(body, "referenceText", "reference_text") or "",
                _optional_text(body, "sourceTitle", "source_title"),
            )
    except ValueError as error:
        return _quality_action_error(error)
    return ApiResponse(HTTPStatus.OK, {"styleAsset": style_asset_payload(asset)})


def _create_deconstruction_study_json(
    db_path: Path,
    book_id: int,
    body: dict[str, Any],
) -> ApiResponse:
    try:
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            study = deconstruct_reference_text(
                session,
                book_id,
                _optional_text(body, "sourceTitle", "source_title") or "",
                _optional_text(body, "referenceText", "reference_text") or "",
            )
    except ValueError as error:
        return _quality_action_error(error)
    return ApiResponse(HTTPStatus.OK, {"deconstructionStudy": deconstruction_study_payload(study)})


def _create_quality_snapshot_json(db_path: Path, book_id: int) -> ApiResponse:
    try:
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            generate_quality_snapshot(session, book_id)
    except ValueError as error:
        return _quality_action_error(error)
    payload = quality_payload(db_path, book_id)
    if payload is None:
        return api_error(HTTPStatus.NOT_FOUND, "book_not_found", "Book not found.")
    return ApiResponse(HTTPStatus.OK, payload)


def _quality_action_error(error: ValueError) -> ApiResponse:
    return api_error(HTTPStatus.BAD_REQUEST, "quality_action_failed", str(error))


def _export_book_json(db_path: Path, book_id: int, export_format: str) -> ApiResponse:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = get_book(session, book_id)
        if book is None:
            return api_error(HTTPStatus.NOT_FOUND, "book_not_found", "Book not found.")
        chapters = list_chapters_for_book(session, book_id)
        canon = get_latest_canon(session, book_id)
        if export_format == "markdown":
            return ApiResponse(
                HTTPStatus.OK,
                export_book_markdown(book, chapters),
                "text/markdown; charset=utf-8",
            )
        if export_format == "json":
            return ApiResponse(HTTPStatus.OK, json.loads(export_book_json(book, canon, chapters)))
    return api_error(HTTPStatus.NOT_FOUND, "not_found", "API route not found.")


def _chapter_action_json(
    db_path: Path,
    chapter_id: int,
    action: str,
    body: dict[str, Any],
) -> ApiResponse:
    if action == "run":
        return _run_chapter_json(db_path, chapter_id)
    if action == "request-revision":
        return _request_chapter_revision_json(db_path, chapter_id, body)
    if action == "repair":
        return _repair_chapter_json(db_path, chapter_id, body)
    if action == "edit":
        return _edit_chapter_json(db_path, chapter_id, body)
    if action == "approve":
        return _approve_chapter_json(db_path, chapter_id, body)
    return _chapter_action_error(ValueError("Unknown chapter action."))


def _run_chapter_json(db_path: Path, chapter_id: int) -> ApiResponse:
    try:
        queued_chapter_id = queue_chapter_run(
            db_path,
            chapter_id,
            _load_provider_config(db_path),
        )
    except ValueError as error:
        return _chapter_action_error(error)
    return _chapter_payload_response(db_path, queued_chapter_id, HTTPStatus.ACCEPTED)


def _run_chapter_batch_json(db_path: Path, book_id: int, body: dict[str, Any]) -> ApiResponse:
    try:
        chapter_ids = parse_chapter_batch_ids(body.get("chapterIds"))
        queued_chapter_id = queue_chapter_batch_run(
            db_path,
            book_id,
            chapter_ids,
            _load_provider_config(db_path),
        )
    except ValueError as error:
        return _chapter_action_error(error)
    return _chapter_payload_response(db_path, queued_chapter_id, HTTPStatus.ACCEPTED)


def _request_chapter_revision_json(
    db_path: Path,
    chapter_id: int,
    body: dict[str, Any],
) -> ApiResponse:
    try:
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            chapter = return_chapter_for_revision(
                session,
                chapter_id,
                _optional_text(body, "reviewerNote", "reviewer_note"),
            )
    except ValueError as error:
        return _chapter_action_error(error)
    return _chapter_payload_response(db_path, chapter.id or chapter_id)


def _repair_chapter_json(db_path: Path, chapter_id: int, body: dict[str, Any]) -> ApiResponse:
    try:
        queued_chapter_id = queue_chapter_repair(
            db_path,
            chapter_id,
            _load_provider_config(db_path),
            reviewer_note=_optional_text(body, "reviewerNote", "reviewer_note"),
        )
    except ValueError as error:
        return _chapter_action_error(error)
    return _chapter_payload_response(db_path, queued_chapter_id, HTTPStatus.ACCEPTED)


def _edit_chapter_json(db_path: Path, chapter_id: int, body: dict[str, Any]) -> ApiResponse:
    text = _optional_text(body, "revisedText", "manualText", "manual_text") or ""
    try:
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            chapter = apply_manual_chapter_edit(
                session,
                chapter_id,
                text,
                _optional_text(body, "reviewerNote", "reviewer_note"),
            )
    except ValueError as error:
        return _chapter_action_error(error)
    return _chapter_payload_response(db_path, chapter.id or chapter_id)


def _approve_chapter_json(db_path: Path, chapter_id: int, body: dict[str, Any]) -> ApiResponse:
    try:
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            chapter = approve_chapter(
                session,
                chapter_id,
                _optional_text(body, "reviewerNote", "reviewer_note"),
                allow_major_changes=_body_bool(body, "allowMajorChanges", "allow_major_changes")
                is True,
            )
    except ValueError as error:
        return _chapter_action_error(error)
    return _chapter_payload_response(db_path, chapter.id or chapter_id)


def _export_chapter_text_json(db_path: Path, chapter_id: int) -> ApiResponse:
    try:
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            chapter = get_chapter(session, chapter_id)
            if chapter is None:
                return api_error(HTTPStatus.NOT_FOUND, "chapter_not_found", "Chapter not found.")
            text = export_chapter_text(chapter)
    except ValueError as error:
        return _chapter_action_error(error)
    return ApiResponse(HTTPStatus.OK, text, "text/plain; charset=utf-8")


def _chapter_payload_response(
    db_path: Path,
    chapter_id: int,
    status: HTTPStatus = HTTPStatus.OK,
) -> ApiResponse:
    payload = chapter_review_payload(db_path, chapter_id)
    if payload is None:
        return api_error(HTTPStatus.NOT_FOUND, "chapter_not_found", "Chapter not found.")
    payload["chapterId"] = chapter_id
    payload["redirectTo"] = f"/chapters/{chapter_id}"
    return ApiResponse(status, payload)


def _chapter_action_error(error: ValueError) -> ApiResponse:
    return api_error(
        HTTPStatus.BAD_REQUEST,
        "chapter_action_failed",
        str(error),
    )


def _load_provider_config(db_path: Path):
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        return get_provider_config(session)


def _optional_text(body: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = body.get(key)
        if value is None:
            continue
        text = str(value).strip()
        return text or None
    return None


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
