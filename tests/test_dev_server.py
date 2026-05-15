from pathlib import Path, PureWindowsPath
import tomllib

from mynovel.dev_server import (
    _book_idea_from_form,
    _chapter_model_client_from_provider_config,
    _review_destination,
    build_health_payload,
    run_server,
)
from mynovel.chapter_server import queue_chapter_run
from mynovel.chapter_server import queue_chapter_batch_run
from mynovel.chapter_server import queue_chapter_repair
from mynovel.chapter_server import _mark_chapter_job_failed
from sqlmodel import Session, select

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import (
    Book,
    BookStatus,
    BlueprintStatus,
    Canon,
    Chapter,
    ChapterStatus,
    OpenBookBlueprint,
    ProviderConfig,
    RunTrace,
)
from mynovel.domain.repositories import (
    add_book,
    add_canon,
)
from mynovel.i18n import t
from mynovel.product_views import (
    render_book_workspace,
    render_blueprint_page,
    render_chapter_review,
    render_home,
)
from mynovel.workflows.chapter_pipeline import ChapterStageError


def test_dev_pixi_task_starts_local_server() -> None:
    config = tomllib.loads(Path("pixi.toml").read_text(encoding="utf-8"))

    dev_task = config["tasks"]["dev"]

    assert dev_task.startswith("mynovel-dev")
    assert "--help" not in dev_task


def test_health_payload_reports_database_path() -> None:
    payload = build_health_payload(Path(".mynovel/dev.sqlite"))

    assert payload == {"status": "ok", "database": ".mynovel/dev.sqlite"}


def test_health_payload_normalizes_windows_database_path() -> None:
    payload = build_health_payload(PureWindowsPath(".mynovel/dev.sqlite"))

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
    assert "连接你的 AI 模型" in page
    assert "模型配置" in page
    assert "连接检查" in page
    assert "先写下第一本书的核心灵感" not in page
    assert "创建第一本书" not in page
    assert "最近结果" not in page
    assert "生产流水线" not in page
    assert ".mynovel/dev.sqlite" in page
    assert "Ready" in page


def test_home_page_renders_focused_next_action_language() -> None:
    book = Book(
        id=3,
        title="长夜图书馆",
        genre="奇幻",
        audience="连载读者",
        status=BookStatus.PRODUCING,
    )
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_api_key="sk-test",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-test",
        rerank_use_llm_credentials=True,
        rerank_base_url="",
        rerank_model="rerank-test",
    )
    blueprint = OpenBookBlueprint(
        id=8,
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={},
        raw_response="{}",
    )

    page = render_home(
        Path(".mynovel/dev.sqlite"),
        [book],
        provider_config,
        [blueprint],
        None,
    )

    assert "你现在只需要做什么" in page
    assert "开书方案 · 生成完成" in page
    assert "可以开始创建书籍并调用本地模型。" not in page


def test_book_workspace_rendered_via_dev_server_focuses_current_action() -> None:
    book = Book(
        id=3,
        title="长夜图书馆",
        genre="奇幻",
        audience="连载读者",
        status=BookStatus.CANON_LOCKED,
    )
    chapters = [
        Chapter(id=1, book_id=3, number=1, title="召唤", status=ChapterStatus.PLANNED),
        Chapter(id=2, book_id=3, number=2, title="穿越迷雾", status=ChapterStatus.PLANNED),
    ]
    canon = Canon(
        id=1,
        book_id=3,
        version=1,
        content={"characters": [{"name": "罗文", "detail": "石匠学徒"}]},
    )

    page = render_book_workspace(book, chapters, canon, [])

    assert "workspace-focus-card" in page
    assert "推进第 01 章" in page
    assert "可信设定摘要" in page
    assert 'class="main-panel project-cockpit"' not in page


def test_running_chapter_rendered_via_dev_server_shows_stage_chain_and_slots() -> None:
    book = Book(
        id=3,
        title="长夜图书馆",
        genre="奇幻",
        audience="连载读者",
        status=BookStatus.PRODUCING,
    )
    chapter = Chapter(
        id=5,
        book_id=3,
        number=5,
        title="雾门",
        status=ChapterStatus.RUNNING,
        plan={"word_budget": 3200, "beat": "潜入雾门"},
        context_package={"canon": "雾门规则", "characters": ["罗文", "莉拉"]},
        draft_text="罗文把手按在雾门表面。",
        word_count=1350,
    )

    page = render_chapter_review(
        book, [chapter], chapter, Canon(id=1, book_id=3, version=1, content={})
    )

    assert "chapter-task-board" in page
    assert "chapter-stage-chain" in page
    assert 'data-slot="plan"' in page
    assert 'data-slot="audit"' in page
    assert "章节规划" in page
    assert "待产出" in page


