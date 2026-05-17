from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, Chapter, ChapterStatus, OpenBookBlueprint, VolumePlan
from mynovel.domain.repositories import list_chapters_for_book, list_volume_plans_for_book
from mynovel.workflows.open_book import create_draft_book_from_blueprint, lock_canon_foundation
from mynovel.workflows.volume_planning import generate_volume_outline, revise_volume_outline


class FakeVolumeRevisionModel:
    model = "卷纲修订模型"

    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        assert stage == "volume_outline_revision"
        assert response_format == "json"
        joined = "\n".join(message["content"] for message in messages)
        self.calls.append((stage, joined))
        return self.payload


class FakeShortVolumeOutlineModel:
    model = "卷纲模型"

    def __init__(self, chapter_count: int) -> None:
        self.chapter_count = chapter_count
        self.calls: list[tuple[str, str]] = []

    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        assert stage == "volume_outline"
        assert response_format == "json"
        joined = "\n".join(message["content"] for message in messages)
        self.calls.append((stage, joined))
        chapters = [
            {"number": number, "title": f"第{number:02d}章", "goal": f"推进第{number}章。"}
            for number in range(1, self.chapter_count + 1)
        ]
        return (
            '{"volumes":[{'
            '"volume_number":1,'
            '"title":"禁书馆夺回战",'
            '"core_conflict":"主角必须夺回禁书馆。",'
            '"pacing_curve":["夺回","反攻"],'
            '"payoff_distribution":[],'
            '"key_turns":["夺回钥匙"],'
            '"commitments":["禁书馆主线"],'
            f'"chapters":{chapters!r}'
            "}]}".replace("'", '"')
        )


class FakeMultiVolumeOutlineWithoutNumbersModel:
    model = "卷纲模型"

    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        assert stage == "volume_outline"
        assert response_format == "json"
        volumes = []
        for volume_number, chapter_count in [(1, 10), (2, 25), (3, 25), (4, 7)]:
            chapters = [
                {"title": f"第{volume_number}-{index}章", "goal": f"推进第{volume_number}-{index}章。"}
                for index in range(1, chapter_count + 1)
            ]
            volumes.append(
                {
                    "volume_number": volume_number,
                    "title": f"第{volume_number}卷",
                    "core_conflict": f"推进第{volume_number}卷。",
                    "pacing_curve": [],
                    "payoff_distribution": [],
                    "key_turns": [],
                    "commitments": [],
                    "chapters": chapters,
                }
            )
        return str({"volumes": volumes}).replace("'", '"')


class FakeAllVolumesRevisionWithoutNumbersModel:
    model = "卷纲修订模型"

    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        assert stage == "volume_outline_revision"
        assert response_format == "json"
        volumes = []
        for volume_number, chapter_count in [(1, 10), (2, 25), (3, 25), (4, 7)]:
            chapters = [
                {"title": f"修复后第{volume_number}-{index}章", "goal": f"推进修复后第{volume_number}-{index}章。"}
                for index in range(1, chapter_count + 1)
            ]
            volumes.append(
                {
                    "volume_number": volume_number,
                    "title": f"修复后第{volume_number}卷",
                    "core_conflict": f"修复后推进第{volume_number}卷。",
                    "pacing_curve": [],
                    "payoff_distribution": [],
                    "key_turns": [],
                    "commitments": [],
                    "chapters": chapters,
                }
            )
        return str({"volumes": volumes}).replace("'", '"')


