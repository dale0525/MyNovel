from pathlib import Path

from mynovel.dev_server import _provider_config_from_form
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
    is_provider_config_complete,
    render_book_workspace,
    render_blueprint_page,
    render_chapter_review,
    render_model_setup_page,
    render_new_book_page,
)


def test_model_setup_allows_dedicated_embedding_and_rerank_config() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://llm.example.test/v1",
        llm_api_key="llm-key",
        llm_model="chat-model",
        embedding_use_llm_credentials=True,
        embedding_base_url="https://embedding.example.test/v1",
        embedding_api_key="embedding-key",
        embedding_model="embedding-model",
        rerank_use_llm_credentials=True,
        rerank_base_url="https://rerank.example.test/v1",
        rerank_api_key="rerank-key",
        rerank_model="rerank-model",
    )

    page = render_model_setup_page(Path(".mynovel/dev.sqlite"), provider_config)

    assert 'name="embedding_use_llm_credentials" type="checkbox" value="1" checked' in page
    assert 'name="embedding_base_url"' in page
    assert 'value="https://embedding.example.test/v1"' in page
    assert 'name="embedding_api_key"' in page
    assert 'value="embedding-key"' in page
    assert 'name="rerank_use_llm_credentials" type="checkbox" value="1" checked' in page
    assert 'name="rerank_base_url"' in page
    assert 'value="https://rerank.example.test/v1"' in page
    assert 'name="rerank_api_key"' in page
    assert 'value="rerank-key"' in page
    assert "检索模型接口" in page
    assert "重排模型接口" in page


def test_provider_config_form_defaults_retrieval_credentials_to_llm() -> None:
    config = _provider_config_from_form(
        {
            "llm_base_url": "https://llm.example.test/v1",
            "llm_api_key": "llm-key",
            "llm_model": "chat-model",
            "embedding_model": "embedding-model",
            "rerank_model": "rerank-model",
        }
    )

    assert config.embedding_use_llm_credentials is True
    assert config.rerank_use_llm_credentials is True
    assert config.resolved_embedding_base_url() == "https://llm.example.test/v1"
    assert config.resolved_rerank_base_url() == "https://llm.example.test/v1"


def test_provider_config_form_can_save_dedicated_retrieval_credentials() -> None:
    config = _provider_config_from_form(
        {
            "llm_base_url": "https://llm.example.test/v1",
            "llm_api_key": "llm-key",
            "llm_model": "chat-model",
            "embedding_use_llm_credentials": "0",
            "embedding_base_url": "https://embedding.example.test/v1",
            "embedding_api_key": "embedding-key",
            "embedding_model": "embedding-model",
            "rerank_use_llm_credentials": "0",
            "rerank_base_url": "https://rerank.example.test/v1",
            "rerank_api_key": "rerank-key",
            "rerank_model": "rerank-model",
        }
    )

    assert config.embedding_use_llm_credentials is False
    assert config.resolved_embedding_base_url() == "https://embedding.example.test/v1"
    assert config.resolved_embedding_api_key() == "embedding-key"
    assert config.rerank_use_llm_credentials is False
    assert config.resolved_rerank_base_url() == "https://rerank.example.test/v1"
    assert config.resolved_rerank_api_key() == "rerank-key"


def test_provider_config_is_incomplete_without_api_key_or_rerank_model() -> None:
    missing_key = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-test",
        rerank_use_llm_credentials=True,
        rerank_base_url="",
        rerank_model="rerank-test",
    )
    missing_rerank = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_api_key="sk-test",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-test",
        rerank_use_llm_credentials=True,
        rerank_base_url="",
        rerank_model="",
    )
    complete = ProviderConfig(
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

    assert is_provider_config_complete(missing_key) is False
    assert is_provider_config_complete(missing_rerank) is False
    assert is_provider_config_complete(complete) is True


def test_new_book_idea_field_is_multiline() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-test",
    )

    page = render_new_book_page(provider_config)

    assert '<textarea name="idea"' in page
    assert 'name="idea" type="text"' not in page
    assert "一句话写下这本书最想写什么" in page
    assert "可选补充" in page
    assert "系统将生成什么" in page


