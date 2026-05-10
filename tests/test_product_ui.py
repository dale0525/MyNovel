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
from mynovel.product_views import render_chapter_review


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
