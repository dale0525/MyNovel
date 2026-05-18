from pathlib import Path

from mynovel.dev_stack import build_api_command, build_frontend_command, frontend_origin


def test_dev_stack_starts_python_api_and_vite_frontend() -> None:
    db_path = Path(".mynovel/dev.sqlite")

    origin = frontend_origin("127.0.0.1", 5173)

    assert build_api_command("127.0.0.1", 8765, db_path, origin) == [
        "python",
        "-m",
        "mynovel.dev_server",
        "--host",
        "127.0.0.1",
        "--port",
        "8765",
        "--db",
        str(db_path),
        "--frontend-origin",
        "http://127.0.0.1:5173",
    ]
    assert origin == "http://127.0.0.1:5173"
    assert build_frontend_command("127.0.0.1", 5173) == [
        "npm",
        "--prefix",
        "frontend",
        "run",
        "dev",
        "--",
        "--host",
        "127.0.0.1",
        "--port",
        "5173",
    ]