def test_new_book_flow_uses_explicit_action_and_result_copy() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="text-embedding-test",
    )

    page = render_new_book_page(provider_config)

    assert "点击“生成开书方案”后" in page
    assert "先生成几条可比较的开书方向，接着由你选定一个书名去生成可信设定定盘预览。" in page
    assert "锁定可信设定，再开始章节生产" in page
    assert "点击这个按钮后，系统会把开书方向整理成可挑选的方案页。" in page
    assert "提交后" not in page
    assert "确认进入生产" not in page
    assert "整理给你确认" not in page


def test_pending_blueprint_uses_configured_model_and_hides_unpriced_cost() -> None:
    provider_config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_model="gpt-live",
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

    assert "gpt-live" in page
    assert "Claude 3.5 Sonnet" not in page
    assert "预计消耗" not in page
    assert "¥" not in page


def test_blueprint_proposal_cards_are_clickable_and_drive_selected_detail() -> None:
    blueprint = _blueprint_with_distinct_candidates()

    page = render_blueprint_page(Path(".mynovel/dev.sqlite"), None, blueprint)

    assert 'id="blueprint-accept-form"' in page
    assert 'id="selected_title" name="selected_title" type="hidden" value="长夜图书馆"' in page
    assert (
        'role="button" tabindex="0" data-blueprint-choice="0" data-selected-title="长夜图书馆"'
        in page
    )
    assert (
        'role="button" tabindex="0" data-blueprint-choice="1" data-selected-title="禁书归途"'
        in page
    )
    assert (
        'role="button" tabindex="0" data-blueprint-choice="2" data-selected-title="群星档案"'
        in page
    )
    assert 'type="radio"' not in page
    assert "data-blueprint-detail-panel" in page
    assert 'data-blueprint-detail="1"' in page
    assert "地铁遗迹" in page
    assert "高冷封印师" in page
    assert "闻舟：高冷封印师" in page
    assert "废弃地铁站连接失落书城" in page
    assert '{"name":' not in page
    assert '{"premise":' not in page
    assert "selectBlueprintCandidate" in page


def test_blueprint_flow_uses_explicit_selection_and_foundation_actions() -> None:
    review_page = render_blueprint_page(
        Path(".mynovel/dev.sqlite"), None, _blueprint_with_distinct_candidates()
    )
    generating_page = render_blueprint_page(
        Path(".mynovel/dev.sqlite"),
        None,
        OpenBookBlueprint(
            id=9,
            idea="失意档案员重建禁书馆",
            version=1,
            status=BlueprintStatus.PENDING,
            instruction=None,
            content={},
            raw_response="",
        ),
    )

    assert "选定这个书名，生成可信设定定盘预览" in review_page
    assert "选定书名后才会生成可信设定定盘预览。" in review_page
    assert "下一步：选定一个书名，生成可信设定定盘预览。" in generating_page
    assert "确认方案，进入下一步" not in review_page
    assert "确认书名，进入下一步" not in review_page
    assert "选择书名并进入可信设定确认" not in generating_page


def test_blueprint_selection_script_initializes_after_selected_title_input() -> None:
    blueprint = _blueprint_with_distinct_candidates()

    page = render_blueprint_page(Path(".mynovel/dev.sqlite"), None, blueprint)

    assert page.index('id="selected_title"') < page.index("selectBlueprintCandidate")


def test_blueprint_action_area_groups_forms_under_the_section_heading() -> None:
    page = render_blueprint_page(
        Path(".mynovel/dev.sqlite"), None, _blueprint_with_distinct_candidates()
    )

    assert 'class="blueprint-action-grid"' in page
    assert 'class="compact-form candidate-confirmation blueprint-confirmation-form"' in page
    assert 'class="compact-form action-form blueprint-revision-form"' in page


