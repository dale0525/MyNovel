from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path

from sqlmodel import Session

from mynovel.api_routes import dispatch_api_get
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import (
    Book,
    BlueprintStatus,
    Chapter,
    ChapterStatus,
    OpenBookBlueprint,
    ProviderConfig,
    ProviderConfigValidation,
)
from mynovel.domain.repositories import save_provider_config, save_provider_config_validation
from mynovel.provider_config_validation import provider_model_fingerprint


def test_bootstrap_opens_workbench_with_valid_saved_provider(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    config = _provider_config()
    _save_provider_state(
        db_path,
        config,
        ProviderConfigValidation(
            llm_fingerprint=provider_model_fingerprint(config, "llm"),
            embedding_fingerprint=provider_model_fingerprint(config, "embedding"),
            rerank_fingerprint=provider_model_fingerprint(config, "rerank"),
        ),
    )

    response = dispatch_api_get("/api/app/bootstrap", "", db_path)

    assert response.status == HTTPStatus.OK
    assert response.body["providerConfigured"] is True
    assert response.body["initialRoute"] == "/"


def test_bootstrap_recovers_interrupted_running_chapters(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    config = _provider_config()
    _save_provider_state(
        db_path,
        config,
        ProviderConfigValidation(
            llm_fingerprint=provider_model_fingerprint(config, "llm"),
            embedding_fingerprint=provider_model_fingerprint(config, "embedding"),
            rerank_fingerprint=provider_model_fingerprint(config, "rerank"),
        ),
    )
    engine = create_engine_for_path(db_path)
    with Session(engine) as session:
        book = Book(title="长夜图书馆", genre="奇幻", audience="成人")
        session.add(book)
        session.commit()
        session.refresh(book)
        chapter = Chapter(
            book_id=book.id or 0,
            number=1,
            title="断点",
            status=ChapterStatus.RUNNING,
        )
        session.add(chapter)
        session.commit()
        chapter_id = chapter.id or 0

    response = dispatch_api_get("/api/app/bootstrap", "", db_path)

    assert response.status == HTTPStatus.OK
    with Session(engine) as session:
        chapter = session.get(Chapter, chapter_id)
    assert chapter is not None
    assert chapter.status == ChapterStatus.NEEDS_REVISION
    assert chapter.reviewer_note == "生成中断：应用已重启，可重新生成本章。"


def test_books_returns_recent_books(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = Book(title="长夜图书馆", genre="奇幻", audience="男频")
        session.add(book)
        session.commit()
        session.refresh(book)

    response = dispatch_api_get("/api/books", "", db_path)

    assert response.status == HTTPStatus.OK
    assert response.body == {
        "books": [
            {
                "id": book.id,
                "title": "长夜图书馆",
                "genre": "奇幻",
                "audience": "男频",
                "status": "draft",
                "premise": None,
            },
        ],
        "blueprints": [],
    }


def test_books_returns_open_book_blueprints_without_acceptance(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        blueprint = OpenBookBlueprint(
            idea="一句灵感：失意档案员重建禁书图书馆",
            version=2,
            status=BlueprintStatus.SUCCEEDED,
            instruction="主角更主动",
            content={"title_options": ["长夜档案"]},
        )
        session.add(blueprint)
        session.commit()
        session.refresh(blueprint)

    response = dispatch_api_get("/api/books", "", db_path)

    assert response.status == HTTPStatus.OK
    assert response.body["books"] == []
    assert response.body["blueprints"] == [
        {
            "id": blueprint.id,
            "parentId": None,
            "version": 2,
            "status": "succeeded",
            "title": "长夜档案",
            "idea": "一句灵感：失意档案员重建禁书图书馆",
            "instruction": "主角更主动",
            "createdAt": blueprint.created_at.isoformat(),
        }
    ]


def test_books_returns_latest_20_with_stable_id_tiebreaker(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        books = [
            Book(
                title=f"Book {index:02d}",
                genre="奇幻",
                audience="男频",
                created_at=created_at,
            )
            for index in range(1, 22)
        ]
        session.add_all(books)
        session.commit()
        ids = [book.id for book in books]

    response = dispatch_api_get("/api/books", "", db_path)

    assert response.status == HTTPStatus.OK
    assert [book["id"] for book in response.body["books"]] == list(reversed(ids[1:]))
    assert response.body["blueprints"] == []


def test_book_detail_returns_single_book(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = Book(
            title="星港遗梦",
            genre="科幻",
            audience="成人",
            premise="领航员追查失落星港的真相。",
        )
        session.add(book)
        session.commit()
        session.refresh(book)

    response = dispatch_api_get(f"/api/books/{book.id}", "", db_path)

    assert response.status == HTTPStatus.OK
    assert response.body == {
        "book": {
            "id": book.id,
            "title": "星港遗梦",
            "genre": "科幻",
            "audience": "成人",
            "status": "draft",
            "premise": "领航员追查失落星港的真相。",
        },
        "wordTargets": {
            "targetWordCount": 120000,
            "chapterWordCount": 2800,
        },
        "chapters": [],
        "latestCanon": None,
        "runTraces": [],
        "volumePlans": [],
    }


def test_book_detail_missing_returns_json_404(tmp_path: Path) -> None:
    response = dispatch_api_get("/api/books/404", "", tmp_path / "dev.sqlite")

    assert response.status == HTTPStatus.NOT_FOUND
    assert response.body["error"]["code"] == "book_not_found"


def _provider_config() -> ProviderConfig:
    return ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_api_key="sk-test",
        llm_model="gpt-test",
        embedding_base_url="https://api.example.test/v1",
        embedding_model="text-embedding-test",
        rerank_base_url="https://rerank.example.test/v1",
        rerank_model="rerank-test",
    )


def _save_provider_state(
    db_path: Path,
    config: ProviderConfig,
    validation: ProviderConfigValidation,
) -> None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        save_provider_config(session, config)
        save_provider_config_validation(session, validation)
