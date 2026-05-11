from pathlib import Path

from mynovel.dev_server import render_blueprint_page, render_home
from mynovel.domain.models import (
    Book,
    BookStatus,
    BlueprintStatus,
    Canon,
    Chapter,
    ChapterStatus,
    OpenBookBlueprint,
    ProviderConfig,
)
from mynovel.product_views import (
    render_book_workspace,
    render_chapter_review,
    render_model_setup_page,
    render_new_book_page,
    render_trusted_state_page,
)


def test_home_page_uses_product_language_without_exposed_english_terms() -> None:
    page = render_home(
        Path(".mynovel/dev.sqlite"),
        books=[],
        provider_config=None,
        blueprints=[],
        message=None,
    )

    assert "MyNovel" in page
    assert "创建第一本书" in page
    assert "模型未配置" in page
    assert "可信设定" in page

    forbidden_terms = [
        "调试台",
        "OpenAI-compatible",
        "LLM",
        "Embedding",
        "Rerank",
        "Base URL",
        "API Key",
        "SQLite",
        "Canon",
        "Draft",
        "StateDelta",
        "RunTrace",
    ]
    for term in forbidden_terms:
        assert term not in page


def test_model_setup_page_keeps_required_fields_but_labels_them_in_chinese() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-test",
    )

    page = render_home(
        Path(".mynovel/dev.sqlite"),
        books=[],
        provider_config=provider_config,
        blueprints=[],
        message=None,
    )

    assert 'name="llm_base_url"' in page
    assert 'name="llm_api_key"' in page
    assert 'name="llm_model"' in page
    assert "接口地址" in page
    assert "访问密钥" in page
    assert "对话模型" in page
    assert "LLM" not in page
    assert "API Key" not in page
    assert "Base URL" not in page


def test_model_setup_page_uses_dedicated_configuration_dashboard() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_api_key="local-demo-key",
        llm_model="gpt-4o-mini",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-3-small",
        rerank_use_llm_credentials=True,
        rerank_base_url="",
        rerank_model="bge-reranker-v2-m3",
    )

    page = render_model_setup_page(Path(".mynovel/dev.sqlite"), provider_config)

    assert "model-setup-layout" in page
    assert "连接你的 AI 模型" in page
    assert "服务类型" in page
    assert "OpenAI-compatible" in page
    assert "setup-checklist" in page
    assert "准备创建书籍" in page
    assert "本地数据库" in page
    assert "测试连接" in page


def test_new_book_page_requires_only_idea_and_uses_optional_presets() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-test",
    )

    page = render_new_book_page(provider_config)

    assert 'name="idea"' in page
    assert 'name="idea" type="text"' in page
    assert 'name="idea" type="text" value="" placeholder="一个失意档案员重建禁书图书馆" required' in page
    assert '<select name="genre">' in page
    assert '<select name="audience">' in page
    assert "让 AI 判断" in page
    assert "玄幻升级" in page
    assert "男频网文读者" in page
    assert "爽点偏好" not in page
    assert "写作禁区" not in page
    assert "参考风格" not in page
    assert "篇幅目标" not in page
    assert "连载节奏" not in page


def test_blueprint_page_translates_structured_model_keys() -> None:
    blueprint = OpenBookBlueprint(
        id=1,
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜图书馆"],
            "genre": "玄幻",
            "audience": "连载读者",
            "selling_points": ["禁书体系"],
            "protagonist": {"name": "林烬", "hook": "失意档案员"},
            "world": {"premise": "书籍可以封印神明"},
            "central_conflict": "重建禁书馆",
            "reader_promises": ["每章有新禁书"],
            "chapter_directions": [{"chapter": "第 1 章", "direction": "得到残页"}],
        },
        raw_response="{}",
    )

    page = render_blueprint_page(Path(".mynovel/dev.sqlite"), None, blueprint)

    assert "章节：第 1 章" in page
    assert "方向：得到残页" in page
    assert "chapter：" not in page
    assert "direction：" not in page


def test_review_page_exposes_revision_repair_accept_and_export_actions() -> None:
    book = Book(
        id=1,
        title="幽谷回声",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )
    chapter = Chapter(
        id=9,
        book_id=1,
        number=1,
        title="离开的召唤",
        status=ChapterStatus.AWAITING_REVIEW,
        revised_text="莉拉离开村庄。",
        audit_report={
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "钩子偏弱", "resolved": False}],
        },
        state_delta={"changes": [{"type": "人物状态", "target": "莉拉", "change": "离村"}]},
    )
    canon = Canon(id=1, book_id=1, version=1, content={})

    page = render_chapter_review(book, [chapter], chapter, canon)

    assert "退回修改" in page
    assert "让系统修复" in page
    assert "批准并写入可信设定" in page
    assert 'action="/request-revision"' in page
    assert 'action="/repair-chapter"' in page
    assert "导出正文" not in page

    chapter.status = ChapterStatus.ACCEPTED
    chapter.final_text = chapter.revised_text
    page = render_chapter_review(book, [chapter], chapter, canon)

    assert "导出正文" in page
    assert "/chapter/9/export" in page