def test_product_surfaces_use_chinese_terms_for_trusted_state_and_traces() -> None:
    review_page = render_blueprint_page(
        Path(".mynovel/dev.sqlite"), None, _blueprint_with_three_titles()
    )
    generating_page = render_blueprint_page(
        Path(".mynovel/dev.sqlite"),
        None,
        OpenBookBlueprint(
            id=2,
            idea="失意档案员重建禁书馆",
            version=1,
            status=BlueprintStatus.PENDING,
            instruction=None,
            content={},
            raw_response="",
        ),
    )

    assert "尚未写入可信设定" in review_page
    assert "尚未写入 Canon" not in review_page
    assert "运行记录" in generating_page
    assert "RunTrace" not in generating_page
    assert "可信设定定盘" in review_page
    assert "Canon 定盘" not in review_page


def test_chapter_and_completion_surfaces_do_not_show_hardcoded_prices() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="男频网文读者",
        status=BookStatus.PRODUCING,
    )
    running_chapter = Chapter(
        id=1,
        book_id=1,
        number=1,
        title="召唤",
        status=ChapterStatus.RUNNING,
        draft_text="薄雾在峡谷间流动。",
        word_count=1248,
        plan={"word_budget": 3000},
    )
    accepted_chapters = [
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

    running_page = render_chapter_review(
        book,
        [running_chapter],
        running_chapter,
        Canon(id=1, book_id=1, version=1, content={}),
    )
    completed_page = render_book_workspace(
        book,
        accepted_chapters,
        Canon(id=1, book_id=1, version=10, content={}),
        [],
    )

    assert "¥" not in running_page
    assert "¥" not in completed_page
    assert "累计成本" not in completed_page


def test_review_primary_actions_use_explicit_verbs() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="男频网文读者",
        status=BookStatus.PRODUCING,
    )
    chapter = Chapter(
        id=7,
        book_id=1,
        number=7,
        title="灰塔复燃",
        status=ChapterStatus.AWAITING_REVIEW,
        draft_text="灰塔在风雪中重新亮起。",
        revised_text="灰塔在风雪中重新亮起，巡夜人决定冒险登塔。",
        summary="主角确认灰塔复燃，并决定进塔调查。",
        word_count=3120,
    )

    page = render_chapter_review(book, [chapter], chapter, Canon(id=1, book_id=1, version=3, content={}))

    assert "批准并写入可信设定" in page
    assert "让 AI 按这轮决定重新修订本章" in page
    assert "提交修改决定，按意见让 AI 修订" not in page


def test_needs_revision_review_flow_uses_revision_only_result_first_wording() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="男频网文读者",
        status=BookStatus.PRODUCING,
    )
    chapter = Chapter(
        id=8,
        book_id=1,
        number=8,
        title="旧塔回声",
        status=ChapterStatus.NEEDS_REVISION,
        revised_text="旧塔深处传来回声。",
        summary="第 08 章当前候选仍需修订，等待你给出下一轮修改决定。",
        audit_report={"risk_level": "medium", "issues": []},
        state_delta={"changes": []},
        word_count=2980,
    )

    page = render_chapter_review(book, [chapter], chapter, Canon(id=1, book_id=1, version=5, content={}))

    assert "先看结果摘要，再决定如何修订本章" in page
    assert "写下修订决定，让 AI 重新生成候选正文" in page
    assert "当前不能直接接受正文，请先写下修订决定，让 AI 重新生成候选正文。" in page
    assert (
        "当前不能直接接受正文；请把这一轮修订决定告诉 AI，让它重新生成候选正文，下一轮再进入批准判断。"
        in page
    )
    assert "先看结果摘要，再决定是否接受本章" not in page
    assert "批准并写入可信设定" not in page


