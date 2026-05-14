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
        self.messages_by_stage: dict[str, list[dict[str, str]]] = {}

    def complete(self, stage: str, messages, response_format: str) -> str:
        self.calls.append(stage)
        self.messages_by_stage[stage] = messages
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


def test_run_chapter_pipeline_prompts_use_readable_inputs_not_raw_internal_json(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = FakeChapterModel()

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)

        run_chapter_pipeline(
            session,
            chapter.id,
            model_client=model,
            model_name="章节模型",
        )

    prompts = {
        stage: "\n".join(message["content"] for message in messages)
        for stage, messages in model.messages_by_stage.items()
    }

    assert "作品：长夜图书馆" in prompts["plan"]
    assert "本章：第 01 章《离开的召唤》" in prompts["draft"]
    assert "待提取正文：" in prompts["extract_state"]
    assert "候选状态变化：" in prompts["audit"]
    assert "待修订正文：" in prompts["revise"]

    combined_prompt = "\n".join(prompts.values())
    assert '"trusted_state"' not in combined_prompt
    assert '"context_package"' not in combined_prompt
    assert '"draft_text"' not in combined_prompt
    assert '"state_delta"' not in combined_prompt
    assert '"audit_report"' not in combined_prompt


def test_run_chapter_pipeline_normalizes_model_state_delta_shape(tmp_path) -> None:
    class LooseStateDeltaModel(FakeChapterModel):
        def complete(self, stage: str, messages, response_format: str) -> str:
            if stage == "extract_state":
                self.calls.append(stage)
                self.messages_by_stage[stage] = messages
                return """
                {
                  "chapter": {"number": 1, "title": "离开的召唤"},
                  "changes": [
                    {
                      "category": "人物",
                      "content": "莉拉主动离开村庄追查真相。"
                    }
                  ]
                }
                """
            return super().complete(stage, messages, response_format)

    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = LooseStateDeltaModel()

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)

        reviewed = run_chapter_pipeline(
            session,
            chapter.id,
            model_client=model,
            model_name="章节模型",
        )

    assert reviewed.state_delta["chapter"] == 1
    assert reviewed.state_delta["changes"] == [
        {
            "type": "人物",
            "target": "待确认",
            "change": "莉拉主动离开村庄追查真相。",
            "risk": "low",
        }
    ]


def test_run_chapter_pipeline_uses_description_state_delta_items(tmp_path) -> None:
    class DescriptionStateDeltaModel(FakeChapterModel):
        def complete(self, stage: str, messages, response_format: str) -> str:
            if stage == "extract_state":
                self.calls.append(stage)
                self.messages_by_stage[stage] = messages
                return """
                {
                  "chapter": {"number": 1, "title": "离开的召唤"},
                  "changes": [
                    {
                      "category": "人物",
                      "description": "苏清月：完成腹部缝合自救，建立冷静果敢的医女形象。"
                    }
                  ]
                }
                """
            return super().complete(stage, messages, response_format)

    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = DescriptionStateDeltaModel()

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)

        reviewed = run_chapter_pipeline(
            session,
            chapter.id,
            model_client=model,
            model_name="章节模型",
        )

    assert reviewed.state_delta["changes"] == [
        {
            "type": "人物",
            "target": "苏清月",
            "change": "完成腹部缝合自救，建立冷静果敢的医女形象。",
            "risk": "low",
        }
    ]


def test_run_chapter_pipeline_accepts_json_wrapped_in_model_explanation(tmp_path) -> None:
    class WrappedAuditModel(FakeChapterModel):
        def complete(self, stage: str, messages, response_format: str) -> str:
            if stage == "audit":
                self.calls.append(stage)
                self.messages_by_stage[stage] = messages
                return """
                审计结果如下：
                {
                  "risk_level": "low",
                  "issues": [],
                  "suggestions": []
                }
                """
            return super().complete(stage, messages, response_format)

    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = WrappedAuditModel()

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)

        reviewed = run_chapter_pipeline(
            session,
            chapter.id,
            model_client=model,
            model_name="章节模型",
        )

    assert reviewed.audit_report["risk_level"] == "low"


