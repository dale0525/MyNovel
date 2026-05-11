from mynovel.domain.models import Book, BookStatus, DeconstructionStudy, QualitySnapshot, StyleAsset
from mynovel.quality_views import render_quality_center


def test_quality_center_renders_v3_assets_analysis_and_cost_strategy() -> None:
    book = Book(
        id=1,
        title="幽谷回声",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )
    style = StyleAsset(
        id=2,
        book_id=1,
        name="雾谷悬疑节奏",
        source_excerpt="雾贴着石阶流动。",
        fingerprint={"average_sentence_chars": 14.2},
        guidance={"style_rules": ["保持短句推进。"]},
    )
    study = DeconstructionStudy(
        id=3,
        book_id=1,
        source_title="参考章节",
        source_excerpt="莉拉离开村庄。",
        beat_map=[{"beat": "开局钩子", "summary": "莉拉离开村庄。"}],
        craft_notes={"reusable_moves": ["先给人物动作，再揭示异常信号。"]},
    )
    snapshot = QualitySnapshot(
        id=4,
        book_id=1,
        score=73.0,
        metrics={"accepted_chapters": 3, "high_risk_issues": 1, "estimated_chars": 12000},
        recommendations=["存在高风险问题，先处理人工审核再继续批量生产。"],
    )

    page = render_quality_center(
        book,
        style_assets=[style],
        studies=[study],
        latest_snapshot=snapshot,
        cost_strategy={
            "mode": "quality",
            "batch_limit": 1,
            "context_policy": "保留完整可信上下文。",
        },
    )

    assert "质量增强" in page
    assert "风格资产" in page
    assert "拆书学习" in page
    assert "长期质量分析" in page
    assert "成本策略" in page
    assert "雾谷悬疑节奏" in page
    assert "参考章节" in page
    assert "73.0" in page
    assert 'action="/style-asset"' in page
    assert 'action="/deconstruct-reference"' in page
    assert 'action="/quality-snapshot"' in page


def test_quality_center_uses_the_main_application_shell() -> None:
    book = Book(
        id=1,
        title="幽谷回声",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )

    page = render_quality_center(
        book,
        style_assets=[],
        studies=[],
        latest_snapshot=None,
        cost_strategy=None,
    )

    assert 'class="app-shell"' in page
    assert "工作台" in page
    assert "章节队列" in page
    assert "返回项目" in page
