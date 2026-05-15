from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, quote, urlparse

from sqlmodel import Session, select

from mynovel.api_errors import ApiResponse
from mynovel.api_open_book import (
    BlueprintAcceptanceInProgressError,
    accept_blueprint_form_safely,
    create_open_book_blueprint_json,
    retry_blueprint_json,
    revise_blueprint_json,
)
from mynovel.api_routes import dispatch_api_get, dispatch_api_post, read_api_json_body
from mynovel.book_abandonment import AbandonBookError, abandon_draft_book_from_form
from mynovel.blueprint_acceptance import (
    BlueprintNotFoundError,
    BlueprintNotReadyError,
    BlueprintTitleSelectionError,
    lock_canon_from_form,
)
from mynovel import canon_proposal_server as canon_server
from mynovel.chapter_server import (
    chapter_model_client_from_provider_config,
    queue_chapter_batch_run,
    queue_chapter_repair,
    queue_chapter_run,
)
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import Book, OpenBookBlueprint, ProviderConfig
from mynovel.domain.repositories import (
    get_book,
    get_chapter,
    get_latest_canon,
    get_open_book_blueprint,
    get_provider_config,
    list_chapters_for_book,
    list_open_book_blueprints,
    list_run_traces_for_book,
    list_volume_plans_for_book,
)
from mynovel.frontend_assets import frontend_dist_path
from mynovel.i18n import t
from mynovel.path_display import display_path
from mynovel.import_views import render_import_project_page
from mynovel.legacy_cleanup import remove_legacy_placeholder_data
from mynovel.product_views import (
    render_book_workspace,
    render_blueprint_page,
    render_chapter_review,
    render_home,  # noqa: F401 - kept for import compatibility during SPA migration.
    render_model_setup_page,  # noqa: F401 - kept for import compatibility during SPA migration.
    render_new_book_page,  # noqa: F401 - kept for import compatibility during SPA migration.
    render_trusted_state_page,
)
from mynovel.provider_config_server import handle_provider_config_post
from mynovel.quality_views import render_quality_center
from mynovel.review_navigation import review_destination as _review_destination  # noqa: F401
from mynovel.static_server import StaticResponse, resolve_spa_response
from mynovel.update_server import handle_check_update, handle_stage_update
from mynovel.update_views import render_update_page  # noqa: F401
from mynovel.word_target_server import save_book_word_targets_from_form
from mynovel.word_targets import book_idea_from_form as _book_idea_from_form  # noqa: F401
from mynovel.workflows.quality_enhancement import (
    create_style_asset,
    deconstruct_reference_text,
    generate_quality_snapshot,
    recommend_cost_strategy,
)
from mynovel.workflows.chapter_pipeline import (
    approve_chapter,
    apply_manual_chapter_edit,
    export_chapter_text,
    return_chapter_for_revision,
)
from mynovel.workflows.book_export import export_book_json, export_book_markdown
from mynovel.workflows.book_import import import_book_json

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_DB_PATH = Path(".mynovel/dev.sqlite")


@dataclass(frozen=True)
class DevServerState:
    db_path: Path


def build_health_payload(db_path: Path) -> dict[str, str]:
    return {"status": "ok", "database": display_path(db_path)}


def run_server(host: str, port: int, db_path: Path) -> None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    remove_legacy_placeholder_data(engine)

    state = DevServerState(db_path=db_path)
    server = ThreadingHTTPServer((host, port), _make_handler(state))
    actual_host = host
    actual_port = server.server_port
    print(f"MyNovel dev server running at http://{actual_host}:{actual_port}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped MyNovel dev server.")
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the local MyNovel product server.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args(argv)

    run_server(args.host, args.port, args.db)


