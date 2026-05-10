from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlmodel import Session, select

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import Book
from mynovel.workflows.open_book import create_draft_book

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_DB_PATH = Path(".mynovel/dev.sqlite")


@dataclass(frozen=True)
class DevServerState:
    db_path: Path


def build_health_payload(db_path: Path) -> dict[str, str]:
    return {"status": "ok", "database": str(db_path)}


def render_home(db_path: Path, books: list[Book], message: str | None = None) -> str:
    escaped_message = html.escape(message) if message else ""
    book_rows = _render_book_rows(books)
    db_label = html.escape(str(db_path))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MyNovel Dev</title>
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
      grid-template-columns: minmax(320px, 420px) 1fr;
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
        <h1>MyNovel Dev</h1>
        <p>Local review surface for the AI novel production pipeline.</p>
      </div>
      <div class="db">SQLite<br>{db_label}</div>
    </header>

    {"<p class='message'>" + escaped_message + "</p>" if escaped_message else ""}

    <div class="workspace">
      <section>
        <h2>Open Book</h2>
        <form method="post" action="/open-book">
          <label>
            Idea
            <input name="idea" required placeholder="A fallen archivist rebuilds a forbidden library">
          </label>
          <label>
            Genre
            <input name="genre" value="web-novel">
          </label>
          <label>
            Audience
            <input name="audience" value="web novel readers">
          </label>
          <button type="submit">Create Draft</button>
        </form>
      </section>

      <section>
        <h2>Draft Books</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Premise</th>
              <th>Genre</th>
              <th>Status</th>
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
        return '<tr><td class="empty" colspan="4">No draft books yet.</td></tr>'

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
            self._send_html(render_home(state.db_path, _load_books(state.db_path), message))

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/init":
                engine = create_engine_for_path(state.db_path)
                create_db_and_tables(engine)
                self._redirect("/?message=Database%20initialized")
                return
            if parsed.path == "/open-book":
                form = self._read_form()
                idea = form.get("idea", "")
                if not idea:
                    self._send_html(
                        render_home(state.db_path, _load_books(state.db_path), "Idea is required."),
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
                self._redirect(f"/?message=Created%20draft%20book%20%23{book.id}")
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

    return DevRequestHandler


def _load_books(db_path: Path) -> list[Book]:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        statement = select(Book).order_by(Book.created_at.desc()).limit(20)
        return list(session.exec(statement))


if __name__ == "__main__":
    main()