def test_home_page_normalizes_windows_database_path() -> None:
    page = render_home(
        PureWindowsPath(".mynovel/dev.sqlite"),
        books=[],
        provider_config=None,
        blueprints=[],
        message=None,
    )

    assert ".mynovel/dev.sqlite" in page
    assert ".mynovel\\dev.sqlite" not in page


def test_home_page_enables_open_book_after_provider_config() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_api_key="sk-test",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="https://api.example.test/v1",
        embedding_model="text-embedding-test",
        rerank_use_llm_credentials=True,
        rerank_base_url="",
        rerank_model="rerank-test",
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


def test_review_destination_prefers_current_awaiting_review_chapter(tmp_path) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = Book(
            title="长夜图书馆",
            genre="奇幻",
            audience="连载读者",
            status=BookStatus.PRODUCING,
        )
        session.add(book)
        session.commit()
        session.refresh(book)
        session.add(
            Chapter(
                id=9,
                book_id=book.id,
                number=1,
                title="离开的召唤",
                status=ChapterStatus.AWAITING_REVIEW,
            )
        )
        session.commit()

    assert _review_destination(db_path) == "/chapter/9"


def test_review_destination_routes_draft_book_to_foundation_gate(tmp_path) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = Book(
            title="长夜图书馆",
            genre="奇幻",
            audience="连载读者",
            status=BookStatus.DRAFT,
        )
        session.add(book)
        session.commit()
        session.refresh(book)

    assert _review_destination(db_path) == f"/book/{book.id}/state"


