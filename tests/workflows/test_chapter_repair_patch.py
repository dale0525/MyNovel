import json

from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, OpenBookBlueprint
from mynovel.domain.repositories import list_chapters_for_book, list_run_traces_for_book
from mynovel.workflows.chapter_pipeline import repair_chapter_with_ai, run_chapter_pipeline
from mynovel.workflows.open_book import create_draft_book_from_blueprint


def test_repair_chapter_with_ai_revises_text_and_reopens_review(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = PromptCapturePatchModel(
        {
            "operations": [
                {
                    "op": "replace",
                    "paragraph_id": 1,
                    "text": "莉拉保留离村动作，结尾处第二枚符号在雾中回应。",
                    "addresses": ["结尾钩子弱"],
                }
            ]
        }
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = _book_chapter(session, book.id, 1)
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

    assert model.calls == [("repair_patch", "json")]
    assert repaired.status.value == "awaiting_review"
    assert repaired.revised_text.startswith("莉拉保留离村动作，结尾处第二枚符号在雾中回应。")
    assert repaired.reviewer_note == "保留离村动作，补强结尾。"
    assert traces[-1].stage == "修复问题"
    assert traces[-1].prompt_id == "chapter_repair_patch"
    assert traces[-1].model == "章节模型"


def test_repair_chapter_prompt_combines_audit_issues_and_manual_instruction(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = PromptCapturePatchModel(
        {
            "operations": [
                {
                    "op": "insert_after",
                    "paragraph_id": 1,
                    "text": "远处符号随即回应，逼迫她继续行动。",
                    "addresses": ["结尾钩子偏弱"],
                }
            ]
        }
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = _book_chapter(session, book.id, 1)
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
    assert "段落清单：" in prompt
    assert "不要返回完整正文" in prompt
    assert "draft_text" not in prompt
    assert "previous_candidate" not in prompt
    assert '"reviewer_note"' not in prompt


def test_repair_chapter_prompt_uses_only_audit_issues_when_manual_instruction_is_empty(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = PromptCapturePatchModel(
        {
            "operations": [
                {
                    "op": "replace",
                    "paragraph_id": 1,
                    "text": "莉拉收紧动作，符号在掌心给出回应。",
                    "addresses": ["节奏偏散"],
                }
            ]
        }
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = _book_chapter(session, book.id, 1)
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


def test_repair_chapter_prompt_expands_bare_transition_jump_issue(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = PromptCapturePatchModel(
        {
            "operations": [
                {
                    "op": "insert_after",
                    "paragraph_id": 1,
                    "text": "她先确认退路，再沿着符号指向继续前进。",
                    "addresses": ["章节过度跳跃"],
                }
            ]
        }
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = _book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "章节过度跳跃", "resolved": False}],
            "suggestions": [],
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
    assert "章节过度跳跃" in prompt
    assert "补足场景之间的承接" in prompt
    assert "补清人物为什么立刻转场、下一步动作如何发生" in prompt
    assert "不要整章扩写或重写" in prompt


def test_repair_chapter_marks_transition_jump_resolved_after_bridge_rewrite(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    source_text = "甲" * 40 + "\n\n" + "乙" * 40 + "\n\n" + "丙" * 30
    model = PromptCapturePatchModel(
        {
            "operations": [
                {
                    "op": "replace",
                    "paragraph_id": 2,
                    "text": "她先确认符号发热，因为那是唯一线索。片刻后，她这才稳住呼吸，继续向祭坛靠近前行。",
                }
            ]
        }
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = _book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 120}
        reviewed.revised_text = source_text
        reviewed.word_count = len(source_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "章节过渡跳跃", "resolved": False}],
            "suggestions": [],
        }
        session.add(reviewed)
        session.commit()

        repaired = repair_chapter_with_ai(
            session,
            reviewed.id,
            model_client=model,
            model_name="章节模型",
            reviewer_note=None,
        )

    assert repaired.audit_report["issues"][0]["resolved"] is True
    assert "过渡承接" in repaired.audit_report["issues"][0]["detail"]
    assert repaired.audit_report["risk_level"] == "low"


def test_repair_chapter_uses_structured_patch_for_transition_jump_in_word_window(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    source_text = "甲" * 40 + "\n\n" + "乙" * 40 + "\n\n" + "丙" * 30
    patch = {
        "operations": [
            {
                "op": "insert_after",
                "paragraph_id": 2,
                "text": "因为符号发热，她这才继续向祭坛靠近。",
                "addresses": ["章节过渡跳跃"],
            }
        ]
    }
    model = PromptCapturePatchModel(patch)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = _book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 120}
        reviewed.revised_text = source_text
        reviewed.word_count = len(source_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "章节过渡跳跃", "resolved": False}],
            "suggestions": [],
        }
        session.add(reviewed)
        session.commit()

        repaired = repair_chapter_with_ai(
            session,
            reviewed.id,
            model_client=model,
            model_name="章节模型",
            reviewer_note=None,
        )
        traces = list_run_traces_for_book(session, book.id)

    assert model.calls == [("repair_patch", "json")]
    assert "只返回 JSON" in model.prompts[0]
    assert "不要返回完整正文" in model.prompts[0]
    assert repaired.status.value == "awaiting_review"
    assert "因为符号发热" in repaired.revised_text
    assert repaired.audit_report["issues"][0]["resolved"] is True
    assert traces[-1].prompt_id == "chapter_repair_patch"


def test_repair_chapter_prompt_includes_concise_book_boundaries(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = PromptCapturePatchModel(
        {
            "operations": [
                {
                    "op": "replace",
                    "paragraph_id": 1,
                    "text": "莉拉按修订要求重写正文，保留离村动作，并补强远处符号回应。",
                    "addresses": ["节奏偏散"],
                }
            ]
        }
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = _book_chapter(session, book.id, 1)
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


def test_repair_chapter_treats_string_false_resolved_as_unresolved(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = PromptCapturePatchModel(
        {
            "operations": [
                {
                    "op": "insert_after",
                    "paragraph_id": 1,
                    "text": "远处符号随即回应，逼迫她继续行动。",
                    "addresses": ["结尾钩子偏弱"],
                }
            ]
        }
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = _book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "结尾钩子偏弱", "resolved": "false"}],
            "suggestions": ["补强远处符号回应"],
        }
        session.add(reviewed)
        session.commit()

        repaired = repair_chapter_with_ai(
            session,
            reviewed.id,
            model_client=model,
            model_name="章节模型",
            reviewer_note=None,
        )

    assert "结尾钩子偏弱" in model.prompts[0]
    assert repaired.audit_report["issues"][0]["resolved"] is True


class PromptCapturePatchModel:
    def __init__(self, response: dict) -> None:
        self.calls: list[tuple[str, str]] = []
        self.prompts: list[str] = []
        self.response = response

    def complete(self, stage: str, messages, response_format: str) -> str:
        self.calls.append((stage, response_format))
        self.prompts.append("\n".join(message["content"] for message in messages))
        assert stage == "repair_patch"
        assert response_format == "json"
        return json.dumps(self.response, ensure_ascii=False)


def _book_chapter(session: Session, book_id: int, number: int):
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
