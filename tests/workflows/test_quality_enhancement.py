from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, OpenBookBlueprint
from mynovel.domain.repositories import (
    list_deconstruction_studies_for_book,
    list_quality_snapshots_for_book,
    list_style_assets_for_book,
)
from mynovel.workflows.chapter_pipeline import approve_chapter, run_chapter_pipeline
from mynovel.workflows.open_book import create_draft_book_from_blueprint
from mynovel.workflows.quality_enhancement import (
    create_style_asset,
    deconstruct_reference_text,
    generate_quality_snapshot,
    recommend_cost_strategy,
)


def test_style_asset_and_deconstruction_study_are_persisted(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="幽谷回声")

        style = create_style_asset(
            session,
            book.id,
            name="雾谷悬疑节奏",
            reference_text="雾贴着石阶流动。莉拉停下脚步。远处有光，像旧王朝还没有死。",
            source_title="参考片段",
        )
        study = deconstruct_reference_text(
            session,
            book.id,
            source_title="参考章节",
            reference_text=(
                "莉拉离开村庄，掌心符号第一次发热。\n\n"
                "守夜人罗文在雾中出现，阻止她靠近遗迹。\n\n"
                "石门回应符号，旧王朝的名字重新浮现。"
            ),
        )
        styles = list_style_assets_for_book(session, book.id)
        studies = list_deconstruction_studies_for_book(session, book.id)

    assert style.name == "雾谷悬疑节奏"
    assert style.source_title == "参考片段"
    assert style.fingerprint["sentence_count"] == 3
    assert "短句" in style.guidance["sentence_profile"]
    assert study.source_title == "参考章节"
    assert len(study.beat_map) == 3
    assert study.craft_notes["opening_hook"].startswith("莉拉离开村庄")
    assert [item.name for item in styles] == ["雾谷悬疑节奏"]
    assert [item.source_title for item in studies] == ["参考章节"]


def test_quality_snapshot_and_cost_strategy_use_chapters_and_traces(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="幽谷回声")
        first = run_chapter_pipeline(session, _chapter_id(session, book.id, 1))
        approve_chapter(session, first.id)
        second = run_chapter_pipeline(session, _chapter_id(session, book.id, 2))
        second.audit_report = {
            "risk_level": "high",
            "issues": [{"severity": "high", "title": "设定冲突", "resolved": False}],
            "suggestions": ["需要人工处理"],
        }
        session.add(second)
        session.commit()

        snapshot = generate_quality_snapshot(session, book.id)
        strategy = recommend_cost_strategy(snapshot)
        snapshots = list_quality_snapshots_for_book(session, book.id)

    assert snapshot.metrics["accepted_chapters"] == 1
    assert snapshot.metrics["review_backlog"] == 1
    assert snapshot.metrics["high_risk_issues"] == 1
    assert snapshot.metrics["unresolved_issues"] == 2
    assert snapshot.metrics["estimated_chars"] > 0
    assert snapshot.score < 90
    assert strategy["mode"] == "quality"
    assert strategy["batch_limit"] == 1
    assert "高风险" in " ".join(snapshot.recommendations)
    assert snapshots[-1].id == snapshot.id


def _chapter_id(session: Session, book_id: int, number: int) -> int:
    from mynovel.domain.repositories import list_chapters_for_book

    chapter = [item for item in list_chapters_for_book(session, book_id) if item.number == number][
        0
    ]
    assert chapter.id is not None
    return chapter.id


def _blueprint() -> OpenBookBlueprint:
    return OpenBookBlueprint(
        id=1,
        idea="失忆少女在幽谷中寻找被抹去的王朝真相",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["幽谷回声"],
            "genre": "奇幻连载",
            "audience": "喜欢成长冒险的连载读者",
            "selling_points": ["每章揭开一条旧王朝线索"],
            "protagonist": {"name": "莉拉", "hook": "失忆但能读懂古代符号"},
            "world": {"premise": "幽谷里散落着被抹去王朝的遗迹"},
            "central_conflict": "莉拉必须确认自己与旧王朝覆灭之间的关系。",
            "reader_promises": ["持续发现遗迹"],
            "chapter_directions": [
                {"title": "离开的召唤", "goal": "发现第一枚符号"},
                {"title": "雾谷来信", "goal": "收到第二枚符号的线索"},
            ],
        },
        raw_response="{}",
    )
