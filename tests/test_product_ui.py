from datetime import UTC, datetime
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
    RunTrace,
    VolumePlan,
)
from mynovel.import_views import render_import_project_page
from mynovel.i18n import TRANSLATIONS
from mynovel.product_views import (
    render_book_workspace,
    render_chapter_review,
    render_model_setup_page,
    render_new_book_page,
    render_trusted_state_page,
)
from mynovel.ui_shell import app_css, render_app_page


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


def test_home_page_prioritizes_single_next_action_card() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-test",
    )
    blueprint = OpenBookBlueprint(
        id=7,
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={},
        raw_response="{}",
    )

    page = render_home(
        Path("/tmp/demo.db"),
        [book],
        provider_config,
        [blueprint],
    )

    assert "current-focus-card" in page
    assert "当前最该推进" in page
    assert "最近结果" in page
    assert "开书方案 · 生成完成" in page
    assert "可以开始创建书籍并调用本地模型。" not in page
    assert "信息汇总" not in page


def test_home_page_prefers_newest_result_across_books_and_blueprints() -> None:
    older_blueprint = OpenBookBlueprint(
        id=7,
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={},
        raw_response="{}",
        created_at=datetime(2026, 5, 14, 8, 0, tzinfo=UTC),
    )
    newer_book = Book(
        id=2,
        title="群星档案",
        genre="科幻冒险",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
        created_at=datetime(2026, 5, 14, 7, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 15, 9, 0, tzinfo=UTC),
    )
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-test",
    )

    page = render_home(Path("/tmp/demo.db"), [newer_book], provider_config, [older_blueprint])

    assert "群星档案 · 连载中" in page
    assert page.index("群星档案") < page.index("开书方案")


def test_home_page_escapes_recent_result_titles() -> None:
    book = Book(
        id=3,
        title="<script>alert('x')</script>",
        genre="悬疑推理",
        audience="悬疑推理读者",
        status=BookStatus.PRODUCING,
        updated_at=datetime(2026, 5, 15, 10, 0, tzinfo=UTC),
    )
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-test",
    )

    page = render_home(Path("/tmp/demo.db"), [book], provider_config, [])

    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt; · 连载中" in page
    assert "<script>alert('x')</script> · 连载中" not in page


def test_project_home_uses_translation_for_settings_link(monkeypatch) -> None:
    monkeypatch.setitem(TRANSLATIONS["zh-CN"], "home.settings_link", "前往模型配置_TEST")
    book = Book(
        id=4,
        title="镜海回声",
        genre="悬疑推理",
        audience="悬疑推理读者",
        status=BookStatus.PRODUCING,
    )
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-test",
    )

    page = render_home(Path("/tmp/demo.db"), [book], provider_config, [])

    assert "前往模型配置_TEST" in page


def test_new_book_page_uses_translations_for_preview_and_optional_copy(monkeypatch) -> None:
    monkeypatch.setitem(TRANSLATIONS["zh-CN"], "new_book.preview_card_title_options", "预览标题_TEST")
    monkeypatch.setitem(
        TRANSLATIONS["zh-CN"],
        "new_book.selling_points_placeholder",
        "爽点占位_TEST",
    )
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-test",
    )

    page = render_new_book_page(provider_config)

    assert "预览标题_TEST" in page
    assert 'placeholder="爽点占位_TEST"' in page


def test_first_launch_home_matches_empty_project_flow_surface() -> None:
    page = render_home(
        Path(".mynovel/dev.sqlite"),
        books=[],
        provider_config=None,
        blueprints=[],
        message=None,
    )

    assert "first-launch-layout" in page
    assert "first-launch-hero" in page
    assert 'href="/books/new"' in page
    assert 'href="/books/import"' in page
    assert 'href="/provider-config"' in page
    assert "先写下第一本书的核心灵感" in page
    assert "你现在只需要做什么" in page
    assert "最近结果" in page
    assert "打开项目" in page
    assert '<a class="button secondary compact-button" href="/books/import">打开项目</a>' in page
    assert "模型就绪状态" in page
    assert "模型未配置" in page
    assert "生产流水线" in page
    assert "开书" in page
    assert "定盘" in page
    assert "生成" in page
    assert "审核" in page
    assert "写入可信设定" in page