def _make_handler(state: DevServerState) -> type[BaseHTTPRequestHandler]:
    class DevRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            route = _classify_get_path(parsed.path)
            if route == "health":
                self._send_json(build_health_payload(state.db_path))
                return
            if route == "api":
                self._send_api_response(
                    dispatch_api_get(parsed.path, parsed.query, state.db_path)
                )
                return
            if route == "book_export":
                book_id, export_format = _parse_book_export(parsed.path)
                self._send_book_export(state.db_path, book_id, export_format)
                return
            if route == "chapter_export":
                self._send_chapter_export(state.db_path, _parse_chapter_export_id(parsed.path))
                return
            self._send_static_response(resolve_spa_response(parsed.path, frontend_dist_path()))

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if _is_api_path(parsed.path):
                body, error = self._read_json()
                if error is not None:
                    self._send_api_response(error)
                    return
                self._send_api_response(
                    dispatch_api_post(parsed.path, body, state.db_path)
                )
                return
            if canon_server.is_canon_proposal_post_path(parsed.path):
                canon_response = canon_server.dispatch_canon_proposal_post(
                    parsed.path,
                    self._read_form(),
                    state.db_path,
                )
                if canon_response.redirect_to:
                    self._redirect(canon_response.redirect_to)
                else:
                    self._send_html(canon_response.body, status=canon_response.status)
                return
            if parsed.path == "/init":
                create_db_and_tables(create_engine_for_path(state.db_path))
                self._redirect_message(t("provider.saved"))
                return
            if parsed.path == "/provider-config":
                provider_response = handle_provider_config_post(state.db_path, self._read_form())
                if provider_response.redirect_to:
                    self._redirect(provider_response.redirect_to)
                else:
                    self._send_html(provider_response.body, status=provider_response.status)
                return
            if parsed.path == "/books/import":
                self._import_book(state.db_path)
                return
            if parsed.path == "/open-book":
                self._create_blueprint(state.db_path)
                return
            if parsed.path == "/revise-blueprint":
                self._revise_blueprint(state.db_path)
                return
            if parsed.path == "/retry-blueprint":
                self._retry_blueprint(state.db_path)
                return
            if parsed.path == "/accept-blueprint":
                self._accept_blueprint(state.db_path)
                return
            if parsed.path == "/lock-canon":
                return self._lock_canon(state.db_path)
            if parsed.path == "/abandon-book":
                return self._abandon_book(state.db_path)
            if parsed.path == "/run-chapter":
                self._run_chapter(state.db_path)
                return
            if parsed.path == "/run-chapter-batch":
                self._run_chapter_batch(state.db_path)
                return
            if parsed.path == "/book-word-targets":
                try:
                    book_id = save_book_word_targets_from_form(self._read_form(), state.db_path)
                except ValueError:
                    self.send_error(HTTPStatus.BAD_REQUEST)
                    return
                self._redirect(f"/book/{book_id}")
                return
            if parsed.path == "/request-revision":
                self._request_revision(state.db_path)
                return
            if parsed.path == "/repair-chapter":
                self._repair_chapter(state.db_path)
                return
            if parsed.path == "/edit-chapter-text":
                self._edit_chapter_text(state.db_path)
                return
            if parsed.path == "/approve-chapter":
                self._approve_chapter(state.db_path)
                return
            if parsed.path == "/style-asset":
                self._create_style_asset(state.db_path)
                return
            if parsed.path == "/deconstruct-reference":
                self._deconstruct_reference(state.db_path)
                return
            if parsed.path == "/quality-snapshot":
                self._create_quality_snapshot(state.db_path)
                return
            if parsed.path == "/check-update":
                update_response = handle_check_update(self._read_form())
                self._send_html(update_response.body, status=update_response.status)
                return
            if parsed.path == "/stage-update":
                stage_response = handle_stage_update(self._read_form(), state.db_path)
                self._send_html(stage_response.body, status=stage_response.status)
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: Any) -> None:
            print(f"{self.address_string()} - {format % args}")

        def _send_book_page(self, db_path: Path, book_id: int) -> None:
            book = _load_book(db_path, book_id)
            if book is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._send_html(
                render_book_workspace(
                    book,
                    _load_chapters_for_book(db_path, book_id),
                    _load_latest_canon(db_path, book_id),
                    _load_run_traces_for_book(db_path, book_id),
                    _load_volume_plans_for_book(db_path, book_id),
                )
            )

        def _send_trusted_state_page(
            self, db_path: Path, book_id: int, revision_id: int | None = None
        ) -> None:
            book = _load_book(db_path, book_id)
            if book is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            revision = canon_server.load_pending_canon_proposal_revision_for_book(
                db_path, book_id, revision_id
            )
            self._send_html(
                render_trusted_state_page(
                    book,
                    _load_latest_canon(db_path, book_id),
                    _load_chapters_for_book(db_path, book_id),
                    proposal_revision=revision,
                )
            )

        def _send_quality_page(self, db_path: Path, book_id: int) -> None:
            book = _load_book(db_path, book_id)
            if book is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._send_html(_render_quality_page_from_db(db_path, book))

        def _send_book_export(self, db_path: Path, book_id: int, export_format: str) -> None:
            book = _load_book(db_path, book_id)
            if book is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            chapters = _load_chapters_for_book(db_path, book_id)
            canon = _load_latest_canon(db_path, book_id)
            if export_format == "markdown":
                payload = export_book_markdown(book, chapters).encode("utf-8")
                content_type = "text/markdown; charset=utf-8"
            elif export_format == "json":
                payload = export_book_json(book, canon, chapters).encode("utf-8")
                content_type = "application/json; charset=utf-8"
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_chapter_page(self, db_path: Path, chapter_id: int) -> None:
            chapter = _load_chapter(db_path, chapter_id)
            if chapter is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            book = _load_book(db_path, chapter.book_id)
            if book is None or book.id is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._send_html(
                render_chapter_review(
                    book,
                    _load_chapters_for_book(db_path, book.id),
                    chapter,
                    _load_latest_canon(db_path, book.id),
                    traces=_load_run_traces_for_book(db_path, book.id),
                )
            )

        def _send_chapter_export(self, db_path: Path, chapter_id: int) -> None:
            chapter = _load_chapter(db_path, chapter_id)
            if chapter is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                text = export_chapter_text(chapter)
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            payload = text.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_blueprint_page(self, db_path: Path, blueprint_id: int) -> None:
            blueprint = _load_open_book_blueprint(db_path, blueprint_id)
            if blueprint is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._send_html(
                render_blueprint_page(db_path, _load_provider_config(db_path), blueprint)
            )

        def _import_book(self, db_path: Path) -> None:
            engine = create_engine_for_path(db_path)
            create_db_and_tables(engine)
            with Session(engine) as session:
                try:
                    book = import_book_json(session, self._read_form().get("project_json", ""))
                except ValueError as error:
                    self._send_html(render_import_project_page(str(error)), HTTPStatus.BAD_REQUEST)
                    return
            self._redirect(f"/book/{book.id or 0}")

        def _create_blueprint(self, db_path: Path) -> None:
            self._redirect_api_response(create_open_book_blueprint_json(db_path, self._read_form()))

        def _revise_blueprint(self, db_path: Path) -> None:
            form = self._read_form()
            try:
                blueprint_id = int(form.get("blueprint_id", "0") or "0")
            except ValueError:
                blueprint_id = 0
            self._redirect_api_response(revise_blueprint_json(db_path, blueprint_id, form))

        def _retry_blueprint(self, db_path: Path) -> None:
            form = self._read_form()
            try:
                blueprint_id = int(form.get("blueprint_id", "0") or "0")
            except ValueError:
                blueprint_id = 0
            self._redirect_api_response(retry_blueprint_json(db_path, blueprint_id))

        def _accept_blueprint(self, db_path: Path) -> None:
            form = self._read_form()
            provider_config = _load_provider_config(db_path)
            try:
                book = accept_blueprint_form_safely(db_path, form)
            except (BlueprintNotFoundError, BlueprintNotReadyError, BlueprintAcceptanceInProgressError) as error:
                status = (
                    HTTPStatus.NOT_FOUND
                    if isinstance(error, BlueprintNotFoundError)
                    else HTTPStatus.CONFLICT
                    if isinstance(error, BlueprintAcceptanceInProgressError)
                    else HTTPStatus.BAD_REQUEST
                )
                self.send_error(status)
                return
            except BlueprintTitleSelectionError as error:
                self._send_html(
                    render_blueprint_page(
                        db_path,
                        provider_config,
                        error.blueprint,
                        t("blueprint.title_required"),
                    ),
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            self._redirect(f"/books/{book.id or 0}")

        def _lock_canon(self, db_path: Path) -> None:
            try:
                book = lock_canon_from_form(db_path, self._read_form())
            except ValueError:
                return self.send_error(HTTPStatus.BAD_REQUEST)
            return self._redirect(f"/book/{book.id or 0}")

        def _abandon_book(self, db_path: Path) -> None:
            try:
                abandon_draft_book_from_form(db_path, self._read_form())
            except AbandonBookError:
                return self.send_error(HTTPStatus.BAD_REQUEST)
            return self._redirect("/books/new")

        def _run_chapter(self, db_path: Path) -> None:
            chapter_id = int(self._read_form().get("chapter_id", "0"))
            provider_config = _load_provider_config(db_path)
            try:
                queued_chapter_id = queue_chapter_run(db_path, chapter_id, provider_config)
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            self._redirect(f"/chapter/{queued_chapter_id}")

        def _run_chapter_batch(self, db_path: Path) -> None:
            form = self._read_form()
            book_id = int(form.get("book_id", "0"))
            limit = _parse_batch_limit(form)
            provider_config = _load_provider_config(db_path)
            try:
                queued_chapter_id = queue_chapter_batch_run(
                    db_path, book_id, limit, provider_config
                )
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            self._redirect(f"/chapter/{queued_chapter_id}")

        def _request_revision(self, db_path: Path) -> None:
            form = self._read_form()
            chapter_id = int(form.get("chapter_id", "0"))
            engine = create_engine_for_path(db_path)
            create_db_and_tables(engine)
            with Session(engine) as session:
                try:
                    chapter = return_chapter_for_revision(
                        session,
                        chapter_id,
                        form.get("reviewer_note") or None,
                    )
                except ValueError:
                    self.send_error(HTTPStatus.BAD_REQUEST)
                    return
            self._redirect(f"/chapter/{chapter.id}")

        def _repair_chapter(self, db_path: Path) -> None:
            form = self._read_form()
            chapter_id = int(form.get("chapter_id", "0"))
            provider_config = _load_provider_config(db_path)
            try:
                queued_chapter_id = queue_chapter_repair(
                    db_path,
                    chapter_id,
                    provider_config,
                    reviewer_note=form.get("reviewer_note") or None,
                )
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            self._redirect(f"/chapter/{queued_chapter_id}")

        def _edit_chapter_text(self, db_path: Path) -> None:
            form = self._read_form()
            chapter_id = int(form.get("chapter_id", "0"))
            engine = create_engine_for_path(db_path)
            create_db_and_tables(engine)
            with Session(engine) as session:
                try:
                    chapter = apply_manual_chapter_edit(
                        session,
                        chapter_id,
                        form.get("manual_text", ""),
                        form.get("reviewer_note") or None,
                    )
                except ValueError:
                    self.send_error(HTTPStatus.BAD_REQUEST)
                    return
            self._redirect(f"/chapter/{chapter.id}")

        def _approve_chapter(self, db_path: Path) -> None:
            form = self._read_form()
            chapter_id = int(form.get("chapter_id", "0"))
            engine = create_engine_for_path(db_path)
            create_db_and_tables(engine)
            with Session(engine) as session:
                try:
                    chapter = approve_chapter(
                        session,
                        chapter_id,
                        form.get("reviewer_note") or None,
                        allow_major_changes=form.get("allow_major_changes") == "1",
                    )
                except ValueError:
                    self.send_error(HTTPStatus.BAD_REQUEST)
                    return
            self._redirect(f"/chapter/{chapter.id}")

        def _create_style_asset(self, db_path: Path) -> None:
            form = self._read_form()
            book_id = int(form.get("book_id", "0"))
            engine = create_engine_for_path(db_path)
            create_db_and_tables(engine)
            with Session(engine) as session:
                try:
                    create_style_asset(
                        session,
                        book_id,
                        form.get("name", ""),
                        form.get("reference_text", ""),
                        form.get("source_title") or None,
                    )
                except ValueError:
                    self.send_error(HTTPStatus.BAD_REQUEST)
                    return
            self._redirect(f"/book/{book_id}/quality")

        def _deconstruct_reference(self, db_path: Path) -> None:
            form = self._read_form()
            book_id = int(form.get("book_id", "0"))
            engine = create_engine_for_path(db_path)
            create_db_and_tables(engine)
            with Session(engine) as session:
                try:
                    deconstruct_reference_text(
                        session,
                        book_id,
                        form.get("source_title", ""),
                        form.get("reference_text", ""),
                    )
                except ValueError:
                    self.send_error(HTTPStatus.BAD_REQUEST)
                    return
            self._redirect(f"/book/{book_id}/quality")

        def _create_quality_snapshot(self, db_path: Path) -> None:
            form = self._read_form()
            book_id = int(form.get("book_id", "0"))
            engine = create_engine_for_path(db_path)
            create_db_and_tables(engine)
            with Session(engine) as session:
                try:
                    generate_quality_snapshot(session, book_id)
                except ValueError:
                    self.send_error(HTTPStatus.BAD_REQUEST)
                    return
            self._redirect(f"/book/{book_id}/quality")

        def _read_form(self) -> dict[str, str]:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            return {key: values[-1].strip() for key, values in parse_qs(body).items()}

        def _read_json(self) -> tuple[dict[str, Any], ApiResponse | None]:
            return read_api_json_body(self.headers.get("Content-Length"), self.rfile.read)

        def _send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_json(self, body: dict[str, str]) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_api_response(self, response: ApiResponse) -> None:
            if response.content_type.startswith("application/json"):
                payload = json.dumps(response.body, ensure_ascii=False).encode("utf-8")
            elif isinstance(response.body, bytes):
                payload = response.body
            else:
                payload = str(response.body).encode("utf-8")
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _redirect_api_response(self, response: ApiResponse) -> None:
            if not isinstance(response.body, dict):
                self.send_error(response.status)
                return
            redirect_to = response.body.get("redirectTo")
            if response.status in {HTTPStatus.OK, HTTPStatus.ACCEPTED} and isinstance(
                redirect_to,
                str,
            ):
                self._redirect(redirect_to)
                return
            self.send_error(response.status)

        def _send_static_response(self, response: StaticResponse) -> None:
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)

        def _redirect(self, location: str) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", location)
            self.end_headers()

        def _redirect_message(self, message: str) -> None:
            self._redirect(f"/?message={quote(message)}")

    return DevRequestHandler


