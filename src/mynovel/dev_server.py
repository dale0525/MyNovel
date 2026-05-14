from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, cast
from urllib.parse import parse_qs, quote, urlparse

from sqlmodel import Session, select

from mynovel.book_abandonment import AbandonBookError, abandon_draft_book_from_form
from mynovel.blueprint_acceptance import (
    BlueprintNotFoundError,
    BlueprintNotReadyError,
    BlueprintTitleSelectionError,
    accept_blueprint_for_foundation_review,
    lock_canon_from_form,
)
from mynovel.blueprint_revision import create_revision_blueprint_job, revision_notes_from_form
from mynovel import canon_proposal_server as canon_server
from mynovel.chapter_server import (
    chapter_model_client_from_provider_config,
    queue_chapter_batch_run,
    queue_chapter_repair,
    queue_chapter_run,
)
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import Book, BlueprintStatus, OpenBookBlueprint, ProviderConfig, utc_now
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
    save_provider_config,
)
from mynovel.i18n import t
from mynovel.import_views import render_import_project_page
from mynovel.legacy_cleanup import remove_legacy_placeholder_data
from mynovel.llm.openai_compatible import ChatRequest, OpenAICompatibleClient
from mynovel.product_views import (
    is_provider_config_complete,
    render_book_workspace,
    render_blueprint_page,
    render_chapter_review,
    render_home,
    render_model_setup_page,
    render_new_book_page,
    render_trusted_state_page,
)
from mynovel.provider_config_forms import provider_config_from_form as _provider_config_from_form
from mynovel.quality_views import render_quality_center
from mynovel.review_navigation import review_destination as _review_destination
from mynovel.update_server import handle_check_update, handle_stage_update
from mynovel.update_views import render_update_page
from mynovel.word_target_server import save_book_word_targets_from_form
from mynovel.word_targets import book_idea_from_form as _book_idea_from_form
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
from mynovel.workflows.open_book_blueprint import (
    build_blueprint_messages,
    create_blueprint_job,
    extract_chat_content,
    parse_blueprint_json,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_DB_PATH = Path(".mynovel/dev.sqlite")


@dataclass(frozen=True)
class DevServerState:
    db_path: Path


def build_health_payload(db_path: Path) -> dict[str, str]:
    return {"status": "ok", "database": str(db_path)}


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
            if parsed.path == "/health":
                self._send_json(build_health_payload(state.db_path))
                return
            if parsed.path == "/books/new":
                self._send_html(render_new_book_page(_load_provider_config(state.db_path)))
                return
            if parsed.path == "/books/import":
                self._send_html(render_import_project_page())
                return
            if parsed.path == "/provider-config":
                self._send_html(
                    render_model_setup_page(state.db_path, _load_provider_config(state.db_path))
                )
                return
            if parsed.path == "/review":
                return self._redirect(_review_destination(state.db_path))
            if parsed.path.startswith("/book/") and parsed.path.endswith("/state"):
                raw_revision_id = parse_qs(parsed.query).get("revision_id", [""])[0]
                revision_id = int(raw_revision_id) if raw_revision_id.isdigit() else None
                self._send_trusted_state_page(state.db_path, _parse_book_state_id(parsed.path), revision_id)
                return
            if parsed.path.startswith("/book/") and parsed.path.endswith("/quality"):
                self._send_quality_page(state.db_path, _parse_book_quality_id(parsed.path))
                return
            if parsed.path.startswith("/book/") and (
                parsed.path.endswith("/export.md") or parsed.path.endswith("/export.json")
            ):
                book_id, export_format = _parse_book_export(parsed.path)
                self._send_book_export(state.db_path, book_id, export_format)
                return
            if parsed.path.startswith("/book/"):
                self._send_book_page(state.db_path, _parse_numeric_id(parsed.path))
                return
            if parsed.path.startswith("/chapter/") and parsed.path.endswith("/export"):
                self._send_chapter_export(state.db_path, _parse_chapter_export_id(parsed.path))
                return
            if parsed.path.startswith("/chapter/"):
                self._send_chapter_page(state.db_path, _parse_numeric_id(parsed.path))
                return
            if parsed.path.startswith("/blueprint/"):
                self._send_blueprint_page(state.db_path, _parse_numeric_id(parsed.path))
                return
            if parsed.path == "/updates":
                self._send_html(render_update_page())
                return
            if parsed.path != "/":
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            message = parse_qs(parsed.query).get("message", [None])[0]
            self._send_html(
                render_home(
                    state.db_path,
                    _load_books(state.db_path),
                    _load_provider_config(state.db_path),
                    _load_open_book_blueprints(state.db_path),
                    message,
                )
            )

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
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
                self._save_provider_config(state.db_path)
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

        def _send_trusted_state_page(self, db_path: Path, book_id: int, revision_id: int | None = None) -> None:
            book = _load_book(db_path, book_id)
            if book is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            revision = canon_server.load_pending_canon_proposal_revision_for_book(db_path, book_id, revision_id)
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

        def _save_provider_config(self, db_path: Path) -> None:
            engine = create_engine_for_path(db_path)
            create_db_and_tables(engine)
            with Session(engine) as session:
                save_provider_config(session, _provider_config_from_form(self._read_form()))
            self._redirect_message(t("provider.saved"))

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
            form = self._read_form()
            idea = _book_idea_from_form(form)
            provider_config = _load_provider_config(db_path)
            if not is_provider_config_complete(provider_config):
                self._send_html(
                    render_home(
                        db_path,
                        _load_books(db_path),
                        provider_config,
                        _load_open_book_blueprints(db_path),
                        t("status.not_configured"),
                    ),
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            if not idea:
                self._send_html(render_new_book_page(provider_config, t("book.idea_required")))
                return

            assert provider_config is not None
            engine = create_engine_for_path(db_path)
            create_db_and_tables(engine)
            with Session(engine) as session:
                blueprint = create_blueprint_job(
                    session,
                    idea=idea,
                    version=1,
                    instruction=None,
                    parent_id=None,
                )
                blueprint_id = blueprint.id
            if blueprint_id is None:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            _start_blueprint_job(db_path, blueprint_id, provider_config)
            self._redirect(f"/blueprint/{blueprint_id}")

        def _revise_blueprint(self, db_path: Path) -> None:
            form = self._read_form()
            revision_notes = revision_notes_from_form(form)
            provider_config = _load_provider_config(db_path)
            blueprints = _load_open_book_blueprints(db_path)
            if not provider_config or not is_provider_config_complete(provider_config):
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            if not blueprints:
                self._redirect("/")
                return
            if not revision_notes:
                self._send_html(
                    render_home(
                        db_path,
                        _load_books(db_path),
                        provider_config,
                        blueprints,
                        t("blueprint.revision_required"),
                    ),
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            engine = create_engine_for_path(db_path)
            create_db_and_tables(engine)
            with Session(engine) as session:
                try:
                    blueprint = create_revision_blueprint_job(
                        session,
                        form,
                        blueprints,
                        revision_notes,
                    )
                except ValueError:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                blueprint_id = blueprint.id
            if blueprint_id is None:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            _start_blueprint_job(db_path, blueprint_id, provider_config)
            self._redirect(f"/blueprint/{blueprint_id}")

        def _retry_blueprint(self, db_path: Path) -> None:
            form = self._read_form()
            blueprint_id = int(form.get("blueprint_id", "0"))
            provider_config = _load_provider_config(db_path)
            if not provider_config or not is_provider_config_complete(provider_config):
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            engine = create_engine_for_path(db_path)
            create_db_and_tables(engine)
            with Session(engine) as session:
                blueprint = get_open_book_blueprint(session, blueprint_id)
                if blueprint is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                _reset_blueprint_for_retry(session, blueprint)
            _start_blueprint_job(db_path, blueprint_id, provider_config)
            self._redirect(f"/blueprint/{blueprint_id}")

        def _accept_blueprint(self, db_path: Path) -> None:
            form = self._read_form()
            provider_config = _load_provider_config(db_path)
            try:
                book = accept_blueprint_for_foundation_review(db_path, form)
            except (BlueprintNotFoundError, BlueprintNotReadyError) as error:
                status = HTTPStatus.NOT_FOUND if isinstance(error, BlueprintNotFoundError) else HTTPStatus.BAD_REQUEST
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
            self._redirect(f"/book/{book.id or 0}/state")

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
                queued_chapter_id = queue_chapter_batch_run(db_path, book_id, limit, provider_config)
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

        def _redirect(self, location: str) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", location)
            self.end_headers()

        def _redirect_message(self, message: str) -> None:
            self._redirect(f"/?message={quote(message)}")

    return DevRequestHandler


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


def _start_blueprint_job(
    db_path: Path,
    blueprint_id: int,
    provider_config: ProviderConfig,
) -> None:
    thread = Thread(
        target=_run_blueprint_job,
        args=(db_path, blueprint_id, provider_config),
        daemon=True,
    )
    thread.start()


def _run_blueprint_job(
    db_path: Path,
    blueprint_id: int,
    provider_config: ProviderConfig,
) -> None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    previous_blueprint: dict[str, Any] | None = None
    idea = ""
    revision_notes = None

    with Session(engine) as session:
        blueprint = get_open_book_blueprint(session, blueprint_id)
        if blueprint is None:
            return
        blueprint.status = BlueprintStatus.RUNNING
        blueprint.started_at = utc_now()
        blueprint.error_message = None
        blueprint.parse_error = None
        blueprint.raw_response = ""
        blueprint.content = {}
        idea = blueprint.idea
        revision_notes = blueprint.instruction
        if blueprint.parent_id is not None:
            parent = get_open_book_blueprint(session, blueprint.parent_id)
            previous_blueprint = parent.content if parent else None
        session.add(blueprint)
        session.commit()

    raw_response = ""
    status = BlueprintStatus.SUCCEEDED
    content: dict[str, Any] = {}
    parse_error = None
    error_message = None

    try:
        raw_response = asyncio.run(
            _request_blueprint(provider_config, idea, previous_blueprint, revision_notes)
        )
        content = parse_blueprint_json(raw_response)
    except (json.JSONDecodeError, ValueError) as error:
        status = BlueprintStatus.FAILED
        parse_error = str(error)
        error_message = str(error)
    except Exception as error:  # noqa: BLE001
        status = BlueprintStatus.FAILED
        error_message = str(error)

    with Session(engine) as session:
        blueprint = get_open_book_blueprint(session, blueprint_id)
        if blueprint is None:
            return
        blueprint.status = status
        blueprint.content = content
        blueprint.raw_response = raw_response
        blueprint.parse_error = parse_error
        blueprint.error_message = error_message
        blueprint.finished_at = utc_now()
        session.add(blueprint)
        session.commit()


def _reset_blueprint_for_retry(
    session: Session,
    blueprint: OpenBookBlueprint,
) -> OpenBookBlueprint:
    blueprint.status = BlueprintStatus.PENDING
    blueprint.content = {}
    blueprint.raw_response = ""
    blueprint.parse_error = None
    blueprint.error_message = None
    blueprint.started_at = None
    blueprint.finished_at = None
    session.add(blueprint)
    session.commit()
    session.refresh(blueprint)
    return blueprint


async def _request_blueprint(
    provider_config: ProviderConfig,
    idea: str,
    previous_blueprint: dict[str, Any] | None,
    revision_notes: str | None,
) -> str:
    client = OpenAICompatibleClient(
        base_url=provider_config.llm_base_url,
        api_key=provider_config.llm_api_key or "",
    )
    response = await client.chat(
        ChatRequest(
            model=provider_config.llm_model,
            messages=build_blueprint_messages(
                idea=idea,
                previous_blueprint=previous_blueprint,
                revision_notes=revision_notes,
            ),
            temperature=0.7,
            extra={"response_format": {"type": "json_object"}},
        )
    )
    return extract_chat_content(response)


if __name__ == "__main__":
    main()
