from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, OpenBookBlueprint
from mynovel.domain.repositories import list_vector_entries_for_book
from mynovel.workflows.chapter_pipeline import approve_chapter, run_chapter_pipeline
from mynovel.workflows.open_book import create_draft_book_from_blueprint
from mynovel.workflows.retrieval import index_text, search_book_context


def test_local_retrieval_index_ranks_matching_context(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="幽谷回声")
        index_text(
            session,
            book_id=book.id,
            source_type="note",
            source_id="symbol",
            text="莉拉的掌心符号会在靠近旧王朝遗迹时发热。",
            metadata={"kind": "伏笔"},
        )
        index_text(
            session,
            book_id=book.id,
            source_type="note",
            source_id="market",
            text="集市上的商人正在售卖普通草药。",
            metadata={"kind": "地点"},
        )

        results = search_book_context(session, book.id, "符号 发热 遗迹")

    assert results[0].source_id == "symbol"
    assert "符号" in results[0].text


def test_accepted_chapter_updates_structured_state_and_rebuildable_index(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="幽谷回声")
        chapter = run_chapter_pipeline(session, _first_chapter_id(session, book.id))
        chapter.state_delta = {
            "chapter": 1,
            "changes": [
                {"type": "人物状态", "target": "莉拉", "change": "主动追查真相"},
                {"type": "地点", "target": "幽谷石门", "change": "首次开启"},
                {"type": "关系", "target": "莉拉 / 罗文", "change": "临时同盟"},
                {"type": "伏笔", "target": "第二枚符号", "change": "远处回应"},
                {"type": "资源", "target": "旧王朝地图", "change": "获得残片"},
            ],
        }
        session.add(chapter)
        session.commit()

        accepted = approve_chapter(session, chapter.id)
        latest_entries = list_vector_entries_for_book(session, book.id)

    assert accepted.status.value == "accepted"
    latest_canon = latest_entries[-1].metadata_["trusted_state_version"]
    assert latest_canon == 2
    indexed_text = "\n".join(entry.text for entry in latest_entries)
    assert "幽谷石门" in indexed_text
    assert "旧王朝地图" in indexed_text


def _first_chapter_id(session: Session, book_id: int) -> int:
    from mynovel.domain.repositories import list_chapters_for_book

    chapter_id = list_chapters_for_book(session, book_id)[0].id
    assert chapter_id is not None
    return chapter_id


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
            "chapter_directions": [{"title": "离开的召唤", "goal": "发现第一枚符号"}],
        },
        raw_response="{}",
    )