def _classify_get_path(path: str) -> str:
    if path == "/health":
        return "health"
    if _is_api_path(path):
        return "api"
    if _parse_book_export(path)[1]:
        return "book_export"
    if _parse_chapter_export_id(path):
        return "chapter_export"
    return "static"


def _is_api_path(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")


def _load_books(db_path: Path) -> list[Book]:
    return _read_db(
        db_path,
        lambda session: list(
            session.exec(select(Book).order_by(cast(Any, Book.created_at).desc()).limit(20))
        ),
    )


def _read_db(db_path: Path, reader):
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        return reader(session)


def _load_book(db_path: Path, book_id: int) -> Book | None:
    return _read_db(db_path, lambda session: get_book(session, book_id))


def _load_chapter(db_path: Path, chapter_id: int):
    return _read_db(db_path, lambda session: get_chapter(session, chapter_id))


def _load_chapters_for_book(db_path: Path, book_id: int):
    return _read_db(db_path, lambda session: list_chapters_for_book(session, book_id))


def _load_latest_canon(db_path: Path, book_id: int):
    return _read_db(db_path, lambda session: get_latest_canon(session, book_id))


def _load_run_traces_for_book(db_path: Path, book_id: int):
    return _read_db(db_path, lambda session: list_run_traces_for_book(session, book_id))


def _load_volume_plans_for_book(db_path: Path, book_id: int):
    return _read_db(db_path, lambda session: list_volume_plans_for_book(session, book_id))


def _load_provider_config(db_path: Path) -> ProviderConfig | None:
    return _read_db(db_path, get_provider_config)


def _load_open_book_blueprints(db_path: Path) -> list[OpenBookBlueprint]:
    return _read_db(db_path, list_open_book_blueprints)


def _load_open_book_blueprint(db_path: Path, blueprint_id: int) -> OpenBookBlueprint | None:
    return _read_db(db_path, lambda session: get_open_book_blueprint(session, blueprint_id))


def _render_quality_page_from_db(db_path: Path, book: Book) -> str:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        from mynovel.domain.repositories import (
            list_deconstruction_studies_for_book,
            list_quality_snapshots_for_book,
            list_style_assets_for_book,
        )

        book_id = book.id or 0
        snapshots = list_quality_snapshots_for_book(session, book_id)
        latest_snapshot = snapshots[-1] if snapshots else None
        strategy = recommend_cost_strategy(latest_snapshot) if latest_snapshot else None
        return render_quality_center(
            book,
            list_style_assets_for_book(session, book_id),
            list_deconstruction_studies_for_book(session, book_id),
            latest_snapshot,
            strategy,
            list_chapters_for_book(session, book_id),
        )


def _parse_numeric_id(path: str) -> int:
    _, _, raw_id = path.rpartition("/")
    try:
        return int(raw_id)
    except ValueError:
        return 0


def _parse_chapter_export_id(path: str) -> int:
    parts = path.strip("/").split("/")
    if len(parts) != 3 or parts[0] != "chapter" or parts[2] != "export":
        return 0
    try:
        return int(parts[1])
    except ValueError:
        return 0


def _parse_book_state_id(path: str) -> int:
    parts = path.strip("/").split("/")
    if len(parts) != 3 or parts[0] != "book" or parts[2] != "state":
        return 0
    try:
        return int(parts[1])
    except ValueError:
        return 0


def _parse_book_quality_id(path: str) -> int:
    parts = path.strip("/").split("/")
    if len(parts) != 3 or parts[0] != "book" or parts[2] != "quality":
        return 0
    try:
        return int(parts[1])
    except ValueError:
        return 0


def _parse_book_export(path: str) -> tuple[int, str]:
    parts = path.strip("/").split("/")
    if len(parts) != 3 or parts[0] != "book":
        return 0, ""
    if parts[2] == "export.md":
        export_format = "markdown"
    elif parts[2] == "export.json":
        export_format = "json"
    else:
        return 0, ""
    try:
        return int(parts[1]), export_format
    except ValueError:
        return 0, ""


def _parse_batch_limit(form: dict[str, str]) -> int:
    try:
        value = int(form.get("limit", "1"))
    except ValueError:
        return 1
    return min(10, max(1, value))


def _chapter_model_client_from_provider_config(provider_config: ProviderConfig | None):
    return chapter_model_client_from_provider_config(provider_config)


if __name__ == "__main__":
    main()
