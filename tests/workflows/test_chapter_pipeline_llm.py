import pytest
from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, OpenBookBlueprint
from mynovel.domain.repositories import get_latest_canon, list_run_traces_for_book
from mynovel.workflows.chapter_pipeline import (
    ReviewGateError,
    approve_chapter,
    apply_manual_chapter_edit,
    export_chapter_text,
    repair_chapter_with_ai,
    return_chapter_for_revision,
    run_chapter_pipeline,
)
from mynovel.workflows.open_book import create_draft_book_from_blueprint


class FakeChapterModel:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete(self, stage: str, messages, response_format: str) -> str:
        self.calls.append(stage)
        match stage:
            case "plan":
                return """
                {
                  "goal": "让莉拉发现第一枚旧王朝符号",
                  "must_write": ["离开村庄", "符号发热"],
                  "forbidden_drift": ["不能确认莉拉真实身份"],
                  "word_budget": 2800,
                  "ending_hook": "第二枚符号在远处回应"
                }
                """
            case "draft":
                return "莉拉离开村庄，雾气在谷口低伏。她掌心的符号忽然发热。"
            case "extract_state":
                return """
                {
                  "chapter": 1,
                  "changes": [
                    {
                      "type": "人物状态",
                      "target": "莉拉",
                      "change": "主动离开村庄追查真相",
                      "risk": "low"
                    }
                  ]
                }
                """
            case "audit":
                return """
                {
                  "risk_level": "medium",
                  "issues": [
                    {
                      "severity": "medium",
                      "title": "结尾钩子还不够强",
                      "resolved": false
                    }
                  ],
                  "suggestions": ["补强符号回应"]
                }
                """
            case "revise":
                return "莉拉离开村庄，雾气在谷口低伏。她掌心的符号忽然发热，远处也亮起同样的微光。"
        raise AssertionError(stage)


def test_run_chapter_pipeline_uses_model_client_for_each_generation_stage(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = FakeChapterModel()

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)

        reviewed = run_chapter_pipeline(
            session,
            chapter.id,
            model_client=model,
            model_name="章节模型",
        )
        traces = list_run_traces_for_book(session, book.id)

    assert model.calls == ["plan", "draft", "extract_state", "audit", "revise"]
    assert reviewed.plan["word_budget"] == 2800
    assert reviewed.draft_text.startswith("莉拉离开村庄")
    assert reviewed.state_delta["changes"][0]["target"] == "莉拉"
    assert reviewed.audit_report["risk_level"] == "medium"
    assert reviewed.revised_text.endswith("远处也亮起同样的微光。")
    assert [trace.stage for trace in traces] == [
        "规划本章",
        "编译上下文",
        "生成草稿",
        "提取状态变化",
        "审计",
        "修订",
    ]
    assert [trace.prompt_id for trace in traces] == [
        "chapter_plan",
        "chapter_context",
        "chapter_draft",
        "chapter_state_extract",
        "chapter_audit",
        "chapter_revise",
    ]
    assert {trace.prompt_version for trace in traces} == {"0.1.0"}
    assert {trace.model for trace in traces} == {"章节模型"}
    assert traces[0].cost["prompt_chars"] > 0
    assert traces[0].cost["completion_chars"] > 0
    assert traces[0].cost["elapsed_ms"] >= 0
    assert traces[0].metadata_["prompt_source"] == "original"


