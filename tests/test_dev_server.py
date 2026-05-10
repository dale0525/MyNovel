from pathlib import Path
import tomllib

from mynovel.dev_server import build_health_payload, render_home
from mynovel.domain.models import OpenBookBlueprint, ProviderConfig
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
    page = render_home(
        Path(".mynovel/dev.sqlite"),
        books=[],
        provider_config=None,
        blueprints=[],
        message="Ready",
    )

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
        blueprints=[],
        message=None,
    )

    assert "配置已完成" in page
    assert "配置完成后才能开书" not in page
    assert '<button type="submit" disabled>' not in page
    assert "只输入一个想法" in page
    assert "类型" not in page
    assert "读者" not in page


def test_home_page_renders_blueprint_revision_form() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-test",
    )
    blueprint = OpenBookBlueprint(
        idea="失意档案员重建禁书馆",
        version=1,
        instruction=None,
        content={
            "title_options": ["长夜图书馆"],
            "genre": "玄幻",
            "central_conflict": "重建禁书馆",
        },
        raw_response="{}",
    )

    page = render_home(
        Path(".mynovel/dev.sqlite"),
        books=[],
        provider_config=provider_config,
        blueprints=[blueprint],
        message=None,
    )

    assert "开书蓝图 v1" in page
    assert "长夜图书馆" in page
    assert "修改意见" in page


def test_i18n_defaults_to_simplified_chinese() -> None:
    assert t("app.title") == "MyNovel 调试台"
