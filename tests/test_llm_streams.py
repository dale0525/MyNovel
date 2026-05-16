from pathlib import Path

from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, ChapterStatus, OpenBookBlueprint
from mynovel.domain.repositories import (
    add_open_book_blueprint,
    get_open_book_blueprint,
    list_chapters_for_book,
)
from mynovel.llm_streams import (
    stream_create_open_book_blueprint,
    stream_generate_volume_outline,
    stream_revise_blueprint,
    stream_run_chapter,
)
from mynovel.workflows.open_book import create_draft_book_from_blueprint, lock_canon_foundation


class FakeBlueprintStreamModel:
    def stream_complete(self, stage: str, messages, response_format: str):
        assert stage == "open_book_blueprint"
        assert messages
        assert response_format == "json"
        yield _valid_blueprint_json()[:80]
        yield _valid_blueprint_json()[80:]


class FakeChapterStreamModel:
    model = "章节模型"

    def stream_complete(self, stage: str, messages, response_format: str):
        assert messages
        payload = {
            "plan": """
            {
              "goal": "让莉拉发现第一枚旧王朝符号",
              "must_write": ["离开村庄", "符号发热"],
              "forbidden_drift": ["不能确认莉拉真实身份"],
              "word_budget": 2800,
              "ending_hook": "第二枚符号在远处回应"
            }
            """,
            "draft": "莉拉离开村庄，雾气在谷口低伏。她掌心的符号忽然发热。",
            "extract_state": """
            {
              "chapter": 1,
              "changes": [
                {"type": "人物状态", "target": "莉拉", "change": "主动离开村庄追查真相"}
              ]
            }
            """,
            "audit": """
            {
              "risk_level": "medium",
              "issues": [{"severity": "medium", "title": "结尾钩子还不够强", "resolved": false}],
              "suggestions": ["补强符号回应"]
            }
            """,
            "revise": "莉拉离开村庄，雾气在谷口低伏。她掌心的符号忽然发热，远处也亮起同样的微光。",
        }[stage]
        assert response_format == ("text" if stage in {"draft", "revise"} else "json")
        midpoint = max(1, len(payload) // 2)
        yield payload[:midpoint]
        yield payload[midpoint:]


class FakeVolumeOutlineStreamModel:
    model = "卷纲模型"

    def stream_complete(self, stage: str, messages, response_format: str):
        assert stage == "volume_outline"
        assert messages
        assert response_format == "json"
        payload = """
        {
          "volumes": [
            {
              "volume_number": 1,
              "title": "旧王朝回声",
              "core_conflict": "莉拉必须确认符号与旧王朝的关系。",
              "pacing_curve": ["离乡", "追索", "卷末揭露"],
              "payoff_distribution": ["确认符号来源"],
              "key_turns": ["离开村庄", "进入遗迹"],
              "commitments": ["每章推进一枚符号"],
              "chapters": [
                {
                  "number": 1,
                  "title": "符号发热",
                  "goal": "莉拉发现第一枚符号回应远方遗迹。",
                  "ending_hook": "远处亮起第二枚符号",
                  "must_write": ["离开村庄", "符号发热"]
                },
                {
                  "number": 2,
                  "title": "雾谷旧路",
                  "goal": "莉拉沿旧路找到遗迹入口。"
                }
              ]
            }
          ]
        }
        """
        midpoint = max(1, len(payload) // 2)
        yield payload[:midpoint]
        yield payload[midpoint:]


def test_stream_create_open_book_blueprint_yields_chunks_and_persists_result(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"

    events = list(
        stream_create_open_book_blueprint(
            db_path,
            {"idea": "失意档案员重建禁书图书馆"},
            model_client=FakeBlueprintStreamModel(),
        )
    )

    assert [event["type"] for event in events] == ["started", "chunk", "chunk", "done"]
    done = events[-1]
    assert done["redirectTo"] == f"/blueprints/{done['blueprintId']}"
    assert done["blueprint"]["status"] == "succeeded"
    assert done["blueprint"]["content"]["title_options"] == ["长夜档案"]

    with Session(create_engine_for_path(db_path)) as session:
        blueprint = get_open_book_blueprint(session, done["blueprintId"])
    assert blueprint is not None
    assert blueprint.status == BlueprintStatus.SUCCEEDED
    assert blueprint.content["central_conflict"] == "档案员追查禁书真相。"


def test_stream_revise_blueprint_creates_revision_and_persists_result(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    parent_id = _save_succeeded_blueprint(db_path)

    events = list(
        stream_revise_blueprint(
            db_path,
            parent_id,
            {"revisionNotes": "主角更主动"},
            model_client=FakeBlueprintStreamModel(),
        )
    )

    done = events[-1]
    assert done["type"] == "done"
    assert done["blueprintId"] != parent_id
    assert done["redirectTo"] == f"/blueprints/{done['blueprintId']}"
    with Session(create_engine_for_path(db_path)) as session:
        revision = get_open_book_blueprint(session, done["blueprintId"])
    assert revision is not None
    assert revision.parent_id == parent_id
    assert revision.version == 2
    assert revision.status == BlueprintStatus.SUCCEEDED
    assert revision.instruction == "主角更主动"


def test_stream_run_chapter_yields_model_chunks_and_returns_fresh_chapter(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    chapter_id = _create_locked_book_chapter(db_path)

    events = list(stream_run_chapter(db_path, chapter_id, model_client=FakeChapterStreamModel()))

    assert events[0]["type"] == "started"
    assert any(event["type"] == "chunk" and "远处也亮起" in event["text"] for event in events)
    done = events[-1]
    assert done["type"] == "done"
    assert done["chapter"]["chapter"]["status"] == "awaiting_review"
    assert "远处也亮起同样的微光" in done["chapter"]["chapter"]["revisedText"]

    with Session(create_engine_for_path(db_path)) as session:
        chapter = session.get(type(list_chapters_for_book(session, 1)[0]), chapter_id)
    assert chapter is not None
    assert chapter.status == ChapterStatus.AWAITING_REVIEW


def test_stream_generate_volume_outline_yields_chunks_and_persists_plan(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id = _create_locked_book(db_path)

    events = list(
        stream_generate_volume_outline(
            db_path,
            book_id,
            model_client=FakeVolumeOutlineStreamModel(),
        )
    )

    assert events[0]["type"] == "started"
    assert any(event["type"] == "chunk" and "旧王朝回声" in event["text"] for event in events)
    done = events[-1]
    assert done["type"] == "done"
    assert done["book"]["volumePlans"][0]["title"] == "旧王朝回声"
    assert done["book"]["chapters"][0]["title"] == "符号发热"
    assert done["book"]["chapters"][0]["volumeNumber"] == 1

    with Session(create_engine_for_path(db_path)) as session:
        chapters = list_chapters_for_book(session, book_id)
    assert chapters[0].plan["volume_number"] == 1
    assert chapters[0].plan["goal"] == "莉拉发现第一枚符号回应远方遗迹。"


def _save_succeeded_blueprint(db_path: Path) -> int:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        blueprint = add_open_book_blueprint(
            session,
            OpenBookBlueprint(
                idea="一座图书馆",
                status=BlueprintStatus.SUCCEEDED,
                content={"title_options": ["旧蓝图"]},
            ),
        )
        assert blueprint.id is not None
        return blueprint.id


def _create_locked_book_chapter(db_path: Path) -> int:
    book_id = _create_locked_book(db_path)
    with Session(create_engine_for_path(db_path)) as session:
        chapter = list_chapters_for_book(session, book_id)[0]
        assert chapter.id is not None
        return chapter.id


def _create_locked_book(db_path: Path) -> int:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = create_draft_book_from_blueprint(
            session,
            OpenBookBlueprint(
                idea="失忆少女寻找旧王朝真相",
                version=1,
                status=BlueprintStatus.SUCCEEDED,
                content={
                    "title_options": ["长夜图书馆"],
                    "genre": "奇幻连载",
                    "audience": "成长冒险读者",
                    "selling_points": ["每章揭开一条旧王朝线索"],
                    "protagonist": {"name": "莉拉"},
                    "world": {"premise": "幽谷里散落着旧王朝遗迹"},
                    "central_conflict": "莉拉必须确认自己与旧王朝覆灭之间的关系。",
                    "reader_promises": ["持续发现遗迹"],
                    "chapter_directions": [{"title": "离开的召唤", "goal": "发现第一枚符号"}],
                },
            ),
            selected_title="长夜图书馆",
            lock_foundation=False,
        )
        lock_canon_foundation(session, book.id)
        assert book.id is not None
        return book.id


def _valid_blueprint_json() -> str:
    return """
{
  "title_options": ["长夜档案"],
  "genre": "奇幻",
  "audience": "成人",
  "selling_points": ["禁书悬疑"],
  "protagonist": {"name": "林既明"},
  "world": {"summary": "禁书会吞噬记忆"},
  "central_conflict": "档案员追查禁书真相。",
  "reader_promises": ["真相反转"],
  "chapter_directions": [
    {"title": "第1章", "goal": "发现禁书"},
    {"title": "第2章", "goal": "确认代价"}
  ]
}
"""