def test_import_project_page_exposes_json_import_form() -> None:
    page = render_import_project_page()

    assert "导入项目" in page
    assert 'action="/books/import"' in page
    assert 'name="project_json"' in page
    assert "粘贴从 MyNovel 导出的 JSON" in page


def test_empty_home_keeps_latest_blueprint_entry_visible() -> None:
    blueprint = OpenBookBlueprint(
        id=7,
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={},
        raw_response="{}",
    )

    page = render_home(
        Path(".mynovel/dev.sqlite"),
        books=[],
        provider_config=None,
        blueprints=[blueprint],
        message=None,
    )

    assert "开书方案" in page
    assert "/blueprint/7" in page
    assert "生成完成" in page


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
    assert "setup-guide-card" in page
    assert "annotated-model-field" in page
    assert "setup-checklist" in page
    assert "准备创建书籍" in page
    assert "本地数据库" in page
    assert "测试连接" not in page


def test_model_setup_page_associates_labels_with_inputs() -> None:
    page = render_model_setup_page(Path(".mynovel/dev.sqlite"), None)

    assert '<label for="llm_base_url">接口地址</label>' in page
    assert '<input id="llm_base_url" name="llm_base_url"' in page
    assert '<label for="llm_api_key">访问密钥</label>' in page
    assert '<input id="llm_api_key" name="llm_api_key"' in page


def test_new_book_page_keeps_idea_as_the_only_required_primary_input() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-test",
    )

    page = render_new_book_page(provider_config)

    assert "一句话写下这本书最想写什么" in page
    assert "可选补充" in page
    assert "系统将生成什么" in page
    assert 'name="idea"' in page
    assert '<textarea name="idea" placeholder="一个失意档案员重建禁书图书馆" required>' in page
    assert '<select name="genre">' in page
    assert '<select name="audience">' in page
    assert "交给 AI 判断" in page
    assert "玄幻升级" in page
    assert "男频网文读者" in page
    assert "目标总字数" in page
    assert "单章目标字数" in page
    assert 'name="target_word_count" type="number" value="120000"' in page
    assert 'name="chapter_word_count" type="number" value="2800"' in page
    assert "single-focus-form" in page
    assert "open-book-focus-panel" in page
    assert "optional-inputs" in page
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
        title="长夜图书馆",
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

    assert "还需要你决定什么" in page
    assert "你也可以补充其他修改意见，但不需要先处理 AI 已自动修复的问题。" in page
    assert "修改决定" in page
    assert "批准并写入可信设定" in page
    assert 'action="/repair-chapter"' in page
    assert 'name="reviewer_note"' in page
    assert "退回修改" not in page
    assert 'action="/request-revision"' not in page
    assert "导出正文" not in page

    chapter.status = ChapterStatus.ACCEPTED
    chapter.final_text = chapter.revised_text
    page = render_chapter_review(book, [chapter], chapter, canon)

    assert "导出正文" in page
    assert "/chapter/9/export" in page


def test_review_page_uses_result_first_status_strip() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
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
        state_delta={"changes": [{"type": "人物状态", "target": "莉拉", "change": "离村"}]},
    )

    page = render_chapter_review(book, [chapter], chapter, Canon(id=1, book_id=1, version=1, content={}))

    assert 'class="global-status-strip"' in page
    assert "先看结果摘要，再决定是否接受本章" in page
    assert "已完成正文生成、自检和高置信度修复" in page
    assert "回答剩余分歧，或直接接受这版正文" in page


