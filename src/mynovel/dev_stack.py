from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8765
DEFAULT_FRONTEND_PORT = 5173
DEFAULT_DB_PATH = Path(".mynovel/dev.sqlite")


def build_api_command(host: str, port: int, db_path: Path) -> list[str]:
    return [
        "python",
        "-m",
        "mynovel.dev_server",
        "--host",
        host,
        "--port",
        str(port),
        "--db",
        str(db_path),
    ]


def build_frontend_command(host: str, port: int) -> list[str]:
    return [
        "npm",
        "--prefix",
        "frontend",
        "run",
        "dev",
        "--",
        "--host",
        host,
        "--port",
        str(port),
    ]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run MyNovel API and Vite dev servers.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--api-port", type=int, default=DEFAULT_API_PORT)
    parser.add_argument("--frontend-port", type=int, default=DEFAULT_FRONTEND_PORT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parents[2]
    processes = [
        subprocess.Popen(build_api_command(args.host, args.api_port, args.db), cwd=project_root),
        subprocess.Popen(
            build_frontend_command(args.host, args.frontend_port),
            cwd=project_root,
        ),
    ]
    print(
        f"MyNovel dev stack running:\n"
        f"- App with HMR: http://{args.host}:{args.frontend_port}\n"
        f"- API/static preview: http://{args.host}:{args.api_port}",
        flush=True,
    )

    try:
        while True:
            for process in processes:
                if process.poll() is not None:
                    raise SystemExit(process.returncode or 0)
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        print("Stopped MyNovel dev stack.", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
