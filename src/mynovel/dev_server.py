from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mynovel.api_errors import ApiResponse
from mynovel.api_routes import dispatch_api_get, dispatch_api_post, read_api_json_body
from mynovel.chapter_server import chapter_model_client_from_provider_config
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import ProviderConfig
from mynovel.frontend_assets import frontend_dist_path
from mynovel.legacy_cleanup import remove_legacy_placeholder_data
from mynovel.path_display import display_path
from mynovel.review_navigation import review_destination as _review_destination  # noqa: F401
from mynovel.static_server import StaticResponse, resolve_spa_response
from mynovel.word_targets import book_idea_from_form as _book_idea_from_form  # noqa: F401

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
            self._send_static_response(resolve_spa_response(parsed.path, frontend_dist_path()))

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if not _is_api_path(parsed.path):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            body, error = self._read_json()
            if error is not None:
                self._send_api_response(error)
                return
            self._send_api_response(dispatch_api_post(parsed.path, body, state.db_path))

        def log_message(self, format: str, *args: Any) -> None:
            print(f"{self.address_string()} - {format % args}")

        def _read_json(self) -> tuple[dict[str, Any], ApiResponse | None]:
            return read_api_json_body(self.headers.get("Content-Length"), self.rfile.read)

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

        def _send_static_response(self, response: StaticResponse) -> None:
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)

    return DevRequestHandler


def _classify_get_path(path: str) -> str:
    if path == "/health":
        return "health"
    if _is_api_path(path):
        return "api"
    return "static"


def _is_api_path(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")


def _chapter_model_client_from_provider_config(provider_config: ProviderConfig | None):
    return chapter_model_client_from_provider_config(provider_config)


if __name__ == "__main__":
    main()