def test_running_chapter_page_exposes_production_control_panels() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
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
            plan={"word_budget": 3200},
            context_package={"canon": "已收集", "characters": "6 人相关"},
            draft_text="罗斯沿着隐秘小径继续向前。",
            state_delta={"changes": []},
            word_count=1248,
            reviewer_note="AI 修复中：压缩到 3000 字左右，解决字数达成率问题",
        )
    ]

    page = render_chapter_review(
        book, chapters, chapters[0], Canon(id=1, book_id=1, version=1, content={})
    )

    assert "AI 正在根据修改意见修订" in page
    assert "本次意见：压缩到 3000 字左右，解决字数达成率问题" in page
    assert "立即刷新" in page
    assert "3,200" in page
    assert "自动刷新" in page
    assert "setTimeout(() => window.location.reload(), 3000)" in page
    assert "阶段完成后会自动刷新" in page
    assert "chapter-stage-chain" in page
    assert "chapter-result-grid" in page
    assert "上下文包" in page
    assert "本次后台任务" in page
    assert "本地模型" not in page
    assert "68%" not in page
    assert "今天 14:32" not in page
    assert "预计剩余" not in page


def test_running_chapter_page_keeps_full_current_candidate_text_visible() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )
    full_text = "第一段开头。" + "A" * 220 + "\n第二段结尾。"
    chapter = Chapter(
        id=1,
        book_id=1,
        number=1,
        title="召唤",
        status=ChapterStatus.RUNNING,
        plan={"word_budget": 3200},
        context_package={"canon": "已收集"},
        draft_text=full_text,
        word_count=len(full_text),
    )

    page = render_chapter_review(
        book,
        [chapter],
        chapter,
        Canon(id=1, book_id=1, version=1, content={}),
    )

    assert "running-chapter-text" in page
    assert "第一段开头。" in page
    assert "第二段结尾。" in page
    assert ("A" * 220) in page


def test_review_page_uses_ai_revision_request_instead_of_manual_edit() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
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

    assert "修改意见" in page
    assert "例如：压缩破庙环境描写" in page
    assert "手动修正文" not in page
    assert 'action="/edit-chapter-text"' not in page
    assert 'name="manual_text"' not in page
    assert "人工备注" not in page
    assert "重大变化" in page
    assert 'name="allow_major_changes"' in page
    assert "review-tabs" in page
    assert "状态变化待验证" in page
    assert "影响范围" in page


def test_needs_revision_chapter_page_exposes_ai_revision_request() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )
    chapter = Chapter(
        id=9,
        book_id=1,
        number=1,
        title="离开的召唤",
        status=ChapterStatus.NEEDS_REVISION,
        revised_text="莉拉离开村庄。",
        audit_report={
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "生成失败后需要修订", "resolved": False}],
        },
        state_delta={"changes": []},
    )
    canon = Canon(id=1, book_id=1, version=1, content={})

    page = render_chapter_review(book, [chapter], chapter, canon)

    assert "修改意见" in page
    assert "按意见让 AI 修订" in page
    assert 'action="/repair-chapter"' in page
    assert 'name="reviewer_note"' in page
    assert "批准并写入可信设定" not in page
    assert "先看结果摘要，再决定是否接受本章" not in page
    assert "回答剩余分歧，或直接接受这版正文" not in page
    assert "AI 没有留下高风险分歧；你可以直接接受正文，或补充风格性意见。" not in page
    assert "先看结果摘要，再决定如何修订本章" in page
    assert "提交修订决定，等待 AI 重新生成候选正文" in page
    assert "第 01 章当前候选仍需修订，等待你给出下一轮修改决定。" in page
    assert "当前不能直接接受正文；请把这一轮修订决定告诉 AI，生成新的候选后再进入批准判断。" in page


def test_book_workspace_links_to_trusted_state_page() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )

    page = render_book_workspace(book, [], Canon(id=1, book_id=1, version=1, content={}), [])

    assert "查看可信设定" in page
    assert "/book/1/state" in page
    assert 'href="/review"' in page
    assert "质量增强" in page
    assert "/book/1/quality" in page


