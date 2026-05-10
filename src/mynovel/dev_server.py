from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from sqlmodel import Session, select

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import Book, ProviderConfig
from mynovel.domain.repositories import get_provider_config, save_provider_config
from mynovel.i18n import DEFAULT_LOCALE, t
from mynovel.workflows.open_book import create_draft_book

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
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    escaped_message = html.escape(message) if message else ""
    book_rows = _render_book_rows(books)
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

    input:disabled,
    button:disabled {{
      cursor: not-allowed;
      opacity: 0.55;
    }}

    input:focus {{
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
          <label>
            {t("book.genre", locale)}
            <input name="genre" value="web-novel"{open_book_disabled}>
          </label>
          <label>
            {t("book.audience", locale)}
            <input name="audience" value="web novel readers"{open_book_disabled}>
          </label>
          <button type="submit"{open_book_disabled}>{t("book.create", locale)}</button>
        </form>

        <h2>{t("books.title", locale)}</h2>
        <table>
          <thead>
            <tr>
              <th>{t("books.id", locale)}</th>
              <th>{t("books.premise", locale)}</th>
              <th>{t("books.genre", locale)}</th>
              <th>{t("books.status", locale)}</th>
            </tr>
          </thead>
          <tbody>
            {book_rows}
          </tbody>
        </table>
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
        embedding_base_url="",
        embedding_model="",
    )
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
            <input name="embedding_base_url" required value="{_field(config.embedding_base_url)}"
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
        and provider_config.embedding_base_url.strip()
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
                            t("book.idea_required"),
                        ),
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return

                engine = create_engine_for_path(state.db_path)
                create_db_and_tables(engine)
                with Session(engine) as session:
                    book = create_draft_book(
                        session,
                        idea=idea,
                        genre=form.get("genre", "web-novel"),
                        audience=form.get("audience", "web novel readers"),
                    )
                self._redirect_message(t("book.created", book_id=book.id))
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
        embedding_base_url=form.get("embedding_base_url", ""),
        embedding_api_key=form.get("embedding_api_key") or None,
        embedding_model=form.get("embedding_model", ""),
        rerank_base_url=form.get("rerank_base_url") or None,
        rerank_api_key=form.get("rerank_api_key") or None,
        rerank_model=form.get("rerank_model") or None,
    )


if __name__ == "__main__":
    main()
