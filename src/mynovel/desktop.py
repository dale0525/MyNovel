from __future__ import annotations

import argparse
import socket
import webbrowser
from pathlib import Path
from threading import Timer

from mynovel.dev_server import DEFAULT_DB_PATH, DEFAULT_HOST, DEFAULT_PORT, run_server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="启动 MyNovel 桌面端本地应用。")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--strict-port", action="store_true", help="只使用指定端口。")
    parser.add_argument("--no-open", action="store_true", help="启动后不自动打开窗口。")
    args = parser.parse_args(argv)

    port = args.port if args.strict_port else _available_port(args.host, args.port)
    if not args.no_open:
        Timer(0.8, _open_browser, args=(args.host, port)).start()
    run_server(args.host, port, args.db)


def _available_port(host: str, start_port: int) -> int:
    for offset in range(20):
        port = start_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return port
    raise OSError(f"No available port found from {start_port}.")


def _open_browser(host: str, port: int) -> None:
    webbrowser.open(f"http://{host}:{port}")


if __name__ == "__main__":
    main()
