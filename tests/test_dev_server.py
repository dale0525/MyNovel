from pathlib import Path
import tomllib

from mynovel.dev_server import build_health_payload, render_home


def test_dev_pixi_task_starts_local_server() -> None:
    config = tomllib.loads(Path("pixi.toml").read_text(encoding="utf-8"))

    dev_task = config["tasks"]["dev"]

    assert dev_task.startswith("mynovel-dev")
    assert "--help" not in dev_task


def test_health_payload_reports_database_path() -> None:
    payload = build_health_payload(Path(".mynovel/dev.sqlite"))

    assert payload == {"status": "ok", "database": ".mynovel/dev.sqlite"}


def test_home_page_renders_debug_surface() -> None:
    html = render_home(Path(".mynovel/dev.sqlite"), books=[], message="Ready")

    assert "MyNovel Dev" in html
    assert "Open Book" in html
    assert ".mynovel/dev.sqlite" in html
    assert "Ready" in html