def test_run_chapter_pipeline_parses_markdown_audit_report(tmp_path) -> None:
    class MarkdownAuditModel(FakeChapterModel):
        def complete(self, stage: str, messages, response_format: str) -> str:
            if stage == "audit":
                self.calls.append(stage)
                self.messages_by_stage[stage] = messages
                return """
                ### 章节审计报告：第 1 章《离开的召唤》

                #### **1. 风险评估 (Risk Level: Low)**

                | 严重程度 | 问题标题 | 是否解决 | 详细描述 |
                | :--- | :--- | :--- | :--- |
                | **Medium** | **字数未达标** | **No** | 当前草稿偏短。 |
                | **Low** | **结尾钩子稳定** | **Yes** | 已满足章节钩子要求。 |

                #### **4. 改进建议 (Suggestions)**

                1. **扩充细节：** 增加感官描写。
                2. **强化生理反馈：** 补充体力消耗。
                """
            return super().complete(stage, messages, response_format)

    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = MarkdownAuditModel()

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)

        reviewed = run_chapter_pipeline(
            session,
            chapter.id,
            model_client=model,
            model_name="章节模型",
        )

    assert reviewed.audit_report["risk_level"] == "low"
    assert reviewed.audit_report["issues"][0] == {
        "severity": "medium",
        "title": "字数未达标",
        "resolved": False,
        "detail": "当前草稿偏短。",
    }
    assert reviewed.audit_report["issues"][1]["resolved"] is True
    assert "AI 审计返回格式异常" not in str(reviewed.audit_report)
    assert reviewed.audit_report["suggestions"] == [
        "扩充细节： 增加感官描写。",
        "强化生理反馈： 补充体力消耗。",
    ]


def test_run_chapter_pipeline_falls_back_when_audit_json_is_unusable(tmp_path) -> None:
    class EmptyAuditModel(FakeChapterModel):
        def complete(self, stage: str, messages, response_format: str) -> str:
            if stage == "audit":
                self.calls.append(stage)
                self.messages_by_stage[stage] = messages
                return ""
            return super().complete(stage, messages, response_format)

    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = EmptyAuditModel()

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)

        reviewed = run_chapter_pipeline(
            session,
            chapter.id,
            model_client=model,
            model_name="章节模型",
        )

    assert reviewed.status.value == "awaiting_review"
    assert reviewed.audit_report["issues"][0]["title"] == "AI 审计返回格式异常，请人工重点检查本章"


def test_chapter_plan_prompt_includes_saved_chapter_word_budget(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = FakeChapterModel()
    blueprint = _blueprint()
    blueprint.idea = "\n".join(
        [
            blueprint.idea,
            "可选偏好：",
            "- 全书目标字数：300000 字",
            "- 单章目标字数：3200 字",
        ]
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, blueprint, selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)

        run_chapter_pipeline(
            session,
            chapter.id,
            model_client=model,
            model_name="章节模型",
        )

    plan_prompt = "\n".join(message["content"] for message in model.messages_by_stage["plan"])

    assert "已有目标字数：3200 字" in plan_prompt
    assert "如果下方已有目标字数，word_budget 必须沿用该数值" in plan_prompt


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


def test_repair_chapter_prompt_combines_audit_issues_and_manual_instruction(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = PromptCaptureRepairModel()

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "结尾钩子偏弱", "resolved": False}],
            "suggestions": ["补强远处符号回应"],
        }
        session.add(reviewed)
        session.commit()

        repair_chapter_with_ai(
            session,
            reviewed.id,
            model_client=model,
            model_name="章节模型",
            reviewer_note="压缩环境描写，强化动作。",
        )

    prompt = model.prompts[0]
    assert "必须同时处理 AI 审核问题和人工修改意见" in prompt
    assert "结尾钩子偏弱" in prompt
    assert "压缩环境描写，强化动作。" in prompt
    assert "待修订正文：" in prompt
    assert "draft_text" not in prompt
    assert "previous_candidate" not in prompt
    assert '"reviewer_note"' not in prompt


def test_repair_chapter_prompt_uses_only_audit_issues_when_manual_instruction_is_empty(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = PromptCaptureRepairModel()

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "节奏偏散", "resolved": False}],
            "suggestions": ["收紧中段节奏"],
        }
        session.add(reviewed)
        session.commit()

        repair_chapter_with_ai(
            session,
            reviewed.id,
            model_client=model,
            model_name="章节模型",
            reviewer_note=None,
        )

    prompt = model.prompts[0]
    assert "未填写人工修改意见，本次只处理 AI 审核问题" in prompt
    assert "节奏偏散" in prompt
    assert '"reviewer_note": null' not in prompt
    assert "人工修改意见：" not in prompt


