from mynovel.domain.models import Book, BookStatus, Canon, Chapter, ChapterStatus, RunTrace
from mynovel.product_views import render_chapter_review


def test_review_page_matches_human_review_surface() -> None:
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
        title="破碎之门",
        status=ChapterStatus.AWAITING_REVIEW,
        revised_text="冰冷的空气从门缝中渗出。",
        word_count=3214,
        audit_report={
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "符号含义未确认", "resolved": False}],
        },
        state_delta={"changes": [{"type": "人物状态", "target": "莉拉", "change": "体温消耗"}]},
    )

    page = render_chapter_review(
        book,
        [chapter],
        chapter,
        Canon(id=1, book_id=1, version=4, content={}),
    )

    assert "human-review-layout" in page
    assert "修改意见" in page
    assert "按意见让 AI 修订" in page
    assert "审计备注" not in page
    assert "状态变化待验证" in page
    assert "review-decision-panel" in page
    assert "批准并写入可信设定" in page
    assert '<button type="button" class="review-tab-button active" data-review-tab="audit"' in page
    assert 'data-review-panel="audit"' in page
    assert 'data-review-panel="state"' in page
    assert 'data-review-panel="revision"' in page
    assert 'data-review-panel="impact"' in page


def test_review_page_exposes_latest_repair_trace_diagnostics() -> None:
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
        title="破碎之门",
        status=ChapterStatus.AWAITING_REVIEW,
        plan={"word_budget": 3000},
        draft_text="草稿正文",
        revised_text="寒" * 4320,
        word_count=4320,
        audit_report={
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "字数不在目标区间", "resolved": False}],
        },
        state_delta={"changes": []},
    )
    trace = RunTrace(
        book_id=1,
        stage="修复问题",
        prompt_id="chapter_repair",
        model="章节模型",
        cost={"prompt_chars": 2048, "completion_chars": 4320, "elapsed_ms": 0},
        metadata_={
            "chapter": 5,
            "before_word_count": 2800,
            "after_word_count": 4320,
            "target_word_count": 3000,
            "word_count_window": [2700, 3450],
            "reviewer_note": "压缩到 3000 字左右。",
            "prompt_messages": [
                {"role": "system", "content": "你是连载章节修复器。"},
                {"role": "user", "content": "当前正文已经超出目标，请以删减和合并为主。"},
            ],
            "raw_response_text": '{"operations":[]}',
            "response_text": '{"operations":[]}',
            "applied_text": "修复后的正文",
        },
    )

    page = render_chapter_review(
        book,
        [chapter],
        chapter,
        Canon(id=1, book_id=1, version=4, content={}),
        traces=[trace],
    )

    assert "目标区间 2,700-3,450 字" in page
    assert "当前偏长" in page
    assert "AI 修复记录" in page
    assert "章节模型" in page
    assert "2,800 → 4,320" in page
    assert "提示词 2048 字符" in page
    assert "模型返回 4320 字符" in page
    assert "压缩到 3000 字左右" in page
    assert "当前正文已经超出目标" in page
    assert "查看模型原始返回" in page
    assert "查看应用后正文" in page
    assert "{&quot;operations&quot;:[]}" in page
    assert "修复后的正文" in page
    assert "RunTrace" not in page


def test_review_page_labels_legacy_patch_trace_without_raw_response_as_applied_text() -> None:
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
        title="破碎之门",
        status=ChapterStatus.AWAITING_REVIEW,
        plan={"word_budget": 3000},
        revised_text="寒" * 3200,
        word_count=3200,
        audit_report={"risk_level": "medium", "issues": []},
        state_delta={"changes": []},
    )
    trace = RunTrace(
        book_id=1,
        stage="修复问题",
        prompt_id="chapter_word_count_patch",
        model="章节模型",
        cost={"prompt_chars": 2048, "completion_chars": 3200},
        metadata_={
            "chapter": 5,
            "before_word_count": 4200,
            "after_word_count": 3200,
            "word_count_repair_mode": "compress",
            "patch_operations": [{"op": "compress", "paragraph_id": 1}],
            "response_text": "旧版记录中的应用后正文",
        },
    )

    page = render_chapter_review(
        book,
        [chapter],
        chapter,
        Canon(id=1, book_id=1, version=4, content={}),
        traces=[trace],
    )

    assert "查看旧版应用后正文" in page
    assert "旧版记录中的应用后正文" in page
    assert "查看模型原始返回" not in page


def test_review_page_overrides_stale_word_count_audit_direction() -> None:
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
        title="破碎之门",
        status=ChapterStatus.AWAITING_REVIEW,
        plan={"word_budget": 3000},
        revised_text="寒" * 4254,
        word_count=4254,
        audit_report={
            "risk_level": "low",
            "issues": [
                {
                    "severity": "medium",
                    "title": "字数达成度偏低",
                    "detail": "当前正文字数约 1500 字，距离 3000 字目标有较大缺口。",
                    "resolved": False,
                }
            ],
            "suggestions": ["扩写到目标字数。"],
        },
        state_delta={"changes": []},
    )

    page = render_chapter_review(
        book,
        [chapter],
        chapter,
        Canon(id=1, book_id=1, version=4, content={}),
    )

    assert "字数不在目标区间" in page
    assert "当前偏长" in page
    assert "1500 字" not in page
    assert "扩写到目标字数" not in page


def test_review_page_hides_low_information_state_delta_items() -> None:
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
        title="破碎之门",
        status=ChapterStatus.AWAITING_REVIEW,
        revised_text="冰冷的空气从门缝中渗出。",
        word_count=3214,
        audit_report={"risk_level": "low", "issues": []},
        state_delta={
            "chapter": 5,
            "changes": [
                {"type": "状态变化", "target": "待确认", "change": "characters"},
                {"type": "状态变化", "target": "待确认", "change": "relations"},
                {"type": "状态变化", "target": "待确认", "change": "locations"},
            ],
        },
    )

    page = render_chapter_review(
        book,
        [chapter],
        chapter,
        Canon(id=1, book_id=1, version=4, content={}),
    )

    assert "AI 未提取到可写入的明确状态变化" in page
    assert ">characters<" not in page
    assert ">relations<" not in page
    assert ">locations<" not in page


def test_review_page_prefers_revised_text_over_stale_final_text() -> None:
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
        title="破碎之门",
        status=ChapterStatus.AWAITING_REVIEW,
        revised_text="这是当前待审核正文。",
        final_text="这是旧的已批准正文。",
    )

    page = render_chapter_review(
        book,
        [chapter],
        chapter,
        Canon(id=1, book_id=1, version=4, content={}),
    )

    assert "这是当前待审核正文。" in page
    assert "这是旧的已批准正文。" not in page