def test_project_navigation_links_to_current_book_surfaces() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )

    page = render_book_workspace(book, [], Canon(id=1, book_id=1, version=1, content={}), [])

    assert '<a class="nav-item active" href="/book/1">' in page
    assert "<span>文档</span></a>" in page
    assert '<svg class="icon-svg" viewBox="0 0 24 24"' in page
    assert 'href="/book/1/state#characters"' in page
    assert 'href="/book/1/state#world"' in page
    assert 'href="/book/1/quality"' in page


def test_trusted_state_page_exposes_character_and_world_anchors() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )
    canon = Canon(
        id=1,
        book_id=1,
        version=1,
        content={
            "world_rules": [{"name": "雾墙规则", "detail": "幽谷边界危险。"}],
            "characters": [{"name": "罗斯", "detail": "石匠学徒。"}],
        },
    )

    page = render_trusted_state_page(book, canon, [])

    assert 'id="world"' in page
    assert 'id="characters"' in page


def test_book_workspace_exposes_whole_book_export_actions() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )

    page = render_book_workspace(book, [], Canon(id=1, book_id=1, version=1, content={}), [])

    assert "导出整本书" in page
    assert "/book/1/export.md" in page
    assert "/book/1/export.json" in page


def test_book_workspace_exposes_editable_word_targets() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
        constraints={"target_word_count": 300000, "chapter_word_count": 3200},
    )
    chapters = [
        Chapter(
            id=1,
            book_id=1,
            number=1,
            title="离开的召唤",
            status=ChapterStatus.AWAITING_REVIEW,
            plan={"word_budget": 2800},
        )
    ]

    page = render_book_workspace(book, chapters, Canon(id=1, book_id=1, version=1, content={}), [])

    assert "目标字数" in page
    assert 'action="/book-word-targets"' in page
    assert 'name="target_word_count" type="number" value="300000"' in page
    assert 'name="chapter_word_count" type="number" value="3200"' in page
    assert 'name="update_existing_chapters"' in page
    assert "同步更新已有章节计划" in page


def test_book_workspace_exposes_batch_chapter_production_action() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
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
    assert 'name="limit" type="number" min="1" max="10" value="2"' in page
    assert 'name="book_id" value="1"' in page


def test_project_surfaces_expose_ai_api_settings_entry() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )

    page = render_book_workspace(book, [], Canon(id=1, book_id=1, version=1, content={}), [])

    assert "/provider-config" in page
    assert "模型接口设置" in page
    assert "AI API 设置" not in page


def test_book_workspace_hides_batch_action_when_book_is_paused() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
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
        title="长夜图书馆",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
        constraints={"target_word_count": 300000},
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

    assert 'class="app-shell app-shell-compact"' in page
    assert 'class="nav-icon"' in page
    assert 'aria-hidden="true"' in page
    assert "项目概览" in page
    assert "300,000 字" in page
    assert "章节队列" in page


def test_application_shell_hides_status_strip_by_default() -> None:
    page = render_app_page(
        title="Status Strip Test",
        active="workspace",
        main="<section>Body</section>",
    )

    assert 'class="app-shell app-shell-compact"' in page
    assert 'class="global-status-strip"' not in page
    assert "你现在要做" not in page
    assert "AI 正在做" not in page
    assert "完成后你要决定" not in page


def test_home_page_opts_into_compact_global_status_strip_tokens() -> None:
    page = render_home(
        Path(".mynovel/dev.sqlite"),
        books=[],
        provider_config=None,
        blueprints=[],
        message=None,
    )

    assert 'class="app-shell app-shell-compact"' in page
    assert 'class="global-status-strip"' in page
    assert "你现在要做" in page
    assert "AI 正在做" in page
    assert "完成后你要决定" in page
    assert "--bg-canvas:" in page
    assert "--panel-elevated:" in page
    assert "--accent-strong:" in page


