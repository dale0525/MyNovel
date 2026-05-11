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