def test_queue_chapter_run_marks_chapter_running_without_blocking(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(
            session,
            Book(
                title="长夜图书馆",
                genre="奇幻",
                audience="连载读者",
                status=BookStatus.CANON_LOCKED,
            ),
        )
        add_canon(session, Canon(book_id=book.id or 0, version=1, content={"characters": []}))
        chapter = Chapter(
            book_id=book.id or 0,
            number=1,
            title="离开的召唤",
            status=ChapterStatus.PLANNED,
        )
        session.add(chapter)
        session.commit()
        session.refresh(chapter)
        chapter_id = chapter.id or 0

    queued_chapter_id = queue_chapter_run(db_path, chapter_id, start_background=False)

    assert queued_chapter_id == chapter_id
    with Session(engine) as session:
        chapter = session.get(Chapter, chapter_id)
        assert chapter is not None
        assert chapter.status == ChapterStatus.RUNNING
        assert chapter.draft_text == ""


def test_queue_chapter_repair_marks_chapter_running_without_blocking(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(
            session,
            Book(
                title="长夜图书馆",
                genre="奇幻",
                audience="连载读者",
                status=BookStatus.PRODUCING,
            ),
        )
        add_canon(session, Canon(book_id=book.id or 0, version=1, content={"characters": []}))
        chapter = Chapter(
            book_id=book.id or 0,
            number=1,
            title="离开的召唤",
            status=ChapterStatus.AWAITING_REVIEW,
            draft_text="旧草稿",
            revised_text="待修复正文",
        )
        session.add(chapter)
        session.commit()
        session.refresh(chapter)
        chapter_id = chapter.id or 0

    queued_chapter_id = queue_chapter_repair(
        db_path,
        chapter_id,
        reviewer_note="补足字数",
        start_background=False,
    )

    assert queued_chapter_id == chapter_id
    with Session(engine) as session:
        chapter = session.get(Chapter, chapter_id)
        assert chapter is not None
        assert chapter.status == ChapterStatus.RUNNING
        assert chapter.reviewer_note == "AI 修复中：补足字数"
        assert chapter.revised_text == "待修复正文"


def test_chapter_job_failure_records_error_type_when_message_is_empty(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(
            session,
            Book(
                title="长夜图书馆",
                genre="奇幻",
                audience="连载读者",
                status=BookStatus.PRODUCING,
            ),
        )
        chapter = Chapter(
            book_id=book.id or 0,
            number=1,
            title="离开的召唤",
            status=ChapterStatus.RUNNING,
            revised_text="待修复正文",
        )
        session.add(chapter)
        session.commit()
        session.refresh(chapter)
        chapter_id = chapter.id or 0
        book_id = book.id or 0

    _mark_chapter_job_failed(db_path, chapter_id, RuntimeError())

    with Session(engine) as session:
        chapter = session.get(Chapter, chapter_id)
        traces = list(session.exec(select(RunTrace).where(RunTrace.book_id == book_id)))

    assert chapter is not None
    assert chapter.status == ChapterStatus.NEEDS_REVISION
    assert chapter.reviewer_note == "生成失败：RuntimeError"
    assert traces[-1].stage == "修复失败"
    assert traces[-1].metadata_["error_type"] == "RuntimeError"


def test_chapter_job_failure_records_raw_model_response_for_json_parse_errors(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(
            session,
            Book(
                title="长夜图书馆",
                genre="奇幻",
                audience="连载读者",
                status=BookStatus.PRODUCING,
            ),
        )
        chapter = Chapter(
            book_id=book.id or 0,
            number=2,
            title="恶奴欺主",
            status=ChapterStatus.RUNNING,
            revised_text="待修复正文",
        )
        session.add(chapter)
        session.commit()
        session.refresh(chapter)
        chapter_id = chapter.id or 0
        book_id = book.id or 0

    error = ChapterStageError(
        "word_count_patch",
        ValueError("Expecting value"),
        messages=[{"role": "system", "content": "你是章节修订补丁规划器。"}],
        response_format="json",
        raw_response_text="模型错误地返回了完整正文",
    )
    _mark_chapter_job_failed(db_path, chapter_id, error)

    with Session(engine) as session:
        traces = list(session.exec(select(RunTrace).where(RunTrace.book_id == book_id)))

    metadata = traces[-1].metadata_
    assert metadata["failed_stage"] == "word_count_patch"
    assert metadata["response_format"] == "json"
    assert metadata["raw_response_text"] == "模型错误地返回了完整正文"
    assert metadata["prompt_messages"][0]["content"] == "你是章节修订补丁规划器。"


def test_queue_chapter_batch_run_redirects_to_first_running_chapter(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(
            session,
            Book(
                title="长夜图书馆",
                genre="奇幻",
                audience="连载读者",
                status=BookStatus.CANON_LOCKED,
            ),
        )
        add_canon(session, Canon(book_id=book.id or 0, version=1, content={"characters": []}))
        first = Chapter(
            book_id=book.id or 0,
            number=1,
            title="离开的召唤",
            status=ChapterStatus.PLANNED,
        )
        second = Chapter(
            book_id=book.id or 0,
            number=2,
            title="穿越迷雾",
            status=ChapterStatus.PLANNED,
        )
        session.add(first)
        session.add(second)
        session.commit()
        session.refresh(first)
        book_id = book.id or 0
        first_id = first.id or 0

    queued_chapter_id = queue_chapter_batch_run(
        db_path,
        book_id,
        limit=2,
        start_background=False,
    )

    assert queued_chapter_id == first_id
    with Session(engine) as session:
        chapter = session.get(Chapter, first_id)
        assert chapter is not None
        assert chapter.status == ChapterStatus.RUNNING


def test_book_idea_from_form_keeps_idea_required_and_uses_visible_presets() -> None:
    idea = _book_idea_from_form(
        {
            "idea": "失意档案员重建禁书馆",
            "genre": "玄幻升级",
            "audience": "男频网文读者",
            "target_word_count": "300000",
            "chapter_word_count": "3200",
            "selling_points": "逆袭反转、智商碾压",
            "constraints": "不写虐主",
            "style_reference": "旧版字段应该忽略",
            "length_goal": "旧版字段应该忽略",
            "serial_rhythm": "旧版字段应该忽略",
        }
    )

    assert "一句灵感：失意档案员重建禁书馆" in idea
    assert "题材：玄幻升级" in idea
    assert "目标读者：男频网文读者" in idea
    assert "全书目标字数：300000 字" in idea
    assert "单章目标字数：3200 字" in idea
    assert "爽点偏好：逆袭反转、智商碾压" in idea
    assert "写作禁区：不写虐主" in idea
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
        llm_api_key="sk-test",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-test",
        rerank_use_llm_credentials=True,
        rerank_base_url="",
        rerank_model="rerank-test",
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

    assert "先写下第一本书的核心灵感" in page
    assert "模型已配置" in page
    assert "最近结果" in page
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
    assert "自动刷新中" in page
    assert "立即刷新" in page
    assert "失意档案员重建禁书馆" in page
    assert "blueprint.generating_title" not in page
    assert "setTimeout(() => window.location.reload(), 3000)" in page
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

    assert "当前选择" in page
    assert "长夜图书馆" in page
    assert 'name="selected_title"' in page
    assert 'value="长夜图书馆"' in page
    assert "选定这个书名，生成可信设定定盘预览" in page
    assert 'type="radio"' not in page
    assert "data-blueprint-detail-panel" in page
    assert 'action="/revise-blueprint"' in page
    assert 'name="revision_notes"' in page
    assert 'name="revision_preset"' in page
    assert "让系统修改蓝图" in page
    assert "换一批" in page
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
        message="请先选定一个书名，再生成可信设定定盘预览。",
    )

    assert "请先选定一个书名，再生成可信设定定盘预览。" in page


def test_i18n_defaults_to_simplified_chinese() -> None:
    assert t("app.title") == "MyNovel"