def test_application_shell_accepts_custom_status_strip_slot() -> None:
    page = render_app_page(
        title="Status Strip Test",
        active="workspace",
        main="<section>Body</section>",
        status_strip='<section class="custom-status-strip">Only this strip</section>',
    )

    assert 'class="custom-status-strip"' in page
    assert "Only this strip" in page
    assert 'class="global-status-strip"' not in page
    assert "你现在要做" not in page


def test_compact_shell_css_stacks_global_status_strip_on_mobile() -> None:
    css = app_css()

    assert ".global-status-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))" in css
    assert ".global-status-strip{grid-template-columns:minmax(0,1fr);padding:12px}" in css


def test_pipeline_renders_stateful_steps_with_icons_and_connectors() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
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
    assert "candidate-confirmation" in page
    assert "candidate-status-banner" in page
    assert "选择后怎么处理" in page
    assert "按备注修改" in page


def test_canon_gate_page_matches_lock_confirmation_surface() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="连载读者",
        status=BookStatus.DRAFT,
    )
    canon = Canon(
        id=1,
        book_id=1,
        version=1,
        content={
            "world_rules": [{"name": "魔法能量来源", "detail": "未限定边界"}],
            "characters": [
                {"name": "罗文", "detail": "少年石匠"},
                {"name": "莉拉", "detail": "符号学徒"},
                {"name": "伊芙", "detail": "旧石会信使"},
            ],
            "factions": [{"name": "旧石会", "detail": "守护遗迹"}],
            "locations": [
                {"name": "幽谷", "detail": "雾墙环绕"},
                {"name": "雾门", "detail": "旧王朝入口"},
            ],
            "relationships": [
                {"from": "罗文", "to": "莉拉", "detail": "同伴"},
                {"from": "罗文", "to": "旧石会", "detail": "被追踪"},
            ],
            "foreshadowing": ["黑石印记尚未回收", "雾门钥匙", "旧王朝病灶"],
            "chapter_summaries": [
                {"chapter": 1, "title": "召唤", "summary": "进入幽谷"},
                {"chapter": 2, "title": "雾门", "summary": "遭遇旧石会"},
                {"chapter": 3, "title": "印记", "summary": "发现病灶线索"},
            ],
        },
    )
    chapters = [
        Chapter(
            id=5,
            book_id=1,
            number=5,
            title="破碎之门",
            status=ChapterStatus.AWAITING_REVIEW,
            word_count=3098,
            audit_report={
                "risk_level": "medium",
                "issues": [{"severity": "medium", "title": "人物出身不完整"}],
            },
        )
    ]

    page = render_trusted_state_page(book, canon, chapters)

    assert "canon-gate-layout" in page
    assert "canon-summary-grid" in page
    assert "chapter-production-basis" in page
    assert "下一步：开始章节生产" in page
    assert "点击下一步后" in page
    assert "状态变化才会写入可信设定" in page
    assert "下一步" in page


def test_book_workspace_matches_project_cockpit_surface() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="男频网文读者",
        status=BookStatus.CANON_LOCKED,
    )
    chapters = [
        Chapter(id=1, book_id=1, number=1, title="召唤", status=ChapterStatus.PLANNED),
        Chapter(id=2, book_id=1, number=2, title="穿越迷雾", status=ChapterStatus.PLANNED),
    ]
    canon = Canon(
        id=1,
        book_id=1,
        version=1,
        content={
            "world_rules": [{"background": "架空大盛王朝", "rules": "医术被视为神迹"}],
            "characters": [{"name": "苏清月", "description": "现代中西医博士"}],
            "foreshadowing": [
                {
                    "trigger": "苏清月检查原主遗物",
                    "description": "发现原主并非死于意外。",
                }
            ],
            "chapter_summaries": [{"title": "第一章：魂穿将门", "content": "现代医生醒来后自救。"}],
            "state_history": [
                {
                    "type": "canon_proposal_revision",
                    "target_section": "locations",
                    "changed_sections": ["locations", "relationships"],
                    "blocked_sections": [{"section": "world_rules", "reason": "已锁定"}],
                    "instruction": "重要地点太少了。",
                    "summary": "已补全地点和关系。",
                }
            ],
        },
    )

    page = render_book_workspace(book, chapters, canon, [])

    assert "workspace-focus-layout" in page
    assert "workspace-focus-card" in page
    assert "workspace-result-sidebar" in page
    assert "当前任务" in page
    assert "推进第 01 章" in page
    assert "开始生产本章" in page
    assert "AI 最近进展" in page
    assert "可信设定摘要" in page
    assert "章节队列" in page
    assert "背景：架空大盛王朝" in page
    assert "说明：现代中西医博士" in page
    assert "苏清月检查原主遗物：发现原主并非死于意外。" in page
    assert "摘要：现代医生醒来后自救。" in page
    assert "background：" not in page
    assert "description：" not in page
    assert "trigger：" not in page
    assert "content：" not in page
    assert "target_section" not in page
    assert "changed_sections" not in page
    assert 'class="main-panel project-cockpit"' not in page
    assert "<span class='info-dot' aria-hidden='true'>i</span>" not in page