def test_running_chapter_page_exposes_production_control_panels() -> None:
    book = Book(
        id=1,
        title="幽谷回声",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )
    chapters = [
        Chapter(
            id=1,
            book_id=1,
            number=1,
            title="召唤",
            status=ChapterStatus.RUNNING,
            context_package={"canon": "已收集", "characters": "6 人相关"},
            draft_text="罗斯沿着隐秘小径继续向前。",
            state_delta={"changes": []},
            word_count=1248,
        )
    ]

    page = render_chapter_review(
        book, chapters, chapters[0], Canon(id=1, book_id=1, version=1, content={})
    )

    assert "production-stage-grid" in page
    assert "下一步风控 Gate" in page
    assert "当前正在" in page
    assert "成本" in page
    assert "恢复点" in page
    assert "继续运行" in page


def test_review_page_exposes_manual_edit_and_major_change_confirmation() -> None:
    book = Book(
        id=1,
        title="幽谷回声",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )
    chapter = Chapter(
        id=9,
        book_id=1,
        number=1,
        title="离开的召唤",
        status=ChapterStatus.AWAITING_REVIEW,
        revised_text="莉拉离开村庄。",
        audit_report={"risk_level": "low", "issues": []},
        state_delta={
            "changes": [
                {
                    "type": "角色死亡",
                    "target": "罗文",
                    "change": "罗文牺牲",
                    "impact": "major",
                }
            ]
        },
    )
    canon = Canon(id=1, book_id=1, version=1, content={})

    page = render_chapter_review(book, [chapter], chapter, canon)

    assert "手动修正文" in page
    assert 'action="/edit-chapter-text"' in page
    assert 'name="manual_text"' in page
    assert "重大变化" in page
    assert 'name="allow_major_changes"' in page
    assert "review-tabs" in page
    assert "StateDelta 待验证" in page
    assert "影响范围" in page


def test_trusted_state_page_shows_full_state_sections_without_raw_keys() -> None:
    book = Book(
        id=1,
        title="幽谷回声",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )
    canon = Canon(
        id=1,
        book_id=1,
        version=3,
        content={
            "characters": [{"name": "莉拉", "detail": "能读懂古代符号"}],
            "locations": [{"name": "幽谷", "detail": "旧王朝遗迹"}],
            "relationships": [{"from": "莉拉", "to": "罗文", "detail": "临时同盟"}],
            "foreshadowing": ["第二枚符号仍未解释"],
            "chapter_summaries": [{"chapter": 1, "title": "离开的召唤", "summary": "离村"}],
            "state_history": [{"chapter": 1, "changes": [{"type": "人物状态", "target": "莉拉"}]}],
        },
    )

    page = render_trusted_state_page(book, canon, [])

    assert "可信设定" in page
    assert "人物" in page
    assert "地点" in page
    assert "关系" in page
    assert "伏笔账本" in page
    assert "章节摘要" in page
    assert "变化历史" in page
    assert "莉拉" in page
    assert "幽谷" in page
    assert "relationships：" not in page
    assert "state_history：" not in page


def test_trusted_state_page_exposes_canon_lock_gate() -> None:
    book = Book(
        id=1,
        title="幽谷回声",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.CANON_LOCKED,
    )
    canon = Canon(
        id=1,
        book_id=1,
        version=1,
        content={
            "world_rules": [{"name": "雾墙规则", "detail": "幽谷边界危险。"}],
            "characters": [{"name": "罗斯", "detail": "石匠学徒。"}],
            "locations": [{"name": "幽谷", "detail": "旧王朝遗迹。"}],
            "relationships": [{"from": "罗斯", "to": "莉拉", "detail": "临时同盟"}],
            "foreshadowing": ["第二枚符号尚未解释"],
            "chapter_summaries": [{"chapter": 1, "title": "召唤", "summary": "进入幽谷"}],
        },
    )

    page = render_trusted_state_page(book, canon, [])

    assert "canon-gate-layout" in page
    assert "审计风险" in page
    assert "强制 Gate" in page
    assert "前 10 章节奏" in page
    assert "锁定可信设定并开始生产" in page