def test_approve_chapter_blocks_high_risk_unresolved_issues(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.audit_report = {
            "risk_level": "high",
            "issues": [{"severity": "high", "title": "设定冲突", "resolved": False}],
            "suggestions": ["必须重写冲突段落"],
        }
        session.add(reviewed)
        session.commit()

        with pytest.raises(ReviewGateError, match="高风险"):
            approve_chapter(session, reviewed.id)


def test_export_chapter_text_returns_only_accepted_final_text(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)

        accepted = approve_chapter(session, reviewed.id)

    assert export_chapter_text(accepted) == accepted.final_text


def test_manual_chapter_edit_replaces_review_candidate_without_updating_trusted_state(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)

        edited = apply_manual_chapter_edit(
            session,
            reviewed.id,
            "莉拉握紧发热的符号，主动踏入雾谷深处。",
            "补强主动性。",
        )
        edited_status = edited.status.value
        edited_text = edited.revised_text
        edited_word_count = edited.word_count
        edited_note = edited.reviewer_note
        canon_before_approval = get_latest_canon(session, book.id)
        canon_before_version = canon_before_approval.version if canon_before_approval else 0
        traces = list_run_traces_for_book(session, book.id)
        latest_trace_stage = traces[-1].stage
        accepted = approve_chapter(session, edited.id)
        canon_after_approval = get_latest_canon(session, book.id)
        canon_after_version = canon_after_approval.version if canon_after_approval else 0

    assert edited_status == "awaiting_review"
    assert edited_text == "莉拉握紧发热的符号，主动踏入雾谷深处。"
    assert edited_word_count == len("莉拉握紧发热的符号，主动踏入雾谷深处。")
    assert edited_note == "补强主动性。"
    assert canon_before_version == 1
    assert latest_trace_stage == "人工修正"
    assert accepted.final_text == "莉拉握紧发热的符号，主动踏入雾谷深处。"
    assert canon_after_version == 2


def test_approve_chapter_requires_explicit_major_change_confirmation(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.audit_report = {"risk_level": "low", "issues": [], "suggestions": []}
        reviewed.state_delta = {
            "chapter": 1,
            "changes": [
                {
                    "type": "角色死亡",
                    "target": "罗文",
                    "change": "罗文为保护莉拉牺牲",
                    "impact": "major",
                }
            ],
        }
        session.add(reviewed)
        session.commit()

        with pytest.raises(ReviewGateError, match="重大变化"):
            approve_chapter(session, reviewed.id)

        accepted = approve_chapter(session, reviewed.id, allow_major_changes=True)

    assert accepted.status.value == "accepted"


def test_return_chapter_for_revision_does_not_update_trusted_state(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)

        returned = return_chapter_for_revision(session, reviewed.id, "人物动机还不够清楚。")
        canon = get_latest_canon(session, book.id)
        traces = list_run_traces_for_book(session, book.id)

    assert returned.status.value == "needs_revision"
    assert returned.reviewer_note == "人物动机还不够清楚。"
    assert canon is not None
    assert canon.version == 1
    assert traces[-1].stage == "退回修订"


def test_repair_chapter_with_ai_revises_text_and_reopens_review(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = FakeRepairModel()

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "结尾钩子弱", "resolved": False}],
            "suggestions": ["补强符号回应"],
        }
        session.add(reviewed)
        session.commit()

        repaired = repair_chapter_with_ai(
            session,
            reviewed.id,
            model_client=model,
            model_name="章节模型",
            reviewer_note="保留离村动作，补强结尾。",
        )
        traces = list_run_traces_for_book(session, book.id)

    assert model.calls == ["revise"]
    assert repaired.status.value == "awaiting_review"
    assert repaired.revised_text == "莉拉保留离村动作，结尾处第二枚符号在雾中回应。"
    assert repaired.reviewer_note == "保留离村动作，补强结尾。"
    assert traces[-1].stage == "修复问题"
    assert traces[-1].model == "章节模型"


def test_run_chapter_pipeline_records_failure_and_leaves_chapter_retryable(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = FakeFailingChapterModel()

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)

        failed = run_chapter_pipeline(
            session,
            chapter.id,
            model_client=model,
            model_name="章节模型",
        )
        traces = list_run_traces_for_book(session, book.id)

    assert failed.status.value == "needs_revision"
    assert failed.reviewer_note == "生成失败：模型审计失败"
    assert traces[-1].stage == "生产失败"
    assert traces[-1].model == "章节模型"
    assert traces[-1].metadata_["failed_stage"] == "audit"
    assert traces[-1].metadata_["retryable"] is True


class FakeRepairModel:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete(self, stage: str, messages, response_format: str) -> str:
        self.calls.append(stage)
        assert response_format == "text"
        return "莉拉保留离村动作，结尾处第二枚符号在雾中回应。"


class FakeFailingChapterModel(FakeChapterModel):
    def complete(self, stage: str, messages, response_format: str) -> str:
        if stage == "audit":
            raise RuntimeError("模型审计失败")
        return super().complete(stage, messages, response_format)


def book_chapter(session: Session, book_id: int, number: int):
    from mynovel.domain.repositories import list_chapters_for_book

    return [
        chapter for chapter in list_chapters_for_book(session, book_id) if chapter.number == number
    ][0]


def _blueprint() -> OpenBookBlueprint:
    return OpenBookBlueprint(
        id=1,
        idea="失忆少女在幽谷中寻找被抹去的王朝真相",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜图书馆"],
            "genre": "奇幻连载",
            "audience": "喜欢成长冒险的连载读者",
            "selling_points": ["每章揭开一条旧王朝线索"],
            "protagonist": {"name": "莉拉", "hook": "失忆但能读懂古代符号"},
            "world": {"premise": "幽谷里散落着被抹去王朝的遗迹"},
            "central_conflict": "莉拉必须确认自己与旧王朝覆灭之间的关系。",
            "reader_promises": ["持续发现遗迹"],
            "chapter_directions": [{"title": "离开的召唤", "goal": "发现第一枚符号"}],
        },
        raw_response="{}",
    )
