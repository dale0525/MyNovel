import json

from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, OpenBookBlueprint
from mynovel.domain.repositories import list_chapters_for_book, list_run_traces_for_book
from mynovel.workflows.chapter_pipeline import repair_chapter_with_ai, run_chapter_pipeline
from mynovel.workflows.open_book import create_draft_book_from_blueprint


def test_repair_chapter_prompt_uses_latest_text_only_for_word_count_repair(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    target_text = "终" * 40
    model = WordCountPatchModel(
        {"operations": [{"op": "replace", "paragraph_id": 1, "text": target_text}]}
    )

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
    assert model.calls == [("word_count_patch", "json")]
    prompt = model.prompts[0]
    assert "模式：压缩模式" in prompt
    assert "目标字数：40 字" in prompt
    assert "目标区间：36-46 字" in prompt
    assert "至少净删" in prompt
    assert "不得原样返回" in prompt
    assert "最终候选正文超出目标。" in prompt
    assert "草稿不应进入修订提示" not in prompt
    assert "previous_candidate" not in prompt


def test_repair_chapter_prompt_replaces_stale_expansion_advice_when_current_text_is_long(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = WordCountPatchModel(
        {"operations": [{"op": "replace", "paragraph_id": 1, "text": "压" * 40}]}
    )

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
    assert "模式：压缩模式" in prompt
    assert "只允许 delete、compress、replace" in prompt
    assert "字数不在目标区间" in prompt
    assert "当前字数约1000字" not in prompt
    assert "远低于3000字" not in prompt
    assert "扩充恶仆" not in prompt
    assert "增加对科研空间" not in prompt
    assert "加入更多利用解剖学知识" not in prompt


def test_repair_chapter_prompt_replaces_stale_reduction_advice_with_current_count(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = WordCountPatchModel(
        {"operations": [{"op": "replace", "paragraph_id": 1, "text": "莉" * 3000}]}
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 3000}
        reviewed.revised_text = "莉" * 3627
        reviewed.word_count = len(reviewed.revised_text)
        reviewed.audit_report = {
            "risk_level": "low",
            "issues": [
                {
                    "severity": "medium",
                    "title": "字数不在目标区间",
                    "detail": "自动复核：当前约 3627 字，目标 3000 字，达成率 121%（目标区间 2700-3450 字）；当前偏长。",
                    "resolved": False,
                }
            ],
            "suggestions": [
                "当前正文约 4109 字，已超出目标区间，请压缩到 3000 字左右。",
                "灵堂环境描写可进一步强化。",
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
    assert "当前正文约 3627 字，已超出目标区间，请压缩到 3000 字左右。" in prompt
    assert "当前正文约 4109 字" not in prompt
    assert "灵堂环境描写可进一步强化" in prompt


def test_word_count_patch_prompt_keeps_non_word_audit_issues_first_class(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = WordCountPatchModel(
        {"operations": [{"op": "replace", "paragraph_id": 1, "text": "莉" * 40}]}
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.revised_text = "莉拉推门而入。" * 10
        reviewed.word_count = len(reviewed.revised_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [
                {"severity": "medium", "title": "字数不在目标区间", "resolved": False},
                {
                    "severity": "medium",
                    "title": "侧面描写缺失",
                    "detail": "需要通过仆人反应侧写主角压迫感。",
                    "resolved": False,
                },
            ],
            "suggestions": ["压缩到目标字数，同时补足侧面描写。"],
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
    assert "你是章节修订补丁规划器" in prompt
    assert "必须同时解决所有未完成审核项" in prompt
    assert "侧面描写缺失" in prompt
    assert "需要通过仆人反应侧写主角压迫感" in prompt
    assert "非字数审核项不得因为压缩模式被忽略" in prompt
    assert '"addresses":["审核项标题"]' in prompt
    assert "不要新增剧情或环境描写" not in prompt


def test_repair_chapter_marks_non_word_issue_resolved_when_applied_patch_addresses_it(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = WordCountPatchModel(
        {
            "operations": [
                {
                    "op": "replace",
                    "paragraph_id": 1,
                    "text": "青黛看见莉拉沉静回望，竟下意识后退半步。" + "莉" * 20,
                    "reason": "补入青黛反应，解决侧面描写缺失。",
                    "addresses": ["侧面描写缺失"],
                }
            ]
        }
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.revised_text = "莉拉推门而入。" * 10
        reviewed.word_count = len(reviewed.revised_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [
                {"severity": "medium", "title": "字数不在目标区间", "resolved": False},
                {
                    "severity": "low",
                    "title": "侧面描写缺失",
                    "detail": "需要通过仆人反应侧写主角压迫感。",
                    "resolved": False,
                },
            ],
            "suggestions": ["压缩到目标字数，同时补足侧面描写。"],
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

    issues = repaired.audit_report["issues"]
    assert issues[0]["resolved"] is True
    assert issues[1]["resolved"] is True
    assert "应用补丁已覆盖该审核项" in issues[1]["detail"]
    assert repaired.audit_report["risk_level"] == "low"


def test_non_word_repair_rejects_response_that_breaks_stable_word_count_window(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    source_text = "莉" * 40
    model = TextRepairModel("短" * 10)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.revised_text = source_text
        reviewed.word_count = len(source_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [
                {
                    "severity": "medium",
                    "title": "字数不在目标区间",
                    "resolved": True,
                    "detail": "之前已进入目标区间。",
                },
                {"severity": "low", "title": "侧面描写缺失", "resolved": False},
            ],
            "suggestions": ["补足侧面描写。"],
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

    assert model.calls == [("revise", "text")]
    assert repaired.status.value == "needs_revision"
    assert repaired.revised_text == source_text
    assert repaired.word_count == len(source_text)
    assert "更偏离 36-46 字目标区间" in repaired.reviewer_note


def test_repair_rechecks_stale_resolved_word_count_issue_before_calling_model(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    side_prefix = "青黛惊恐地看着莉拉。"
    target_text = side_prefix + "莉" * (40 - len(side_prefix))
    model = WordCountPatchModel(
        {
            "operations": [
                {
                    "op": "replace",
                    "paragraph_id": 1,
                    "text": target_text,
                    "addresses": ["侧面描写缺失"],
                }
            ]
        }
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.revised_text = "莉" * 20
        reviewed.word_count = len(reviewed.revised_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [
                {
                    "severity": "medium",
                    "title": "字数不在目标区间",
                    "resolved": True,
                    "detail": "之前已进入目标区间。",
                },
                {"severity": "low", "title": "侧面描写缺失", "resolved": False},
            ],
            "suggestions": ["补足侧面描写。"],
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

    assert model.calls == [("word_count_patch", "json")]
    assert repaired.status.value == "awaiting_review"
    assert repaired.word_count == 40
    assert [issue["resolved"] for issue in repaired.audit_report["issues"]] == [True, True]


def test_non_word_repair_marks_side_description_issue_resolved_from_revised_text(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    revised_text = "青黛惊恐地看着莉拉，两个小丫鬟吓得瘫软在地。" + "莉" * 15
    model = TextRepairModel(revised_text)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.revised_text = "莉" * 40
        reviewed.word_count = len(reviewed.revised_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [
                {
                    "severity": "medium",
                    "title": "字数不在目标区间",
                    "resolved": True,
                    "detail": "之前已进入目标区间。",
                },
                {"severity": "low", "title": "侧面描写缺失", "resolved": False},
            ],
            "suggestions": ["补足侧面描写。"],
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

    issues = repaired.audit_report["issues"]
    assert repaired.status.value == "awaiting_review"
    assert 36 <= repaired.word_count <= 46
    assert issues[0]["resolved"] is True
    assert issues[1]["resolved"] is True
    assert "正文已出现明确侧面反应" in issues[1]["detail"]


def test_repair_chapter_records_word_count_issue_unresolved_when_patch_stays_off_target(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = WordCountPatchModel(
        {"operations": [{"op": "insert_after", "paragraph_id": 1, "text": "仍然太短"}]}
    )

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

    assert model.calls == [("word_count_patch", "json")]
    assert repaired.revised_text == "短\n\n仍然太短"
    assert repaired.audit_report["issues"][0]["resolved"] is False


def test_repair_chapter_records_prompt_response_and_word_count_diagnostics(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    patch = {"operations": [{"op": "insert_after", "paragraph_id": 1, "text": "莉" * 35}]}
    model = WordCountPatchModel(patch)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.revised_text = "短"
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
            reviewer_note="补足必要动作。",
        )
        traces = list_run_traces_for_book(session, book.id)

    repair_trace = traces[-1]
    assert repair_trace.stage == "修复问题"
    assert repair_trace.prompt_id == "chapter_word_count_patch"
    assert repair_trace.cost["prompt_chars"] > 0
    assert repair_trace.cost["completion_chars"] == len(repair_trace.metadata_["raw_response_text"])
    assert repair_trace.metadata_["before_word_count"] == 1
    assert repair_trace.metadata_["after_word_count"] == len(repaired.revised_text)
    assert repair_trace.metadata_["target_word_count"] == 40
    assert repair_trace.metadata_["word_count_window"] == [36, 46]
    assert repair_trace.metadata_["word_count_repair_mode"] == "expand"
    assert repair_trace.metadata_["patch_operations"] == patch["operations"]
    assert repair_trace.metadata_["reviewer_note"] == "补足必要动作。"
    assert repair_trace.metadata_["unresolved_audit_issues"] == ["字数达成率严重不足"]
    assert repair_trace.metadata_["prompt_messages"][0]["role"] == "system"
    assert "补足必要动作" in repair_trace.metadata_["prompt_messages"][1]["content"]
    assert json.loads(repair_trace.metadata_["raw_response_text"]) == patch
    assert json.loads(repair_trace.metadata_["response_text"]) == patch
    assert repair_trace.metadata_["applied_text"] == repaired.revised_text


def test_repair_chapter_marks_noop_word_count_patch_as_needing_revision(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    unchanged_text = "莉拉沿着雾谷继续向前。" * 8
    model = WordCountPatchModel(
        {"operations": [{"op": "replace", "paragraph_id": 1, "text": unchanged_text}]}
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.revised_text = unchanged_text
        reviewed.word_count = len(reviewed.revised_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "字数不在目标区间", "resolved": False}],
            "suggestions": ["压缩到目标字数。"],
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

    assert repaired.status.value == "needs_revision"
    assert repaired.reviewer_note == "AI 修复未改变正文：当前 88 字，仍未进入 36-46 字目标区间。"
    assert traces[-1].stage == "修复问题"
    assert traces[-1].metadata_["validation_warning"] == repaired.reviewer_note
    assert traces[-1].metadata_["before_word_count"] == 88
    assert traces[-1].metadata_["after_word_count"] == 88


def test_repair_chapter_rejects_word_count_patch_that_moves_farther_from_window(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    source_text = "莉拉沿着雾谷继续向前。" * 8
    worse_response = "莉拉沿着雾谷继续向前。" * 12
    model = WordCountPatchModel(
        {"operations": [{"op": "replace", "paragraph_id": 1, "text": worse_response}]}
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.revised_text = source_text
        reviewed.word_count = len(reviewed.revised_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "字数不在目标区间", "resolved": False}],
            "suggestions": ["压缩到目标字数。"],
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

    assert repaired.status.value == "needs_revision"
    assert repaired.revised_text == source_text
    assert repaired.word_count == len(source_text)
    assert repaired.reviewer_note == (
        "AI 修复结果被拒绝：模型将正文从 88 字扩写到 132 字，更偏离 36-46 字目标区间。"
    )
    assert traces[-1].metadata_["validation_warning"] == repaired.reviewer_note
    assert traces[-1].metadata_["after_word_count"] == len(source_text)
    assert traces[-1].metadata_["model_response_word_count"] == len(worse_response)
    assert traces[-1].metadata_["rejected_response_text"] == worse_response


def test_repair_chapter_uses_structured_patch_to_compress_overlong_text(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    source_text = "甲" * 20 + "\n\n" + "乙" * 20 + "\n\n" + "丙" * 20
    model = WordCountPatchModel(
        {"operations": [{"op": "delete", "paragraph_id": 2, "reason": "删除重复气氛描写"}]}
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.revised_text = source_text
        reviewed.word_count = len(source_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "字数不在目标区间", "resolved": False}],
            "suggestions": ["压缩到目标字数。"],
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

    assert model.calls == [("word_count_patch", "json")]
    assert "压缩模式" in model.prompts[0]
    assert "至少净删" in model.prompts[0]
    assert "段落 2" in model.prompts[0]
    assert repaired.status.value == "awaiting_review"
    assert repaired.revised_text == "甲" * 20 + "\n\n" + "丙" * 20
    assert 36 <= repaired.word_count <= 46
    assert traces[-1].prompt_id == "chapter_word_count_patch"
    assert traces[-1].metadata_["word_count_repair_mode"] == "compress"
    assert traces[-1].metadata_["patch_operations"] == [
        {"op": "delete", "paragraph_id": 2, "reason": "删除重复气氛描写"}
    ]


def test_repair_chapter_accepts_json_patch_with_trailing_markdown_fence(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    source_text = "\n\n".join("甲" * 10 for _ in range(5))
    patch = {"operations": [{"op": "delete", "paragraph_id": 2, "reason": "删除重复段落"}]}
    model = RawWordCountPatchModel(json.dumps(patch, ensure_ascii=False) + "\n\n```")

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.revised_text = source_text
        reviewed.word_count = len(source_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "字数不在目标区间", "resolved": False}],
            "suggestions": ["压缩到目标字数。"],
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

    assert repaired.status.value == "awaiting_review"
    assert repaired.word_count == 46
    assert traces[-1].metadata_["raw_response_text"].endswith("```")


def test_repair_chapter_uses_best_in_window_prefix_when_patch_over_compresses(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    source_text = "\n\n".join("甲" * 10 for _ in range(5))
    model = WordCountPatchModel(
        {
            "operations": [
                {"op": "delete", "paragraph_id": 2, "reason": "删除重复段落"},
                {"op": "delete", "paragraph_id": 3, "reason": "继续删除会过压"},
            ]
        }
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.revised_text = source_text
        reviewed.word_count = len(source_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "字数不在目标区间", "resolved": False}],
            "suggestions": ["压缩到目标字数。"],
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

    assert repaired.status.value == "awaiting_review"
    assert repaired.word_count == 46
    assert repaired.revised_text == "\n\n".join("甲" * 10 for _ in range(4))
    assert traces[-1].metadata_["patch_operations"] == [
        {"op": "delete", "paragraph_id": 2, "reason": "删除重复段落"},
        {"op": "delete", "paragraph_id": 3, "reason": "继续删除会过压"},
    ]
    assert traces[-1].metadata_["applied_patch_operations"] == [
        {"op": "delete", "paragraph_id": 2, "reason": "删除重复段落"}
    ]


def test_repair_chapter_uses_structured_patch_to_expand_short_text(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    source_text = "甲" * 10 + "\n\n" + "乙" * 10
    model = WordCountPatchModel(
        {
            "operations": [
                {
                    "op": "insert_after",
                    "paragraph_id": 1,
                    "text": "新" * 15,
                    "reason": "补足动作因果",
                }
            ]
        }
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.revised_text = source_text
        reviewed.word_count = len(source_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [{"severity": "medium", "title": "字数达成率严重不足", "resolved": False}],
            "suggestions": ["补足到目标字数。"],
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

    assert model.calls == [("word_count_patch", "json")]
    assert "扩写模式" in model.prompts[0]
    assert "至少净增" in model.prompts[0]
    assert repaired.status.value == "awaiting_review"
    assert repaired.revised_text == "甲" * 10 + "\n\n" + "新" * 15 + "\n\n" + "乙" * 10
    assert 36 <= repaired.word_count <= 46
    assert traces[-1].prompt_id == "chapter_word_count_patch"
    assert traces[-1].metadata_["word_count_repair_mode"] == "expand"
    assert traces[-1].metadata_["patch_operations"][0]["text"] == "新" * 15


def test_repair_chapter_refreshes_stale_word_count_issue_when_text_is_too_long(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = WordCountPatchModel(
        {"operations": [{"op": "replace", "paragraph_id": 1, "text": "莉" * 60}]}
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 40}
        reviewed.revised_text = "莉" * 70
        reviewed.word_count = len(reviewed.revised_text)
        reviewed.audit_report = {
            "risk_level": "medium",
            "issues": [
                {
                    "severity": "medium",
                    "title": "字数达成度偏低",
                    "detail": "当前正文字数约 1500 字，距离 3000 字目标有较大缺口。",
                    "resolved": False,
                }
            ],
            "suggestions": ["扩写到目标字数。", "增加更多环境描写。"],
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

    word_count_issue = repaired.audit_report["issues"][0]
    suggestions = "\n".join(repaired.audit_report["suggestions"])
    assert word_count_issue["resolved"] is False
    assert word_count_issue["title"] == "字数不在目标区间"
    assert "当前偏长" in word_count_issue["detail"]
    assert "1500 字" not in word_count_issue["detail"]
    assert "扩写" not in suggestions
    assert "增加更多" not in suggestions
    assert "压缩到 40 字左右" in suggestions


def test_repair_chapter_refreshes_stale_reduction_suggestion_to_current_count(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = WordCountPatchModel(
        {"operations": [{"op": "replace", "paragraph_id": 1, "text": "莉" * 3627}]}
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.plan = {**reviewed.plan, "word_budget": 3000}
        reviewed.revised_text = "莉" * 3675
        reviewed.word_count = len(reviewed.revised_text)
        reviewed.audit_report = {
            "risk_level": "low",
            "issues": [
                {
                    "severity": "medium",
                    "title": "字数不在目标区间",
                    "detail": "自动复核：当前约 3675 字，目标 3000 字，达成率 122%（目标区间 2700-3450 字）；当前偏长。",
                    "resolved": False,
                }
            ],
            "suggestions": [
                "当前正文约 4109 字，已超出目标区间，请压缩到 3000 字左右。",
                "灵堂环境描写可进一步强化。",
            ],
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

    suggestions = "\n".join(repaired.audit_report["suggestions"])
    assert "当前正文约 3627 字，已超出目标区间，请压缩到 3000 字左右。" in suggestions
    assert "当前正文约 4109 字" not in suggestions
    assert "灵堂环境描写可进一步强化" in suggestions


class WordCountPatchModel:
    def __init__(self, response: dict) -> None:
        self.calls: list[tuple[str, str]] = []
        self.prompts: list[str] = []
        self.response = response

    def complete(self, stage: str, messages, response_format: str) -> str:
        self.calls.append((stage, response_format))
        self.prompts.append("\n".join(message["content"] for message in messages))
        assert stage == "word_count_patch"
        assert response_format == "json"
        return json.dumps(self.response, ensure_ascii=False)


class RawWordCountPatchModel:
    def __init__(self, response: str) -> None:
        self.calls: list[tuple[str, str]] = []
        self.prompts: list[str] = []
        self.response = response

    def complete(self, stage: str, messages, response_format: str) -> str:
        self.calls.append((stage, response_format))
        self.prompts.append("\n".join(message["content"] for message in messages))
        assert stage == "word_count_patch"
        assert response_format == "json"
        return self.response


class TextRepairModel:
    def __init__(self, response: str) -> None:
        self.calls: list[tuple[str, str]] = []
        self.response = response

    def complete(self, stage: str, messages, response_format: str) -> str:
        self.calls.append((stage, response_format))
        assert stage == "revise"
        assert response_format == "text"
        return self.response


def book_chapter(session: Session, book_id: int, number: int):
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