def test_running_waiting_copy_explains_current_work_and_next_decision() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="男频网文读者",
        status=BookStatus.PRODUCING,
    )
    chapter = Chapter(
        id=3,
        book_id=1,
        number=3,
        title="塔底回声",
        status=ChapterStatus.RUNNING,
        plan={"goal": "确认塔底异响来源"},
        context_package={"characters": ["林烬"], "summary": "上一章进入灰塔"},
        word_count=0,
    )

    page = render_chapter_review(book, [chapter], chapter, Canon(id=1, book_id=1, version=2, content={}))

    assert "AI 正在生成草稿正文；完成后会继续提取状态变化。" in page
    assert "AI 正在提取本章状态变化；完成后你就能核对是否写入可信设定。" in page
    assert "等待审计结果出来后，再决定是继续修订还是批准写入可信设定。" in page
    assert ">正在生成草稿<" not in page
    assert "等待本章产出后进入人工审核。" not in page


def test_shell_css_uses_auto_fit_for_status_and_review_summary_layouts() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="男频网文读者",
        status=BookStatus.PRODUCING,
    )
    chapter = Chapter(
        id=5,
        book_id=1,
        number=5,
        title="雨夜誓约",
        status=ChapterStatus.AWAITING_REVIEW,
        draft_text="雨夜里，誓约被重新说出。",
        revised_text="雨夜里，誓约被重新说出，旧约也因此改写。",
        summary="主角在雨夜重申誓约并触发旧约回响。",
        word_count=3050,
    )

    page = render_chapter_review(book, [chapter], chapter, Canon(id=1, book_id=1, version=4, content={}))

    assert "grid-template-columns:repeat(auto-fit,minmax(240px,1fr))" in page
    assert "grid-template-columns:repeat(auto-fit,minmax(220px,1fr))" in page


def _blueprint_with_three_titles() -> OpenBookBlueprint:
    return OpenBookBlueprint(
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


def _blueprint_with_distinct_candidates() -> OpenBookBlueprint:
    return OpenBookBlueprint(
        id=1,
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜图书馆", "禁书归途", "群星档案"],
            "genre": "玄幻",
            "audience": "男频网文读者",
            "selling_points": ["禁书体系"],
            "protagonist": {"name": "林烬", "hook": "失意档案员"},
            "world": {"premise": "书籍可以封印神明"},
            "central_conflict": "主角重建禁书馆",
            "reader_promises": ["每章有新禁书"],
            "chapter_directions": [{"chapter": "第 1 章", "direction": "得到残页"}],
            "candidates": [
                {
                    "title": "长夜图书馆",
                    "selling_points": ["禁书体系", "馆藏升级"],
                    "protagonist": {"name": "林烬", "hook": "失意档案员"},
                    "world": {"premise": "书籍可以封印神明"},
                    "central_conflict": "重建禁书馆",
                    "reader_promises": ["每章有新禁书"],
                    "chapter_directions": [{"chapter": "第 1 章", "direction": "得到残页"}],
                },
                {
                    "title": "禁书归途",
                    "selling_points": ["地铁遗迹", "逃亡解谜"],
                    "protagonist": {"name": "闻舟", "hook": "高冷封印师"},
                    "world": {"premise": "废弃地铁站连接失落书城"},
                    "central_conflict": "带着禁书穿越封锁线",
                    "reader_promises": ["每站解锁一段旧史"],
                    "chapter_directions": [{"chapter": "第 1 章", "direction": "逃入旧站台"}],
                },
                {
                    "title": "群星档案",
                    "selling_points": ["星际档案", "群像追谜"],
                    "protagonist": {"name": "许澜", "hook": "星图修复师"},
                    "world": {"premise": "档案馆漂浮在群星轨道"},
                    "central_conflict": "修复被抹除的文明档案",
                    "reader_promises": ["每卷揭开一颗星球的真相"],
                    "chapter_directions": [{"chapter": "第 1 章", "direction": "修复第一份星图"}],
                },
            ],
        },
        raw_response="{}",
    )
