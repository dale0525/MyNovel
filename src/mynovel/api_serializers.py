from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from sqlmodel import Session, select

from mynovel.blueprint_content import public_blueprint_content
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import Book, OpenBookBlueprint, ProviderConfig, ProviderConfigValidation
from mynovel.domain.repositories import get_provider_config, get_provider_config_validation
from mynovel.provider_config_validation import provider_model_fingerprint


def app_bootstrap_payload(db_path: Path) -> dict[str, Any]:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        configured = is_provider_config_validated(
            get_provider_config(session),
            get_provider_config_validation(session),
        )
    return {"providerConfigured": configured, "initialRoute": "/" if configured else "/setup", "message": None}


def book_payload(book: Book) -> dict[str, Any]:
    return {
        "id": book.id,
        "title": book.title,
        "genre": book.genre,
        "audience": book.audience,
        "status": book.status.value,
        "premise": book.premise,
    }


def blueprint_payload(blueprint: OpenBookBlueprint) -> dict[str, Any]:
    return {
        "id": blueprint.id,
        "parentId": blueprint.parent_id,
        "idea": blueprint.idea,
        "version": blueprint.version,
        "status": blueprint.status.value,
        "instruction": blueprint.instruction,
        "content": public_blueprint_content(blueprint.content),
        "parseError": blueprint.parse_error,
        "errorMessage": blueprint.error_message,
    }


def books_payload(db_path: Path) -> dict[str, Any]:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        books = list(
            session.exec(
                select(Book)
                .order_by(cast(Any, Book.created_at).desc(), cast(Any, Book.id).desc())
                .limit(20)
            )
        )
    return {"books": [book_payload(book) for book in books]}


def is_provider_config_validated(
    config: ProviderConfig | None,
    validation: ProviderConfigValidation | None,
) -> bool:
    if config is None or validation is None:
        return False
    return (
        validation.llm_fingerprint == provider_model_fingerprint(config, "llm")
        and validation.embedding_fingerprint == provider_model_fingerprint(config, "embedding")
        and validation.rerank_fingerprint == provider_model_fingerprint(config, "rerank")
    )
