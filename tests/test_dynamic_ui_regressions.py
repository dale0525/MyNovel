from pathlib import Path

from mynovel.blueprint_review_views import render_blueprint_review
from mynovel.canon_proposal_views import render_canon_proposal_surface
from mynovel.domain.models import Book, Canon, OpenBookBlueprint
from mynovel.product_views import render_model_setup_page
from mynovel.ui_shell import app_css


def test_model_setup_does_not_label_required_embedding_model_as_optional() -> None:
    page = render_model_setup_page(Path(".mynovel/dev.sqlite"), None)

    assert "检索模型（可选）" not in page
    assert '<label for="embedding_model">检索模型</label>' in page
    assert 'id="embedding_model" name="embedding_model"' in page
    assert 'id="embedding_model" name="embedding_model" type="text"' in page
    assert 'name="embedding_model" type="text" value="" placeholder="bge-m3" required' in page
    assert "配置检索模型" in page
    assert "（可选）配置检索模型" not in page


def test_model_setup_does_not_label_required_rerank_model_as_optional() -> None:
    page = render_model_setup_page(Path(".mynovel/dev.sqlite"), None)

    assert "重排模型（可选）" not in page
    assert '<label for="rerank_model">重排模型</label>' in page
    assert 'id="rerank_model" name="rerank_model"' in page
    assert 'id="rerank_model" name="rerank_model" type="text"' in page
    assert (
        'name="rerank_model" type="text" value="" placeholder="bge-reranker-v2-m3" '
        "required"
    ) in page
    assert "配置重排模型" in page
    assert "（可选）配置重排模型" not in page


def test_blueprint_cards_distinguish_selected_candidate_from_other_candidates() -> None:
    blueprint = OpenBookBlueprint(
        id=1,
        idea="修复禁书图书馆",
        content={
            "title_options": ["记忆修补师", "失落卫星", "禁书目录"],
            "protagonist": {"name": "苏格", "identity": "档案修复师"},
            "world": {"name": "虚空卫星", "rules": "记忆会改写现实"},
            "central_conflict": "修复禁书会失去妹妹记忆",
            "selling_points": ["记忆代价", "禁书修复"],
        },
    )

    page = render_blueprint_review(blueprint, blueprint.content, "zh_CN")

    assert "data-candidate-state>已选中</span>" in page
    assert page.count("data-candidate-state>候选</span>") == 2
    assert "候选中" not in page


def test_canon_completion_instruction_names_all_missing_requirements() -> None:
    book = Book(id=1, title="记忆修补师", genre="奇幻", audience="网文读者")
    canon = Canon(
        book_id=1,
        version=1,
        content={
            "world_rules": [{"name": "记忆修补术"}],
            "characters": [{"name": "苏格"}],
            "factions": [],
            "locations": [],
            "relationships": [],
            "foreshadowing": [],
            "chapter_summaries": [],
        },
    )

    page = render_canon_proposal_surface(book, canon, locked=False)

    assert "当前未达标要求" in page
    assert "请一次性补齐所有未达标且未锁定分区" in page
    assert "人物至少 3 条" in page
    assert "伏笔账本至少 3 条" in page


def test_pipeline_uses_compact_footer_height() -> None:
    css = app_css()

    assert ".pipeline{flex:0 0 108px" in css
    assert "min-height:108px" in css
    assert ".pipeline-track{grid-column:1 / -1" in css
    assert "min-width:max-content" not in css


def test_current_run_sidebar_keeps_labels_horizontal() -> None:
    css = app_css()

    assert ".current-run dl{grid-template-columns:86px minmax(0,1fr)" in css
    assert ".current-run dd{min-width:0;overflow-wrap:anywhere}" in css


def test_vertical_flow_copy_stays_in_text_column() -> None:
    css = app_css()

    assert ".vertical-flow span{grid-column:2;color:var(--muted)}" in css