def test_repair_chapter_prompt_uses_latest_text_only_for_word_count_repair(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = PromptCaptureRepairModel()

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.draft_text = "草稿不应进入修订提示。"
        reviewed.revised_text = "最终候选正文超出目标。" * 6
        reviewed.word_count = len(reviewed.revised_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "字数达成率严重不足", "resolved": False}],
            "suggestions": ["扩写到目标字数。"],
        }
        session.add(reviewed)
        session.commit()

        repaired = repair_chapter_with_ai(
            session,
            reviewed.id,
            model_client=model,
            model_name="章节模型",
            reviewer_note="压缩到目标字数。",
        )

    assert repaired.status.value == "awaiting_review"
    assert len(model.prompts) == 1
    prompt = model.prompts[0]
    assert "目标字数：40 字" in prompt
    assert "建议区间：36-46 字" in prompt
    assert "当前正文已经超出目标，请以删减和合并为主" in prompt
    assert "最终候选正文超出目标。" in prompt
    assert "草稿不应进入修订提示" not in prompt
    assert "previous_candidate" not in prompt


def test_repair_chapter_prompt_replaces_stale_expansion_advice_when_current_text_is_long(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = PromptCaptureRepairModel()

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.revised_text = "最终候选正文已经明显超出目标，需要压缩。" * 6
        reviewed.word_count = len(reviewed.revised_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "字数达成率严重不足", "resolved": False}],
            "suggestions": [
                "当前字数约1000字，远低于3000字的预算，建议在自救环节增加更多生理痛苦描写。",
                "扩充恶仆赖大、赖二的对话内容。",
                "增加对科研空间初次开启时的视觉与体感描写。",
                "在反杀过程中，可加入更多利用解剖学知识精准致残的细节描写。",
            ],
        }
        session.add(reviewed)
        session.commit()

        repair_chapter_with_ai(
            session,
            reviewed.id,
            model_client=model,
            model_name="章节模型",
            reviewer_note=None,
        )

    prompt = model.prompts[0]
    assert "当前正文已经超出目标，请以删减和合并为主" in prompt
    assert "字数不在目标区间" in prompt
    assert "当前字数约1000字" not in prompt
    assert "远低于3000字" not in prompt
    assert "扩充恶仆" not in prompt
    assert "增加对科研空间" not in prompt
    assert "加入更多利用解剖学知识" not in prompt


def test_repair_chapter_prompt_includes_concise_book_boundaries(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = PromptCaptureRepairModel()

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "节奏偏散", "resolved": False}],
            "suggestions": [],
        }
        session.add(reviewed)
        session.commit()

        repair_chapter_with_ai(
            session,
            reviewed.id,
            model_client=model,
            model_name="章节模型",
            reviewer_note="压缩旁枝。",
        )

    prompt = model.prompts[0]
    assert "作品边界：" in prompt
    assert "类型：奇幻连载" in prompt
    assert "读者：喜欢成长冒险的连载读者" in prompt
    assert "前提：失忆少女在幽谷中寻找被抹去的王朝真相" in prompt
    assert "不得改写已锁定设定，不得新增绕过人工审核的可信状态。" in prompt


def test_repair_chapter_records_word_count_issue_unresolved_when_model_returns_off_target(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = PromptCaptureRepairModel(response="仍然太短")

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.revised_text = "短"
        reviewed.word_count = 1
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "字数达成率严重不足", "resolved": False}],
            "suggestions": ["扩写到目标字数。"],
        }
        session.add(reviewed)
        session.commit()

        repaired = repair_chapter_with_ai(
            session,
            reviewed.id,
            model_client=model,
            model_name="章节模型",
            reviewer_note="必须补足篇幅。",
        )

    assert len(model.prompts) == 1
    assert repaired.revised_text == "仍然太短"
    assert repaired.audit_report["issues"][0]["resolved"] is False


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


class PromptCaptureRepairModel:
    def __init__(
        self,
        response: str = "莉拉按修订要求重写正文，保留离村动作，并补强远处符号回应。",
    ) -> None:
        self.prompts: list[str] = []
        self.response = response

    def complete(self, stage: str, messages, response_format: str) -> str:
        self.prompts.append("\n".join(message["content"] for message in messages))
        assert stage == "revise"
        assert response_format == "text"
        return self.response


class ShortThenLongRepairModel:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.prompts: list[str] = []

    def complete(self, stage: str, messages, response_format: str) -> str:
        self.calls.append(stage)
        self.prompts.append("\n".join(message["content"] for message in messages))
        assert response_format == "text"
        if len(self.calls) == 1:
            return "仍然太短"
        return "莉拉沿着雾谷继续向前，掌心符号反复发热，她把疼痛记成线索，并听见远处微光回应。"


class LongThenTargetRepairModel:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.prompts: list[str] = []

    def complete(self, stage: str, messages, response_format: str) -> str:
        self.calls.append(stage)
        self.prompts.append("\n".join(message["content"] for message in messages))
        assert response_format == "text"
        if len(self.calls) == 1:
            return "莉拉沿着雾谷不断向前。" * 8
        return "莉拉沿着雾谷继续向前，掌心符号发热，她把疼痛记成线索，并听见远处微光回应。"


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