def test_generate_volume_outline_extends_short_model_result_to_target_chapter_count(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = FakeShortVolumeOutlineModel(chapter_count=37)

    with Session(engine) as session:
        blueprint = _blueprint()
        blueprint.idea = "一句灵感：失意档案员重建禁书馆\n可选偏好：\n- 全书目标字数：200000 字\n- 单章目标字数：3000 字"
        book = create_draft_book_from_blueprint(session, blueprint, selected_title="长夜图书馆")
        lock_canon_foundation(session, book.id)

        generate_volume_outline(session, book.id or 0, model_client=model)
        chapters = list_chapters_for_book(session, book.id or 0)

    assert len(chapters) == 67
    assert chapters[-1].number == 67
    assert chapters[-1].plan["word_budget"] == 3000
    assert '"target_chapter_count": 67' in model.calls[0][1]
    assert '"required_chapter_range": "1-67"' in model.calls[0][1]


def test_generate_volume_outline_fills_missing_plan_without_overwriting_existing_items(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = FakeShortVolumeOutlineModel(chapter_count=12)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        lock_canon_foundation(session, book.id)
        original_plan = list_volume_plans_for_book(session, book.id or 0)[0]
        original_plan_title = original_plan.title
        original_plan_conflict = original_plan.core_conflict
        original_chapters = list_chapters_for_book(session, book.id or 0)
        original_first_title = original_chapters[0].title
        original_second_goal = original_chapters[1].plan["goal"]

        generate_volume_outline(session, book.id or 0, model_client=model)
        plans = list_volume_plans_for_book(session, book.id or 0)
        chapters = list_chapters_for_book(session, book.id or 0)

    assert plans[0].title == original_plan_title
    assert plans[0].core_conflict == original_plan_conflict
    assert chapters[0].title == original_first_title
    assert chapters[1].plan["goal"] == original_second_goal
    assert len(chapters) == 43
    assert chapters[10].number == 11
    assert chapters[10].title == "第11章"
    assert chapters[10].plan["volume_number"] == 1


def test_generate_volume_outline_renumbers_model_chapters_sequentially_across_volumes(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        blueprint = _blueprint()
        blueprint.idea = "一句灵感：失意档案员重建禁书馆\n可选偏好：\n- 全书目标字数：200000 字\n- 单章目标字数：3000 字"
        book = create_draft_book_from_blueprint(session, blueprint, selected_title="长夜图书馆")
        lock_canon_foundation(session, book.id)

        generate_volume_outline(
            session,
            book.id or 0,
            model_client=FakeMultiVolumeOutlineWithoutNumbersModel(),
        )
        chapters = list_chapters_for_book(session, book.id or 0)

    ranges = {}
    for volume_number in range(1, 5):
        numbers = [
            chapter.number
            for chapter in chapters
            if chapter.plan.get("volume_number") == volume_number
        ]
        ranges[volume_number] = (min(numbers), max(numbers), len(numbers))

    assert ranges == {
        1: (1, 10, 10),
        2: (11, 35, 25),
        3: (36, 60, 25),
        4: (61, 67, 7),
    }


def test_revise_all_volumes_replaces_planned_chapter_list_with_sequential_ranges(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        blueprint = _blueprint()
        blueprint.idea = "一句灵感：失意档案员重建禁书馆\n可选偏好：\n- 全书目标字数：200000 字\n- 单章目标字数：3000 字"
        book = create_draft_book_from_blueprint(session, blueprint, selected_title="长夜图书馆")
        lock_canon_foundation(session, book.id)
        _seed_broken_volume_ranges(session, book.id or 0)

        revise_volume_outline(
            session,
            book.id or 0,
            {"scope": "all_volumes", "revisionNotes": "修复旧的卷纲和章节归属。"},
            model_client=FakeAllVolumesRevisionWithoutNumbersModel(),
        )
        plans = list_volume_plans_for_book(session, book.id or 0)
        chapters = list_chapters_for_book(session, book.id or 0)

    assert [plan.title for plan in plans] == [
        "修复后第1卷",
        "修复后第2卷",
        "修复后第3卷",
        "修复后第4卷",
    ]
    ranges = {}
    for volume_number in range(1, 5):
        numbers = [
            chapter.number
            for chapter in chapters
            if chapter.plan.get("volume_number") == volume_number
        ]
        ranges[volume_number] = (min(numbers), max(numbers), len(numbers))

    assert ranges == {
        1: (1, 10, 10),
        2: (11, 35, 25),
        3: (36, 60, 25),
        4: (61, 67, 7),
    }
    chapter_46 = next(chapter for chapter in chapters if chapter.number == 46)
    chapter_61 = next(chapter for chapter in chapters if chapter.number == 61)
    assert chapter_46.plan["volume_number"] == 3
    assert chapter_61.plan["volume_number"] == 4


def test_revise_volume_summary_updates_only_target_volume_plan(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = FakeVolumeRevisionModel(
        """
        {
          "volumes": [
            {
              "volume_number": 1,
              "title": "禁书馆夺回战",
              "core_conflict": "主角必须夺回被二房把持的禁书馆。",
              "pacing_curve": ["夺回", "设局"],
              "payoff_distribution": ["禁书馆钥匙"],
              "key_turns": ["公开反击"],
              "commitments": ["禁书馆主线持续推进"],
              "chapters": [
                {"number": 1, "title": "不应改动", "goal": "不应改动"}
              ]
            }
          ]
        }
        """
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        lock_canon_foundation(session, book.id)
        first_title = list_chapters_for_book(session, book.id)[0].title

        revise_volume_outline(
            session,
            book.id or 0,
            {
                "scope": "volume_summary",
                "volumeNumber": 1,
                "revisionNotes": "第一卷更像夺回战。",
            },
            model_client=model,
        )
        plans = list_volume_plans_for_book(session, book.id or 0)
        chapters = list_chapters_for_book(session, book.id or 0)

    assert plans[0].title == "禁书馆夺回战"
    assert plans[0].core_conflict == "主角必须夺回被二房把持的禁书馆。"
    assert chapters[0].title == first_title
    assert "scope" in model.calls[0][1]
    assert "volume_summary" in model.calls[0][1]


def test_revise_all_volumes_prompt_treats_produced_chapters_as_fact_boundary(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = FakeVolumeRevisionModel(
        """
        {
          "volumes": [
            {
              "volume_number": 1,
              "title": "禁书馆夺回战",
              "core_conflict": "围绕既有章节事实重整首卷。",
              "pacing_curve": ["夺回", "设局"],
              "payoff_distribution": [],
              "key_turns": [],
              "commitments": ["禁书馆主线"],
              "chapters": [
                {"number": 1, "title": "不应改动", "goal": "不应改动"}
              ]
            }
          ]
        }
        """
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        lock_canon_foundation(session, book.id)
        chapters = list_chapters_for_book(session, book.id or 0)
        chapters[0].status = ChapterStatus.ACCEPTED
        chapters[0].summary = "第一章已经确认主角从旧馆逃出。"
        chapters[0].final_text = "林烬从旧馆逃出，禁书钥匙落入掌心。"
        session.add(chapters[0])
        session.commit()
        original_title = chapters[0].title
        original_summary = chapters[0].summary

        revise_volume_outline(
            session,
            book.id or 0,
            {
                "scope": "all_volumes",
                "revisionNotes": "把第一卷改成主角主动潜入禁书馆。",
            },
            model_client=model,
        )
        revised_chapters = list_chapters_for_book(session, book.id or 0)

    prompt = model.calls[0][1]
    assert "已生产章节是不可推翻的事实边界" in prompt
    assert '"locked": true' in prompt
    assert "第一章已经确认主角从旧馆逃出。" in prompt
    assert "林烬从旧馆逃出，禁书钥匙落入掌心。" in prompt
    assert revised_chapters[0].title == original_title
    assert revised_chapters[0].summary == original_summary


def test_revise_volume_chapters_preserves_locked_chapters(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = FakeVolumeRevisionModel(
        """
        {
          "volumes": [
            {
              "volume_number": 1,
              "title": "模型不应改概括",
              "core_conflict": "模型不应改概括。",
              "pacing_curve": ["模型不应改概括"],
              "payoff_distribution": [],
              "key_turns": [],
              "commitments": [],
              "chapters": [
                {"number": 1, "title": "锁定章不应改", "goal": "锁定章不应改"},
                {"number": 2, "title": "提前设局", "goal": "二房提前布下药铺陷阱。"}
              ]
            }
          ]
        }
        """
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        lock_canon_foundation(session, book.id)
        chapters = list_chapters_for_book(session, book.id)
        chapters[0].status = ChapterStatus.ACCEPTED
        session.add(chapters[0])
        session.commit()
        original_title = chapters[0].title
        original_conflict = list_volume_plans_for_book(session, book.id or 0)[0].core_conflict

        revise_volume_outline(
            session,
            book.id or 0,
            {
                "scope": "volume_chapters",
                "volumeNumber": 1,
                "revisionNotes": "第二章提前把二房药铺线拉出来。",
            },
            model_client=model,
        )
        revised_plans = list_volume_plans_for_book(session, book.id or 0)
        revised_chapters = list_chapters_for_book(session, book.id or 0)

    assert revised_chapters[0].title == original_title
    assert revised_chapters[1].title == "提前设局"
    assert revised_chapters[1].plan["goal"] == "二房提前布下药铺陷阱。"
    assert revised_plans[0].core_conflict == original_conflict


def _blueprint() -> OpenBookBlueprint:
    return OpenBookBlueprint(
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜图书馆"],
            "genre": "玄幻",
            "audience": "男频网文读者",
            "central_conflict": "主角必须在追捕者到来前恢复禁书馆。",
            "reader_promises": ["持续禁书谜题", "关系信任逐章推进"],
            "chapter_directions": [
                {"title": "残页召唤", "goal": "主角得到第一张残页。"},
                {"title": "药铺暗线", "goal": "主角发现二房控制药铺。"},
            ],
            "volume_plan": {
                "volume_number": 1,
                "title": "禁书馆重启",
                "core_conflict": "主角必须在追捕者到来前恢复禁书馆。",
                "pacing_curve": ["开局钩子", "中段反转", "卷末危机"],
                "commitments": ["持续禁书谜题", "关系信任逐章推进"],
            },
        },
        raw_response="{}",
    )


def _seed_broken_volume_ranges(session: Session, book_id: int) -> None:
    for volume_number in range(2, 5):
        session.add(
            VolumePlan(
                book_id=book_id,
                volume_number=volume_number,
                title=f"旧第{volume_number}卷",
                core_conflict=f"旧第{volume_number}卷冲突。",
            )
        )
    broken_ranges = [
        (range(11, 36), 2),
        (range(36, 46), 3),
        (range(46, 68), 4),
    ]
    for chapter_numbers, volume_number in broken_ranges:
        for number in chapter_numbers:
            session.add(
                Chapter(
                    book_id=book_id,
                    number=number,
                    title=f"旧第{number}章",
                    plan={
                        "volume_number": volume_number,
                        "goal": f"旧第{number}章目标。",
                    },
                )
            )
    session.commit()
