from __future__ import annotations

import argparse
import asyncio
import html
import json
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from sqlmodel import Session, select

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import Book, BlueprintStatus, OpenBookBlueprint, ProviderConfig, utc_now
from mynovel.domain.repositories import (
    get_open_book_blueprint,
    get_provider_config,
    list_open_book_blueprints,
    save_provider_config,
)
from mynovel.dev_views import (
    blueprint_status_label,
    render_blueprint_page,
    render_structured_blueprint,
)
from mynovel.i18n import DEFAULT_LOCALE, t
from mynovel.llm.openai_compatible import ChatRequest, OpenAICompatibleClient
from mynovel.workflows.open_book import create_draft_book_from_blueprint
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


def render_home(
    db_path: Path,
    books: list[Book],
    provider_config: ProviderConfig | None,
    blueprints: list[OpenBookBlueprint] | None = None,
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    escaped_message = html.escape(message) if message else ""
    blueprints = blueprints or []
    blueprint_panel = _render_blueprint_panel(blueprints, locale)
    db_label = html.escape(str(db_path))
    configured = is_provider_config_complete(provider_config)
    config_status = t("status.configured", locale) if configured else t("status.not_configured", locale)
    open_book_disabled = "" if configured else " disabled"
    provider_form = _render_provider_form(provider_config, locale)

    return f"""<!doctype html>
<html lang="{locale}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{t("app.title", locale)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #eef2ed;
      --panel: #fbfcf8;
      --ink: #1e2a24;
      --muted: #65736b;
      --line: #d5ddd2;
      --accent: #356b55;
      --accent-ink: #ffffff;
      --warn: #7a5b21;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }}

    main {{
      width: min(1120px, calc(100% - 32px));
      margin: 0 auto;
      padding: 32px 0;
    }}

    header {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 24px;
      margin-bottom: 28px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 20px;
    }}

    h1 {{
      margin: 0 0 8px;
      font-size: 34px;
      line-height: 1.1;
      font-weight: 720;
    }}

    p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }}

    .db {{
      color: var(--muted);
      font-size: 14px;
      text-align: right;
    }}

    .workspace {{
      display: grid;
      grid-template-columns: minmax(360px, 460px) 1fr;
      gap: 24px;
      align-items: start;
    }}

    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 20px;
    }}

    h2 {{
      margin: 0 0 16px;
      font-size: 18px;
      line-height: 1.3;
    }}

    form {{
      display: grid;
      gap: 14px;
    }}

    label {{
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 13px;
    }}

    input {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #ffffff;
      color: var(--ink);
      font: inherit;
      min-height: 42px;
      padding: 9px 11px;
    }}

    input[type="checkbox"] {{
      width: auto;
      min-height: auto;
      margin: 0;
    }}

    textarea {{
      width: 100%;
      min-height: 96px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #ffffff;
      color: var(--ink);
      font: inherit;
      padding: 9px 11px;
    }}

    input:disabled,
    button:disabled,
    textarea:disabled {{
      cursor: not-allowed;
      opacity: 0.55;
    }}

    input:focus,
    textarea:focus {{
      border-color: var(--accent);
      outline: 3px solid rgba(53, 107, 85, 0.18);
    }}

    button {{
      border: 0;
      border-radius: 6px;
      background: var(--accent);
      color: var(--accent-ink);
      cursor: pointer;
      font: inherit;
      font-weight: 650;
      min-height: 42px;
      padding: 10px 14px;
    }}

    button.secondary {{
      border: 1px solid var(--line);
      background: #ffffff;
      color: var(--ink);
    }}

    .message {{
      margin-bottom: 16px;
      color: var(--warn);
      font-size: 14px;
    }}

    .status {{
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      font-size: 13px;
      min-height: 28px;
      padding: 3px 10px;
    }}

    .section-intro {{
      margin-bottom: 16px;
      font-size: 14px;
    }}

    .inline-check {{
      display: flex;
      grid-template-columns: auto 1fr;
      align-items: center;
      gap: 8px;
      color: var(--ink);
    }}

    .blueprint {{
      margin-top: 20px;
      border-top: 1px solid var(--line);
      padding-top: 18px;
    }}

    .blueprint pre {{
      overflow: auto;
      max-height: 360px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f6f8f3;
      color: var(--ink);
      font-size: 13px;
      line-height: 1.55;
      padding: 14px;
      white-space: pre-wrap;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}

    th,
    td {{
      border-bottom: 1px solid var(--line);
      padding: 12px 8px;
      text-align: left;
      vertical-align: top;
    }}

    th {{
      color: var(--muted);
      font-weight: 650;
    }}

    td.empty {{
      color: var(--muted);
    }}

    @media (max-width: 800px) {{
      main {{
        width: min(100% - 20px, 720px);
        padding: 20px 0;
      }}

      header,
      .workspace {{
        display: grid;
        grid-template-columns: 1fr;
      }}

      .db {{
        text-align: left;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>{t("app.title", locale)}</h1>
        <p>{t("app.subtitle", locale)}</p>
      </div>
      <div class="db">{t("app.sqlite", locale)}<br>{db_label}</div>
    </header>

    {"<p class='message'>" + escaped_message + "</p>" if escaped_message else ""}

    <div class="workspace">
      <section>
        <h2>{t("provider.title", locale)}</h2>
        <p class="section-intro">{t("provider.description", locale)}</p>
        {provider_form}
      </section>

      <section>
        <h2>{t("book.title", locale)}</h2>
        <p class="section-intro">{t("book.description", locale)}</p>
        <p class="status">{config_status}</p>
        <form method="post" action="/open-book">
          <label>
            {t("book.idea", locale)}
            <input name="idea" required placeholder="{t("book.idea_placeholder", locale)}"
              {open_book_disabled}>
          </label>
          <button type="submit"{open_book_disabled}>{t("book.create", locale)}</button>
        </form>

        {blueprint_panel}
      </section>
    </div>
  </main>
</body>
</html>
"""


def _render_book_rows(books: list[Book]) -> str:
    if not books:
        return f'<tr><td class="empty" colspan="4">{t("status.no_books")}</td></tr>'

    rows = []
    for book in books:
        rows.append(
            "<tr>"
            f"<td>{book.id}</td>"
            f"<td>{html.escape(book.premise or '')}</td>"
            f"<td>{html.escape(book.genre)}</td>"
            f"<td>{html.escape(str(book.status))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _render_provider_form(provider_config: ProviderConfig | None, locale: str) -> str:
    config = provider_config or ProviderConfig(
        llm_base_url="",
        llm_model="",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="",
        rerank_use_llm_credentials=True,
    )
    embedding_checked = " checked" if config.embedding_use_llm_credentials else ""
    rerank_checked = " checked" if config.rerank_use_llm_credentials else ""
    return f"""
        <form method="post" action="/provider-config">
          <label>
            {t("provider.llm_base_url", locale)}
            <input name="llm_base_url" required value="{_field(config.llm_base_url)}"
              placeholder="https://api.openai.com/v1">
          </label>
          <label>
            {t("provider.llm_api_key", locale)}
            <input name="llm_api_key" type="password" value="{_field(config.llm_api_key)}">
          </label>
          <label>
            {t("provider.llm_model", locale)}
            <input name="llm_model" required value="{_field(config.llm_model)}"
              placeholder="gpt-4.1">
          </label>
          <label>
            {t("provider.embedding_base_url", locale)}
            <input name="embedding_base_url" value="{_field(config.embedding_base_url)}"
              placeholder="https://api.openai.com/v1">
          </label>
          <label>
            {t("provider.embedding_api_key", locale)}
            <input name="embedding_api_key" type="password" value="{_field(config.embedding_api_key)}">
          </label>
          <label>
            {t("provider.embedding_model", locale)}
            <input name="embedding_model" required value="{_field(config.embedding_model)}"
              placeholder="text-embedding-3-small">
          </label>
          <label class="inline-check">
            <input name="embedding_use_llm_credentials" type="checkbox" value="1"{embedding_checked}>
            {t("provider.embedding_use_llm", locale)}
          </label>
          <label>
            {t("provider.rerank_base_url", locale)}
            <input name="rerank_base_url" value="{_field(config.rerank_base_url)}">
          </label>
          <label>
            {t("provider.rerank_api_key", locale)}
            <input name="rerank_api_key" type="password" value="{_field(config.rerank_api_key)}">
          </label>
          <label>
            {t("provider.rerank_model", locale)}
            <input name="rerank_model" value="{_field(config.rerank_model)}">
          </label>
          <label class="inline-check">
            <input name="rerank_use_llm_credentials" type="checkbox" value="1"{rerank_checked}>
            {t("provider.rerank_use_llm", locale)}
          </label>
          <button type="submit">{t("provider.save", locale)}</button>
        </form>
"""


def _field(value: str | None) -> str:
    return html.escape(value or "", quote=True)


def is_provider_config_complete(provider_config: ProviderConfig | None) -> bool:
    return bool(
        provider_config
        and provider_config.llm_base_url.strip()
        and provider_config.llm_model.strip()
        and provider_config.resolved_embedding_base_url().strip()
        and provider_config.embedding_model.strip()
    )


def run_server(host: str, port: int, db_path: Path) -> None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)

    state = DevServerState(db_path=db_path)
    handler = _make_handler(state)
    server = ThreadingHTTPServer((host, port), handler)
    actual_host, actual_port = server.server_address
    print(f"MyNovel dev server running at http://{actual_host}:{actual_port}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped MyNovel dev server.")
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the local MyNovel debug server.")
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
            if parsed.path.startswith("/blueprint/"):
                blueprint_id = _parse_blueprint_id(parsed.path)
                provider_config = _load_provider_config(state.db_path)
                blueprint = _load_open_book_blueprint(state.db_path, blueprint_id)
                if blueprint is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self._send_html(render_blueprint_page(state.db_path, provider_config, blueprint))
                return
            if parsed.path != "/":
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            params = parse_qs(parsed.query)
            message = params.get("message", [None])[0]
            provider_config = _load_provider_config(state.db_path)
            self._send_html(
                render_home(
                    state.db_path,
                    _load_books(state.db_path),
                    provider_config,
                    _load_open_book_blueprints(state.db_path),
                    message,
                )
            )

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/init":
                engine = create_engine_for_path(state.db_path)
                create_db_and_tables(engine)
                self._redirect_message(t("provider.saved"))
                return
            if parsed.path == "/provider-config":
                form = self._read_form()
                engine = create_engine_for_path(state.db_path)
                create_db_and_tables(engine)
                with Session(engine) as session:
                    save_provider_config(session, _provider_config_from_form(form))
                self._redirect_message(t("provider.saved"))
                return
            if parsed.path == "/open-book":
                form = self._read_form()
                idea = form.get("idea", "")
                provider_config = _load_provider_config(state.db_path)
                if not is_provider_config_complete(provider_config):
                    self._send_html(
                        render_home(
                            state.db_path,
                            _load_books(state.db_path),
                            provider_config,
                            _load_open_book_blueprints(state.db_path),
                            t("status.not_configured"),
                        ),
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                if not idea:
                    self._send_html(
                        render_home(
                            state.db_path,
                            _load_books(state.db_path),
                            provider_config,
                            _load_open_book_blueprints(state.db_path),
                            t("book.idea_required"),
                        ),
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return

                engine = create_engine_for_path(state.db_path)
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
                _start_blueprint_job(state.db_path, blueprint_id, provider_config)
                self._redirect(f"/blueprint/{blueprint_id}")
                return
            if parsed.path == "/revise-blueprint":
                form = self._read_form()
                revision_notes = form.get("revision_notes", "")
                provider_config = _load_provider_config(state.db_path)
                blueprints = _load_open_book_blueprints(state.db_path)
                if not provider_config or not is_provider_config_complete(provider_config):
                    self._send_html(
                        render_home(
                            state.db_path,
                            _load_books(state.db_path),
                            provider_config,
                            blueprints,
                            t("status.not_configured"),
                        ),
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                if not blueprints:
                    self._redirect("/")
                    return
                if not revision_notes:
                    self._send_html(
                        render_home(
                            state.db_path,
                            _load_books(state.db_path),
                            provider_config,
                            blueprints,
                            t("blueprint.revision_required"),
                        ),
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return

                latest = blueprints[0]
                engine = create_engine_for_path(state.db_path)
                create_db_and_tables(engine)
                with Session(engine) as session:
                    blueprint = create_blueprint_job(
                        session,
                        idea=latest.idea,
                        version=latest.version + 1,
                        instruction=revision_notes,
                        parent_id=latest.id,
                    )
                    blueprint_id = blueprint.id
                if blueprint_id is None:
                    self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)
                    return
                _start_blueprint_job(state.db_path, blueprint_id, provider_config)
                self._redirect(f"/blueprint/{blueprint_id}")
                return
            if parsed.path == "/retry-blueprint":
                form = self._read_form()
                blueprint_id = int(form.get("blueprint_id", "0"))
                provider_config = _load_provider_config(state.db_path)
                if not provider_config or not is_provider_config_complete(provider_config):
                    self.send_error(HTTPStatus.BAD_REQUEST)
                    return
                engine = create_engine_for_path(state.db_path)
                create_db_and_tables(engine)
                with Session(engine) as session:
                    blueprint = get_open_book_blueprint(session, blueprint_id)
                    if blueprint is None:
                        self.send_error(HTTPStatus.NOT_FOUND)
                        return
                    _reset_blueprint_for_retry(session, blueprint)
                _start_blueprint_job(state.db_path, blueprint_id, provider_config)
                self._redirect(f"/blueprint/{blueprint_id}")
                return
            if parsed.path == "/accept-blueprint":
                form = self._read_form()
                blueprint_id = int(form.get("blueprint_id", "0"))
                selected_title = form.get("selected_title", "")
                provider_config = _load_provider_config(state.db_path)
                engine = create_engine_for_path(state.db_path)
                create_db_and_tables(engine)
                with Session(engine) as session:
                    blueprint = get_open_book_blueprint(session, blueprint_id)
                    if blueprint is None:
                        self.send_error(HTTPStatus.NOT_FOUND)
                        return
                    if blueprint.status != BlueprintStatus.SUCCEEDED:
                        self.send_error(HTTPStatus.BAD_REQUEST)
                        return
                    try:
                        book = create_draft_book_from_blueprint(
                            session,
                            blueprint,
                            selected_title=selected_title,
                        )
                    except ValueError:
                        self._send_html(
                            render_blueprint_page(
                                state.db_path,
                                provider_config,
                                blueprint,
                                t("blueprint.title_required"),
                            ),
                            status=HTTPStatus.BAD_REQUEST,
                        )
                        return

                self._redirect_message(
                    t(
                        "book.created_from_blueprint",
                        title=book.title,
                        book_id=book.id,
                    )
                )
                return

            self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: Any) -> None:
            print(f"{self.address_string()} - {format % args}")

        def _read_form(self) -> dict[str, str]:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            return {key: values[0].strip() for key, values in parse_qs(body).items()}

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
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        statement = select(Book).order_by(Book.created_at.desc()).limit(20)
        return list(session.exec(statement))


def _load_provider_config(db_path: Path) -> ProviderConfig | None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        return get_provider_config(session)


def _provider_config_from_form(form: dict[str, str]) -> ProviderConfig:
    return ProviderConfig(
        llm_base_url=form.get("llm_base_url", ""),
        llm_api_key=form.get("llm_api_key") or None,
        llm_model=form.get("llm_model", ""),
        embedding_use_llm_credentials=form.get("embedding_use_llm_credentials") == "1",
        embedding_base_url=form.get("embedding_base_url", ""),
        embedding_api_key=form.get("embedding_api_key") or None,
        embedding_model=form.get("embedding_model", ""),
        rerank_use_llm_credentials=form.get("rerank_use_llm_credentials") == "1",
        rerank_base_url=form.get("rerank_base_url") or None,
        rerank_api_key=form.get("rerank_api_key") or None,
        rerank_model=form.get("rerank_model") or None,
    )


def _load_open_book_blueprints(db_path: Path) -> list[OpenBookBlueprint]:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        return list_open_book_blueprints(session)


def _load_open_book_blueprint(db_path: Path, blueprint_id: int) -> OpenBookBlueprint | None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        return get_open_book_blueprint(session, blueprint_id)


def _parse_blueprint_id(path: str) -> int:
    _, _, raw_id = path.rpartition("/")
    try:
        return int(raw_id)
    except ValueError:
        return 0


def _render_blueprint_panel(blueprints: list[OpenBookBlueprint], locale: str) -> str:
    if not blueprints:
        return f'<div class="blueprint"><p>{t("blueprint.empty", locale)}</p></div>'

    latest = blueprints[0]
    title = t("blueprint.title", locale, version=latest.version)
    status = blueprint_status_label(latest.status, locale)
    body = render_structured_blueprint(latest.content, locale) if latest.content else f"<p>{status}</p>"

    return f"""
        <div class="blueprint">
          <h2>{title}</h2>
          {body}
          <div class="actions">
            <a class="button secondary" href="/blueprint/{latest.id}">{t("blueprint.open", locale)}</a>
          </div>
        </div>
"""


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
