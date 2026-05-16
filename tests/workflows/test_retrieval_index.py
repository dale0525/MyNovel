import math

from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, OpenBookBlueprint
from mynovel.domain.repositories import list_vector_entries_for_book
from mynovel.workflows.chapter_pipeline import approve_chapter, run_chapter_pipeline
from mynovel.workflows.open_book import create_draft_book_from_blueprint
from mynovel.workflows.retrieval import index_text, retrieve_book_context, search_book_context


def test_local_retrieval_index_ranks_matching_context(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
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


def test_model_retrieval_ranks_by_cosine_similarity(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        index_text(
            session,
            book.id,
            "note",
            "symbol",
            "符号发热",
            embedding_vector=[1.0, 0.0],
            embedding_model="embedding-test",
        )
        index_text(
            session,
            book.id,
            "note",
            "market",
            "普通草药",
            embedding_vector=[0.0, 1.0],
            embedding_model="embedding-test",
        )

        results = retrieve_book_context(
            session,
            book.id,
            "符号",
            query_embedding=[0.9, 0.1],
            embedding_model="embedding-test",
            top_k=2,
        )

    assert [result.source_id for result in results] == ["symbol", "market"]
    assert results[0].score > results[1].score


def test_model_retrieval_falls_back_to_lexical_when_model_candidates_unavailable(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        index_text(
            session,
            book.id,
            "note",
            "old",
            "旧模型",
            embedding_vector=[1.0, 0.0],
            embedding_model="old",
        )
        results = retrieve_book_context(
            session,
            book.id,
            "旧模型",
            query_embedding=[1.0, 0.0],
            embedding_model="new",
        )

    assert [result.source_id for result in results] == ["old"]
    assert results[0].metadata["embedding_model"] == "old"


def test_model_retrieval_fallback_scores_vector_entries_from_text(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        index_text(
            session,
            book.id,
            "note",
            "old",
            "旧模型",
            embedding_vector=[1.0, 0.0],
            embedding_model="old",
        )
        results = retrieve_book_context(
            session,
            book.id,
            "旧",
            query_embedding=[1.0, 0.0],
            embedding_model="new",
        )

    assert [result.source_id for result in results] == ["old"]


def test_retrieval_budget_truncates_high_score_oversized_context(
    tmp_path,
) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        index_text(
            session,
            book.id,
            "note",
            "long",
            "符号" * 20,
            embedding_vector=[1.0, 0.0],
            embedding_model="embedding-test",
        )
        index_text(
            session,
            book.id,
            "note",
            "small",
            "短符号",
            embedding_vector=[0.9, 0.1],
            embedding_model="embedding-test",
        )

        results = retrieve_book_context(
            session,
            book.id,
            "符号",
            query_embedding=[1.0, 0.0],
            embedding_model="embedding-test",
            top_k=2,
            character_budget=4,
        )

    assert [result.source_id for result in results] == ["long"]
    assert results[0].text == "符号符号"


def test_retrieval_budget_exact_exhaustion_does_not_add_empty_context(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        index_text(
            session,
            book.id,
            "note",
            "first",
            "符号符号",
            embedding_vector=[1.0, 0.0],
            embedding_model="embedding-test",
        )
        index_text(
            session,
            book.id,
            "note",
            "second",
            "短符号",
            embedding_vector=[0.9, 0.1],
            embedding_model="embedding-test",
        )

        results = retrieve_book_context(
            session,
            book.id,
            "符号",
            query_embedding=[1.0, 0.0],
            embedding_model="embedding-test",
            top_k=2,
            character_budget=4,
        )

    assert [result.source_id for result in results] == ["first"]
    assert results[0].text == "符号符号"
    assert all(result.text for result in results)


def test_index_text_stores_invalid_embedding_vector_as_lexical(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    invalid_vectors = [[True], [], [math.nan], [math.inf]]

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        entries = [
            index_text(
                session,
                book.id,
                "note",
                f"invalid-{index}",
                "符号发热",
                embedding_vector=invalid_vector,
                embedding_model="embedding-test",
                embedding_error="upstream embedding failed",
            )
            for index, invalid_vector in enumerate(invalid_vectors)
        ]

        for entry in entries:
            assert entry.metadata_["embedding_kind"] == "lexical"
            assert entry.metadata_["embedding_error"] == "upstream embedding failed"
            assert "embedding_model" not in entry.metadata_
            assert isinstance(entry.embedding, dict)
            assert "符号" in entry.embedding


def test_accepted_chapter_updates_structured_state_and_rebuildable_index(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
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
