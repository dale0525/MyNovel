from pathlib import Path
import tomllib

from mynovel.dev_server import build_health_payload, render_blueprint_page, render_home
from mynovel.domain.models import BlueprintStatus, OpenBookBlueprint, ProviderConfig
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