def test_book_workspace_links_to_trusted_state_page() -> None:
    book = Book(
        id=1,
        title="幽谷回声",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )

    page = render_book_workspace(book, [], Canon(id=1, book_id=1, version=1, content={}), [])

    assert "查看可信设定" in page
    assert "/book/1/state" in page
    assert "质量增强" in page
    assert "/book/1/quality" in page


def test_book_workspace_exposes_whole_book_export_actions() -> None:
    book = Book(
        id=1,
        title="幽谷回声",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )

    page = render_book_workspace(book, [], Canon(id=1, book_id=1, version=1, content={}), [])

    assert "导出整本书" in page
    assert "/book/1/export.md" in page
    assert "/book/1/export.json" in page


def test_book_workspace_exposes_batch_chapter_production_action() -> None:
    book = Book(
        id=1,
        title="幽谷回声",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )
    chapters = [
        Chapter(
            id=1,
            book_id=1,
            number=1,
            title="离开的召唤",
            status=ChapterStatus.PLANNED,
        )
    ]

    page = render_book_workspace(book, chapters, Canon(id=1, book_id=1, version=1, content={}), [])

    assert "连续生产" in page
    assert 'action="/run-chapter-batch"' in page
    assert 'name="limit"' in page
    assert 'name="book_id" value="1"' in page


def test_project_surfaces_expose_ai_api_settings_entry() -> None:
    book = Book(
        id=1,
        title="幽谷回声",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )

    page = render_book_workspace(book, [], Canon(id=1, book_id=1, version=1, content={}), [])

    assert "/provider-config" in page
    assert "模型配置" in page
    assert "AI API 设置" in page


def test_book_workspace_hides_batch_action_when_book_is_paused() -> None:
    book = Book(
        id=1,
        title="幽谷回声",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PAUSED,
    )
    chapters = [
        Chapter(
            id=1,
            book_id=1,
            number=1,
            title="离开的召唤",
            status=ChapterStatus.AWAITING_REVIEW,
        )
    ]

    page = render_book_workspace(book, chapters, Canon(id=1, book_id=1, version=1, content={}), [])

    assert "等待人工审核" in page
    assert 'action="/run-chapter-batch"' not in page


def test_application_shell_uses_icon_navigation_and_project_context() -> None:
    book = Book(
        id=1,
        title="幽谷回声",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )
    chapters = [
        Chapter(id=1, book_id=1, number=1, title="召唤", status=ChapterStatus.ACCEPTED),
        Chapter(id=2, book_id=1, number=2, title="穿越迷雾", status=ChapterStatus.AWAITING_REVIEW),
    ]

    page = render_book_workspace(
        book,
        chapters,
        Canon(id=1, book_id=1, version=1, content={}),
        [],
    )

    assert 'class="app-shell"' in page
    assert 'class="nav-icon"' in page
    assert 'aria-hidden="true"' in page
    assert "项目概览" in page
    assert "120,000 字" in page
    assert "章节队列" in page


def test_pipeline_renders_stateful_steps_with_icons_and_connectors() -> None:
    book = Book(
        id=1,
        title="幽谷回声",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )
    chapters = [
        Chapter(id=1, book_id=1, number=1, title="召唤", status=ChapterStatus.ACCEPTED),
        Chapter(id=2, book_id=1, number=2, title="穿越迷雾", status=ChapterStatus.AWAITING_REVIEW),
    ]

    page = render_chapter_review(
        book,
        chapters,
        chapters[1],
        Canon(id=1, book_id=1, version=1, content={}),
    )

    assert "制作流水线" in page
    assert 'class="pipeline-step done"' in page
    assert 'class="pipeline-step current"' in page
    assert 'class="pipeline-connector"' in page
    assert "当前阶段" in page


def test_blueprint_review_uses_wide_proposal_layout_without_overflow_columns() -> None:
    blueprint = OpenBookBlueprint(
        id=1,
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜图书馆", "禁书归途", "群星档案"],
            "genre": "玄幻",
            "audience": "男频网文读者",
            "selling_points": ["禁书体系", "升级节奏"],
            "protagonist": {"name": "林烬", "hook": "失意档案员"},
            "world": {"premise": "书籍可以封印神明"},
            "central_conflict": "主角重建禁书馆",
            "reader_promises": ["每章有新禁书"],
            "chapter_directions": [{"chapter": "第 1 章", "direction": "得到残页"}],
        },
        raw_response="{}",
    )

    page = render_blueprint_page(Path(".mynovel/dev.sqlite"), None, blueprint)

    assert "blueprint-layout" in page
    assert "proposal-grid" in page
    assert 'class="main-panel blueprint-main"' in page
    assert 'class="right-panel blueprint-actions"' in page
    assert "方案 A" in page
