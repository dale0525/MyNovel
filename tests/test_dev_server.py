from pathlib import Path
import tomllib

from mynovel.dev_server import (
    _book_idea_from_form,
    _chapter_model_client_from_provider_config,
    _parse_batch_limit,
    _parse_book_export,
    _parse_book_quality_id,
    _parse_book_state_id,
    build_health_payload,
    render_blueprint_page,
    render_home,
    run_server,
)
from sqlmodel import Session, select

from mynovel.db import create_engine_for_path
from mynovel.domain.models import Book, BlueprintStatus, OpenBookBlueprint, ProviderConfig
from mynovel.i18n import t


def test_dev_pixi_task_starts_local_server() -> None:
    config = tomllib.loads(Path("pixi.toml").read_text(encoding="utf-8"))

    dev_task = config["tasks"]["dev"]

    assert dev_task.startswith("mynovel-dev")
    assert "--help" not in dev_task


def test_health_payload_reports_database_path() -> None:
    payload = build_health_payload(Path(".mynovel/dev.sqlite"))

    assert payload == {"status": "ok", "database": ".mynovel/dev.sqlite"}


def test_home_page_renders_product_surface() -> None:
    page = render_home(
        Path(".mynovel/dev.sqlite"),
        books=[],
        provider_config=None,
        blueprints=[],
        message="Ready",
    )

    assert 'lang="zh-CN"' in page
    assert "MyNovel" in page
    assert "还没有书籍" in page
    assert "模型配置" in page
    assert "模型未配置" in page
    assert "创建第一本书" in page
    assert "可信设定" in page
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

    assert "模型已配置" in page
    assert "配置完成后才能开书" not in page
    assert "创建第一本书" in page
    assert "接口地址" in page
    assert "访问密钥" in page
    assert "对话模型" in page


def test_chapter_generation_uses_saved_dialogue_model_config() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_api_key="secret",
        llm_model="chapter-model",
        embedding_base_url="https://api.example.test/v1",
        embedding_model="text-embedding-test",
    )

    client, model_name = _chapter_model_client_from_provider_config(provider_config)

    assert client is not None
    assert client.model == "chapter-model"
    assert client.client.base_url == "https://api.example.test/v1"
    assert model_name == "chapter-model"


def test_book_state_route_parser_extracts_book_id() -> None:
    assert _parse_book_state_id("/book/42/state") == 42
    assert _parse_book_state_id("/book/not-a-number/state") == 0


def test_book_quality_route_parser_extracts_book_id() -> None:
    assert _parse_book_quality_id("/book/42/quality") == 42
    assert _parse_book_quality_id("/book/not-a-number/quality") == 0


def test_book_export_route_parser_extracts_book_id_and_format() -> None:
    assert _parse_book_export("/book/42/export.md") == (42, "markdown")
    assert _parse_book_export("/book/42/export.json") == (42, "json")
    assert _parse_book_export("/book/42/export.pdf") == (0, "")


def test_parse_batch_limit_clamps_to_safe_range() -> None:
    assert _parse_batch_limit({"limit": "5"}) == 5
    assert _parse_batch_limit({"limit": "0"}) == 1
    assert _parse_batch_limit({"limit": "99"}) == 10
    assert _parse_batch_limit({"limit": "bad"}) == 1


def test_book_idea_from_form_keeps_only_idea_required_and_optional_presets() -> None:
    idea = _book_idea_from_form(
        {
            "idea": "失意档案员重建禁书馆",
            "genre": "玄幻升级",
            "audience": "男频网文读者",
            "selling_points": "旧版字段应该忽略",
            "constraints": "旧版字段应该忽略",
            "style_reference": "旧版字段应该忽略",
            "length_goal": "旧版字段应该忽略",
            "serial_rhythm": "旧版字段应该忽略",
        }
    )

    assert "一句灵感：失意档案员重建禁书馆" in idea
    assert "题材：玄幻升级" in idea
    assert "目标读者：男频网文读者" in idea
    assert "旧版字段应该忽略" not in idea
    assert _book_idea_from_form({"idea": "", "genre": "玄幻升级"}) == ""