def test_book_workspace_renders_volume_plan_items_as_readable_text() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="男频网文读者",
        status=BookStatus.CANON_LOCKED,
    )
    volume_plan = VolumePlan(
        id=1,
        book_id=1,
        title="第一卷",
        core_conflict="主角重建禁书馆。",
        pacing_curve=[{"title": "死而复生", "goal": "完成自救。"}],
        commitments=["前三章完成自救"],
    )

    page = render_book_workspace(
        book,
        [],
        Canon(id=1, book_id=1, version=1, content={}),
        [],
        volume_plans=[volume_plan],
    )

    assert "标题：死而复生" in page
    assert "目标：完成自救。" in page
    assert "&#x27;title&#x27;" not in page
    assert "&#x27;goal&#x27;" not in page


def test_running_chapter_page_matches_stage_control_surface() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="男频网文读者",
        status=BookStatus.PRODUCING,
    )
    chapter = Chapter(
        id=1,
        book_id=1,
        number=1,
        title="召唤",
        status=ChapterStatus.RUNNING,
        plan={"word_budget": 3000},
        context_package={"canon": "雾门规则", "characters": ["罗文", "莉拉"]},
    )

    page = render_chapter_review(
        book,
        [chapter],
        chapter,
        Canon(id=1, book_id=1, version=1, content={}),
    )

    assert "chapter-production-layout" in page
    assert "chapter-task-board" in page
    assert "chapter-stage-chain" in page
    assert "chapter-result-grid" in page
    assert 'data-stage="plan"' in page
    assert 'data-stage="context"' in page
    assert 'data-stage="draft"' in page
    assert 'data-stage="delta"' in page
    assert 'data-stage="audit"' in page
    assert 'data-slot="plan"' in page
    assert 'data-slot="context"' in page
    assert 'data-slot="draft"' in page
    assert 'data-slot="delta"' in page
    assert 'data-slot="audit"' in page
    assert "章节规划" in page
    assert "上下文包" in page
    assert "草稿正文" in page
    assert "状态变化" in page
    assert "审计结果" in page
    assert "立即刷新" in page
    assert "正在生成草稿" in page
    assert "待产出" in page
    assert "已生成章节规划" in page
    assert "已编译上下文包" in page


def test_running_chapter_page_marks_empty_delta_and_audit_as_completed() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="男频网文读者",
        status=BookStatus.PRODUCING,
    )
    chapter = Chapter(
        id=1,
        book_id=1,
        number=1,
        title="召唤",
        status=ChapterStatus.RUNNING,
        draft_text="薄雾在峡谷间流动，像一层轻纱。",
        plan={"word_budget": 3000},
        context_package={"canon": "雾门规则"},
        state_delta={"changes": []},
        audit_report={"issues": []},
    )

    page = render_chapter_review(
        book,
        [chapter],
        chapter,
        Canon(id=1, book_id=1, version=1, content={}),
    )

    assert 'data-stage="delta"' in page
    assert 'data-stage="audit"' in page
    assert 'class="chapter-stage done" data-stage="delta"' in page
    assert 'class="chapter-stage done" data-stage="audit"' in page
    assert 'class="chapter-result-slot ready" data-slot="delta"' in page
    assert 'class="chapter-result-slot ready" data-slot="audit"' in page
    assert "无状态变化" in page
    assert "无审计问题" in page
    assert "状态变化待产出" not in page
    assert "审计结果待产出" not in page


