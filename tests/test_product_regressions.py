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
    render_book_workspace,
    render_blueprint_page,
    render_chapter_review,
    render_model_setup_page,
    render_new_book_page,
)


def test_model_setup_advanced_options_allow_dedicated_embedding_and_rerank_config() -> None:
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

    assert '<details class="advanced-model-options">' in page
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
    assert "高级配置" in page


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
