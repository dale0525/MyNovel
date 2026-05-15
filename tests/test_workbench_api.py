from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path

from sqlmodel import Session

from mynovel.api_routes import dispatch_api_get
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import Book, ProviderConfig, ProviderConfigValidation
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
    }


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