def test_running_chapter_page_uses_translations_for_task_board_copy(monkeypatch) -> None:
    monkeypatch.setitem(TRANSLATIONS["zh-CN"], "running_board.refresh_now", "立即刷新_TEST")
    monkeypatch.setitem(TRANSLATIONS["zh-CN"], "running_board.word_stats", "字数面板_TEST：{current}/{target}")
    monkeypatch.setitem(TRANSLATIONS["zh-CN"], "running_board.auto_refreshing", "自动刷新_TEST")
    monkeypatch.setitem(TRANSLATIONS["zh-CN"], "running_board.none_delta", "无状态变化_TEST")
    monkeypatch.setitem(TRANSLATIONS["zh-CN"], "running_board.none_audit", "无审计问题_TEST")

    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="男频网文读者",
        status=BookStatus.PRODUCING,
    )
    chapter = Chapter(
        id=1,
        book_id=1,
        number=1,
        title="召唤",
        status=ChapterStatus.RUNNING,
        draft_text="薄雾在峡谷间流动，像一层轻纱。",
        word_count=1248,
        plan={"word_budget": 3000},
        context_package={"canon": "雾门规则"},
        state_delta={"changes": []},
        audit_report={"issues": []},
    )

    page = render_chapter_review(
        book,
        [chapter],
        chapter,
        Canon(id=1, book_id=1, version=1, content={}),
    )

    assert "立即刷新_TEST" in page
    assert "字数面板_TEST：1248/3,000" in page
    assert "自动刷新_TEST" in page
    assert "无状态变化_TEST" in page
    assert "无审计问题_TEST" in page


def test_running_chapter_page_uses_translations_for_mode_and_chapter_number(monkeypatch) -> None:
    locale = "test-locale"
    monkeypatch.setitem(TRANSLATIONS, locale, dict(TRANSLATIONS["zh-CN"]))
    monkeypatch.setitem(TRANSLATIONS[locale], "running_board.mode_generate", "AI 生成_TEST")
    monkeypatch.setitem(
        TRANSLATIONS[locale],
        "running_board.mode_generate_status",
        "阶段状态_TEST",
    )
    monkeypatch.setitem(TRANSLATIONS[locale], "chapter.number", "章节编号_TEST {number}")

    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="男频网文读者",
        status=BookStatus.PRODUCING,
    )
    chapter = Chapter(
        id=1,
        book_id=1,
        number=3,
        title="召唤",
        status=ChapterStatus.RUNNING,
        plan={"word_budget": 3000},
    )

    page = render_chapter_review(
        book,
        [chapter],
        chapter,
        Canon(id=1, book_id=1, version=1, content={}),
        locale=locale,
    )

    assert page.count("AI 生成_TEST") == 2
    assert page.count("阶段状态_TEST") == 2
    assert "章节编号_TEST 3 召唤" in page


