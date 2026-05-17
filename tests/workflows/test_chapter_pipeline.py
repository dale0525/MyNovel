from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import (
    BookStatus,
    BlueprintStatus,
    Chapter,
    ChapterStatus,
    OpenBookBlueprint,
    VolumePlan,
)
from mynovel.domain.repositories import get_latest_canon, list_chapters_for_book
import mynovel.workflows.chapter_pipeline as chapter_pipeline
from mynovel.workflows.chapter_pipeline import approve_chapter, run_chapter_pipeline
from mynovel.workflows.open_book import create_draft_book_from_blueprint, lock_canon_foundation


def test_accepting_blueprint_creates_locked_foundation_and_ten_chapters(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    blueprint = _blueprint()

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(
            session,
            blueprint,
            selected_title="长夜图书馆",
        )
        canon = get_latest_canon(session, book.id)
        chapters = list_chapters_for_book(session, book.id)

    assert book.status == BookStatus.CANON_LOCKED
    assert canon is not None
    assert canon.version == 1
    assert canon.content["book"]["title"] == "长夜图书馆"
    assert len(chapters) == 10
    assert chapters[0].title == "离开的召唤"
    assert chapters[0].status == ChapterStatus.PLANNED


def test_chapter_pipeline_requires_locked_foundation(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(
            session,
            _blueprint(),
            selected_title="长夜图书馆",
            lock_foundation=False,
        )
        chapter = list_chapters_for_book(session, book.id)[0]

        try:
            run_chapter_pipeline(session, chapter.id)
        except ValueError as error:
            message = str(error)
        else:
            message = ""

    assert "Trusted state must be locked" in message


def test_run_chapter_pipeline_prepares_human_review(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        lock_canon_foundation(session, book.id)
        chapter = list_chapters_for_book(session, book.id)[0]

        reviewed = run_chapter_pipeline(session, chapter.id)

    assert reviewed.status == ChapterStatus.AWAITING_REVIEW
    assert reviewed.plan["goal"]
    assert reviewed.context_package["trusted_state"]
    assert reviewed.context_package["volume_plan"]["core_conflict"]
    assert reviewed.draft_text
    assert reviewed.revised_text
    assert reviewed.audit_report["issues"]
    assert reviewed.state_delta["changes"]


def test_chapter_pipeline_uses_the_chapter_volume_plan(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        session.add(
            VolumePlan(
                book_id=book.id,
                volume_number=2,
                title="远行卷",
                core_conflict="莉拉离开幽谷，追查旧王朝远行线。",
            )
        )
        chapter = Chapter(
            book_id=book.id,
            number=11,
            title="远行之门",
            plan={"volume_number": 2, "goal": "莉拉踏出幽谷。"},
        )
        session.add(chapter)
        session.commit()
        session.refresh(chapter)

        reviewed = run_chapter_pipeline(session, chapter.id)

    assert reviewed.context_package["volume_plan"]["volume_number"] == 2
    assert reviewed.context_package["volume_plan"]["title"] == "远行卷"


def test_run_chapter_pipeline_prepares_state_delta_and_audit_for_result_first_review(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "review.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        lock_canon_foundation(session, book.id)
        chapter = list_chapters_for_book(session, book.id)[0]

        reviewed = run_chapter_pipeline(session, chapter.id)

    assert isinstance(reviewed.audit_report, dict)
    assert isinstance(reviewed.state_delta, dict)
    assert "issues" in reviewed.audit_report
    assert "changes" in reviewed.state_delta


def test_approve_chapter_writes_state_delta_to_latest_canon(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        lock_canon_foundation(session, book.id)
        chapter = list_chapters_for_book(session, book.id)[0]
        reviewed = run_chapter_pipeline(session, chapter.id)

        accepted = approve_chapter(session, reviewed.id, reviewer_note="可以进入连载队列。")
        canon = get_latest_canon(session, book.id)

    assert accepted.status == ChapterStatus.ACCEPTED
    assert accepted.final_text == accepted.revised_text
    assert accepted.reviewer_note == "可以进入连载队列。"
    assert canon is not None
    assert canon.version == 2
    assert canon.content["chapter_summaries"][0]["title"] == "离开的召唤"
    assert canon.content["state_history"][0]["chapter"] == 1
    for bucket in ("characters", "locations", "foreshadowing"):
        for item in canon.content.get(bucket, []):
            if isinstance(item, dict):
                assert "chapter_title" not in item
                assert "updated_at" not in item


def test_approve_chapter_does_not_write_low_information_state_items(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        lock_canon_foundation(session, book.id)
        chapter = list_chapters_for_book(session, book.id)[0]
        reviewed = run_chapter_pipeline(session, chapter.id)
        reviewed.state_delta = {
            "chapter": reviewed.number,
            "changes": [{"type": "状态变化", "target": "待确认", "change": "人物"}],
        }
        session.add(reviewed)
        session.commit()

        approve_chapter(session, reviewed.id)
        canon = get_latest_canon(session, book.id)

    assert canon is not None
    assert all(item.get("name") != "待确认" for item in canon.content.get("characters", []))


def test_chapter_context_package_excludes_canon_proposal_metadata(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(
            session,
            _blueprint(),
            selected_title="长夜图书馆",
            lock_foundation=False,
        )
        book.constraints = {
            **book.constraints,
            "_canon_proposal": {"last_revision": {"summary": "草稿"}},
        }
        session.add(book)
        canon = get_latest_canon(session, book.id or 0)
        assert canon is not None
        canon.content = {
            **canon.content,
            "_canon_proposal": {"should": "not enter context"},
        }
        session.add(canon)
        session.commit()
        lock_canon_foundation(session, book.id)
        chapter = list_chapters_for_book(session, book.id or 0)[0]

        reviewed = run_chapter_pipeline(session, chapter.id)

    context_text = str(reviewed.context_package)
    assert "_canon_proposal" not in context_text
    assert "last_revision" not in context_text


class _FixedEmbeddingClient:
    model = "embedding-test"

    def embed_text(self, text: str) -> list[float]:
        return [1.0, 0.0] if "莉拉" in text or "符号" in text else [0.5, 0.5]


def test_chapter_pipeline_adds_retrieved_context_from_embedding(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    embedder = _FixedEmbeddingClient()
    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        first = list_chapters_for_book(session, book.id)[0]
        reviewed = run_chapter_pipeline(session, first.id, embedding_client=embedder)
        approve_chapter(session, reviewed.id, embedding_client=embedder)
        second = list_chapters_for_book(session, book.id)[1]
        next_reviewed = run_chapter_pipeline(session, second.id, embedding_client=embedder)

    retrieved = next_reviewed.context_package["retrieved_context"]
    assert retrieved
    assert {"source_type", "source_id", "score", "text"} <= set(retrieved[0])


def test_chapter_pipeline_calls_lexical_retrieval_without_embedding_kwargs(
    tmp_path, monkeypatch
) -> None:
    calls = []

    def fake_retrieve_book_context(*args, **kwargs):
        calls.append((args, kwargs))
        return []

    monkeypatch.setattr(chapter_pipeline, "retrieve_book_context", fake_retrieve_book_context)
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = list_chapters_for_book(session, book.id)[0]
        run_chapter_pipeline(session, chapter.id, embedding_client=None)

    assert calls
    assert calls[0][1] == {}


def _blueprint() -> OpenBookBlueprint:
    return OpenBookBlueprint(
        id=1,
        idea="失忆少女在幽谷中寻找被抹去的王朝真相",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["长夜图书馆", "雾谷遗书"],
            "genre": "奇幻连载",
            "audience": "喜欢成长冒险的连载读者",
            "selling_points": ["每章揭开一条旧王朝线索", "角色关系随真相推进变化"],
            "protagonist": {"name": "莉拉", "hook": "失忆但能读懂古代符号"},
            "world": {"premise": "幽谷里散落着被抹去王朝的遗迹"},
            "central_conflict": "莉拉必须确认自己与旧王朝覆灭之间的关系。",
            "reader_promises": ["持续发现遗迹", "每章结尾留下新问题"],
            "chapter_directions": [
                {"title": "离开的召唤", "goal": "莉拉离开村庄，发现第一枚符号。"},
                {"title": "穿越迷雾", "goal": "进入幽谷，遭遇守夜人罗文。"},
                {"title": "隐秘小径", "goal": "找到通向废墟的道路。"},
                {"title": "废墟中的低语", "goal": "发现旧王朝留下的低语。"},
                {"title": "破碎石门", "goal": "开启第一处遗迹入口。"},
                {"title": "谷底深处", "goal": "确认幽谷中仍有人活动。"},
                {"title": "遗落的祠堂", "goal": "发现主角身世线索。"},
                {"title": "月影之约", "goal": "莉拉与罗文建立临时同盟。"},
                {"title": "守夜人", "goal": "揭示罗文的守护职责。"},
                {"title": "风声再起", "goal": "旧王朝敌人逼近。"},
            ],
        },
        raw_response="{}",
    )
