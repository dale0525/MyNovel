from pathlib import Path
import tomllib

from mynovel.dev_server import build_health_payload, render_home
from mynovel.domain.models import ProviderConfig
from mynovel.i18n import t


def test_dev_pixi_task_starts_local_server() -> None:
    config = tomllib.loads(Path("pixi.toml").read_text(encoding="utf-8"))

    dev_task = config["tasks"]["dev"]

    assert dev_task.startswith("mynovel-dev")
    assert "--help" not in dev_task


def test_health_payload_reports_database_path() -> None:
    payload = build_health_payload(Path(".mynovel/dev.sqlite"))

    assert payload == {"status": "ok", "database": ".mynovel/dev.sqlite"}


def test_home_page_renders_debug_surface() -> None:
    page = render_home(Path(".mynovel/dev.sqlite"), books=[], provider_config=None, message="Ready")

    assert 'lang="zh-CN"' in page
    assert "MyNovel 调试台" in page
    assert "模型配置" in page
    assert "配置完成后才能开书" in page
    assert "disabled" in page
    assert ".mynovel/dev.sqlite" in page
    assert "Ready" in page


def test_home_page_enables_open_book_after_provider_config() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_base_url="https://api.example.test/v1",
        embedding_model="text-embedding-test",
    )

    page = render_home(
        Path(".mynovel/dev.sqlite"),
        books=[],
        provider_config=provider_config,
        message=None,
    )

    assert "配置已完成" in page
    assert "配置完成后才能开书" not in page
    assert '<button type="submit" disabled>' not in page


def test_i18n_defaults_to_simplified_chinese() -> None:
    assert t("app.title") == "MyNovel 调试台"