def test_default_server_database_starts_without_placeholder_book(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "dev.sqlite"

    class FakeServer:
        server_port = 8765

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            pass

    monkeypatch.setattr("mynovel.dev_server.DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr("mynovel.dev_server.ThreadingHTTPServer", FakeServer)

    run_server("127.0.0.1", 0, db_path)

    engine = create_engine_for_path(db_path)
    with Session(engine) as session:
        books = list(session.exec(select(Book)))

    assert books == []


def test_home_page_keeps_language_product_focused_with_blueprints_present() -> None:
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

    assert "还没有书籍" in page
    assert "模型已配置" in page
    assert "调试台" not in page
    assert "Canon" not in page


def test_blueprint_page_renders_pending_job_without_content() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_base_url="https://api.example.test/v1",
        embedding_model="text-embedding-test",
    )
    blueprint = OpenBookBlueprint(
        id=7,
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.PENDING,
        instruction=None,
        content={},
        raw_response="",
    )

    page = render_blueprint_page(Path(".mynovel/dev.sqlite"), provider_config, blueprint)

    assert "正在生成开书蓝图" in page
    assert "手动刷新" in page
    assert "重新尝试" not in page


def test_blueprint_page_renders_failure_retry() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_base_url="https://api.example.test/v1",
        embedding_model="text-embedding-test",
    )
    blueprint = OpenBookBlueprint(
        id=8,
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.FAILED,
        instruction=None,
        content={},
        raw_response="not json",
        parse_error="missing fields",
        error_message="missing fields",
    )

    page = render_blueprint_page(Path(".mynovel/dev.sqlite"), provider_config, blueprint)

    assert "生成失败" in page
    assert "missing fields" in page
    assert 'action="/retry-blueprint"' in page
    assert "重新尝试" in page


def test_blueprint_page_renders_structured_blueprint() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_base_url="https://api.example.test/v1",
        embedding_model="text-embedding-test",
    )
    blueprint = OpenBookBlueprint(
        id=9,
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        instruction=None,
        content={
            "title_options": ["长夜图书馆", "禁书归途"],
            "genre": "玄幻",
            "audience": "男频网文读者",
            "selling_points": ["禁书体系", "升级节奏"],
            "protagonist": {"name": "林烬", "hook": "失意档案员"},
            "world": {"premise": "书籍可以封印神明"},
            "central_conflict": "主角重建禁书馆",
            "reader_promises": ["每章有新禁书"],
            "chapter_directions": [
                {"chapter": "第 1 章", "direction": "得到残页"},
                {"chapter": "第 2 章", "direction": "发现追杀者"},
            ],
        },
        raw_response="{}",
    )

    page = render_blueprint_page(Path(".mynovel/dev.sqlite"), provider_config, blueprint)

    assert "书名候选" in page
    assert "长夜图书馆" in page
    assert 'name="selected_title"' in page
    assert 'value="长夜图书馆"' in page
    assert "确认书名，进入下一步" in page
    assert "核心冲突" in page
    assert "前 10 章方向" in page
    assert "章节：第 1 章" in page
    assert "得到残页" in page
    assert "{&#x27;chapter&#x27;" not in page
    assert '"title_options"' not in page


def test_blueprint_page_renders_title_required_message() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_base_url="https://api.example.test/v1",
        embedding_model="text-embedding-test",
    )
    blueprint = OpenBookBlueprint(
        id=10,
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        instruction=None,
        content={
            "title_options": ["长夜图书馆"],
            "genre": "玄幻",
            "audience": "男频网文读者",
            "selling_points": [],
            "protagonist": {},
            "world": {},
            "central_conflict": "主角重建禁书馆",
            "reader_promises": [],
            "chapter_directions": [],
        },
        raw_response="{}",
    )

    page = render_blueprint_page(
        Path(".mynovel/dev.sqlite"),
        provider_config,
        blueprint,
        message="请选择一个书名后再进入下一步。",
    )

    assert "请选择一个书名后再进入下一步。" in page


def test_i18n_defaults_to_simplified_chinese() -> None:
    assert t("app.title") == "MyNovel"
