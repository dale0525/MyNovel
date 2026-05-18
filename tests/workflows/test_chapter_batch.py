from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BookStatus, BlueprintStatus, ChapterStatus, OpenBookBlueprint
from mynovel.domain.repositories import get_book, list_chapters_for_book, list_run_traces_for_book
from mynovel.workflows.chapter_batch import run_chapter_batch
from mynovel.workflows.open_book import create_draft_book_from_blueprint


class FakeBatchChapterModel:
    def __init__(self, risk_levels: list[str]) -> None:
        self.risk_levels = risk_levels
        self.audit_count = 0
        self.calls: list[str] = []

    def complete(self, stage: str, messages, response_format: str) -> str:
        self.calls.append(stage)
        match stage:
            case "plan":
                return """
                {
                  "goal": "推进本章主线并留下新问题",
                  "must_write": ["延续上一章承诺"],
                  "forbidden_drift": ["不要改写可信设定"],
                  "word_budget": 2600,
                  "ending_hook": "结尾抛出新线索"
                }
                """
            case "draft":
                return "莉拉沿着雾谷继续前进，发现旧王朝符号再次发热。"
            case "extract_state":
                return """
                {
                  "chapter": 1,
                  "changes": [
                    {
                      "type": "伏笔",
                      "target": "旧王朝符号",
                      "change": "符号在新地点再次发热",
                      "risk": "low"
                    }
                  ]
                }
                """
            case "audit":
                risk = self.risk_levels[self.audit_count]
                self.audit_count += 1
                resolved = "true" if risk != "high" else "false"
                severity = "low" if risk != "high" else "high"
                return f"""
                {{
                  "risk_level": "{risk}",
                  "issues": [
                    {{
                      "severity": "{severity}",
                      "title": "章节风险",
                      "resolved": {resolved}
                    }}
                  ],
                  "suggestions": ["进入人工审核"]
                }}
                """
            case "revise":
                return """
                {
                  "operations": [
                    {
                      "op": "replace",
                      "paragraph_id": 1,
                      "text": "莉拉沿着雾谷继续前进，旧王朝符号在结尾指向新的遗迹。",
                      "addresses": ["章节风险"]
                    }
                  ]
                }
                """
        raise AssertionError(stage)


def test_batch_runs_selected_chapters_into_review_queue_without_accepting(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = FakeBatchChapterModel(["low", "medium"])

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapters = list_chapters_for_book(session, book.id)

        result = run_chapter_batch(
            session,
            book.id,
            chapter_ids=[chapters[2].id or 0, chapters[0].id or 0],
            model_client=model,
            model_name="章节模型",
        )
        chapters = list_chapters_for_book(session, book.id)
        canon_version = result.trusted_state_version

    assert result.requested_chapter_ids == [chapters[2].id, chapters[0].id]
    assert result.completed_chapter_numbers == [1, 3]
    assert result.paused is False
    assert canon_version == 1
    assert [chapter.status for chapter in chapters[:3]] == [
        ChapterStatus.AWAITING_REVIEW,
        ChapterStatus.PLANNED,
        ChapterStatus.AWAITING_REVIEW,
    ]
    assert model.calls == [
        "plan",
        "draft",
        "extract_state",
        "audit",
        "revise",
        "plan",
        "draft",
        "extract_state",
        "audit",
        "revise",
    ]


def test_batch_pauses_book_on_high_risk_and_leaves_later_chapters_planned(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = FakeBatchChapterModel(["low", "high", "low"])

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapters = list_chapters_for_book(session, book.id)

        result = run_chapter_batch(
            session,
            book.id,
            chapter_ids=[chapter.id or 0 for chapter in chapters[:3]],
            model_client=model,
            model_name="章节模型",
        )
        chapters = list_chapters_for_book(session, book.id)
        stored_book = get_book(session, book.id)
        traces = list_run_traces_for_book(session, book.id)

    assert result.completed_chapter_numbers == [1, 2]
    assert result.paused is True
    assert result.paused_chapter_number == 2
    assert result.pause_reason == "高风险章节需要人工审核"
    assert stored_book is not None
    assert stored_book.status == BookStatus.PAUSED
    assert [chapter.status for chapter in chapters[:3]] == [
        ChapterStatus.AWAITING_REVIEW,
        ChapterStatus.AWAITING_REVIEW,
        ChapterStatus.PLANNED,
    ]
    assert traces[-1].stage == "批量生产暂停"
    assert traces[-1].metadata_["chapter"] == 2
    assert traces[-1].metadata_["reason"] == "高风险章节需要人工审核"


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
            "chapter_directions": [
                {"title": "离开的召唤", "goal": "发现第一枚符号"},
                {"title": "雾谷来信", "goal": "收到第二枚符号的线索"},
                {"title": "石门之前", "goal": "抵达第一处遗迹"},
            ],
        },
        raw_response="{}",
    )