def test_book_workspace_uses_translations_for_workspace_preview_labels(monkeypatch) -> None:
    locale = "workspace-test"
    monkeypatch.setitem(TRANSLATIONS, locale, dict(TRANSLATIONS["zh-CN"]))
    monkeypatch.setitem(TRANSLATIONS[locale], "workspace.current_task", "CURRENT_TASK_TEST")
    monkeypatch.setitem(TRANSLATIONS[locale], "workspace.focus_title_run", "RUN_TASK_TEST {number}")
    monkeypatch.setitem(TRANSLATIONS[locale], "workspace.focus_detail_run", "RUN_DETAIL_TEST")
    monkeypatch.setitem(TRANSLATIONS[locale], "workspace.book_meta", "{genre} / {audience}")
    monkeypatch.setitem(TRANSLATIONS[locale], "workspace.empty_value", "EMPTY_TEST")
    monkeypatch.setitem(TRANSLATIONS[locale], "workspace.preview_pair", "{left} => {right}")
    monkeypatch.setitem(TRANSLATIONS[locale], "workspace.preview_joiner", " | ")
    monkeypatch.setitem(TRANSLATIONS[locale], "workspace.label.background", "BG_TEST")
    monkeypatch.setitem(TRANSLATIONS[locale], "workspace.label.description", "DESC_TEST")
    monkeypatch.setitem(TRANSLATIONS[locale], "workspace.label.title", "TITLE_TEST")
    monkeypatch.setitem(TRANSLATIONS[locale], "workspace.label.goal", "GOAL_TEST")
    monkeypatch.setitem(TRANSLATIONS[locale], "word_targets.total_label", "TOTAL_WORDS_TEST")
    monkeypatch.setitem(TRANSLATIONS[locale], "word_targets.chapter_label", "CHAPTER_WORDS_TEST")
    monkeypatch.setitem(TRANSLATIONS[locale], "word_targets.update_existing", "SYNC_EXISTING_TEST")
    monkeypatch.setitem(TRANSLATIONS[locale], "word_targets.save", "SAVE_TARGETS_TEST")
    monkeypatch.setitem(TRANSLATIONS[locale], "workspace.trace_time_format", "{hour}h{minute}")

    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="男频网文读者",
        status=BookStatus.CANON_LOCKED,
        constraints={"target_word_count": 180000, "chapter_word_count": 3200},
    )
    chapters = [Chapter(id=1, book_id=1, number=1, title="召唤", status=ChapterStatus.PLANNED)]
    canon = Canon(
        id=1,
        book_id=1,
        version=1,
        content={
            "world_rules": [{"background": "架空大盛王朝", "description": "医术被视为神迹"}],
            "chapter_summaries": [{"title": "第一章", "goal": "完成自救"}],
        },
    )
    traces = [
        RunTrace(
            id=1,
            book_id=1,
            stage="chapter_pipeline",
            created_at=datetime(2026, 5, 15, 9, 7, tzinfo=UTC),
        )
    ]

    page = render_book_workspace(book, chapters, canon, traces, locale=locale)

    assert "CURRENT_TASK_TEST" in page
    assert page.count("RUN_TASK_TEST 1") == 2
    assert page.count("RUN_DETAIL_TEST") == 2
    assert "奇幻 / 男频网文读者" in page
    assert "BG_TEST => 架空大盛王朝" in page
    assert "DESC_TEST => 医术被视为神迹" in page
    assert "TITLE_TEST => 第一章" in page
    assert "GOAL_TEST => 完成自救" in page
    assert "TOTAL_WORDS_TEST" in page
    assert "CHAPTER_WORDS_TEST" in page
    assert "SYNC_EXISTING_TEST" in page
    assert "SAVE_TARGETS_TEST" in page
    assert "9h07" in page
    assert "09:07" not in page
    assert "背景：架空大盛王朝" not in page


def test_completed_book_workspace_matches_first_ten_complete_surface() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="男频网文读者",
        status=BookStatus.PRODUCING,
    )
    chapters = [
        Chapter(
            id=index,
            book_id=1,
            number=index,
            title=f"第 {index:02d} 章",
            status=ChapterStatus.ACCEPTED,
            final_text="已完成",
            word_count=3000,
        )
        for index in range(1, 11)
    ]

    page = render_book_workspace(book, chapters, Canon(id=1, book_id=1, version=10, content={}), [])

    assert "project-progress-overview" in page
    assert "可信设定更新总览" in page
    assert "已连续更新到 v10" in page
    assert "继续生产第 11 章" in page
    assert "导出已批准章节" in page
