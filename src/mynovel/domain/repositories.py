from sqlmodel import Session, select

from mynovel.domain.models import (
    Book,
    Canon,
    Chapter,
    OpenBookBlueprint,
    ProviderConfig,
    RunTrace,
    VectorEntry,
    utc_now,
)


def add_book(session: Session, book: Book) -> Book:
    session.add(book)
    session.commit()
    session.refresh(book)
    return book


def get_book(session: Session, book_id: int) -> Book | None:
    return session.get(Book, book_id)


def add_canon(session: Session, canon: Canon) -> Canon:
    session.add(canon)
    session.commit()
    session.refresh(canon)
    return canon


def get_latest_canon(session: Session, book_id: int) -> Canon | None:
    statement = (
        select(Canon)
        .where(Canon.book_id == book_id)
        .order_by(Canon.version.desc(), Canon.created_at.desc())
        .limit(1)
    )
    return session.exec(statement).first()


def add_chapter(session: Session, chapter: Chapter) -> Chapter:
    session.add(chapter)
    session.commit()
    session.refresh(chapter)
    return chapter


def get_chapter(session: Session, chapter_id: int) -> Chapter | None:
    return session.get(Chapter, chapter_id)


def list_chapters_for_book(session: Session, book_id: int) -> list[Chapter]:
    statement = select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.number)
    return list(session.exec(statement))


def add_run_trace(session: Session, trace: RunTrace) -> RunTrace:
    session.add(trace)
    session.commit()
    session.refresh(trace)
    return trace


def list_run_traces_for_book(session: Session, book_id: int) -> list[RunTrace]:
    statement = select(RunTrace).where(RunTrace.book_id == book_id).order_by(RunTrace.created_at)
    return list(session.exec(statement))


def add_vector_entry(session: Session, entry: VectorEntry) -> VectorEntry:
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def list_vector_entries_for_book(session: Session, book_id: int) -> list[VectorEntry]:
    statement = (
        select(VectorEntry)
        .where(VectorEntry.book_id == book_id)
        .order_by(VectorEntry.created_at, VectorEntry.id)
    )
    return list(session.exec(statement))


def list_vector_entries_for_source(
    session: Session,
    book_id: int,
    source_type: str,
    source_id: str,
) -> list[VectorEntry]:
    statement = (
        select(VectorEntry)
        .where(
            VectorEntry.book_id == book_id,
            VectorEntry.source_type == source_type,
            VectorEntry.source_id == source_id,
        )
        .order_by(VectorEntry.created_at, VectorEntry.id)
    )
    return list(session.exec(statement))


def get_provider_config(session: Session) -> ProviderConfig | None:
    return session.get(ProviderConfig, 1)


def save_provider_config(session: Session, config: ProviderConfig) -> ProviderConfig:
    existing = get_provider_config(session)
    if existing is None:
        config.id = 1
        session.add(config)
        session.commit()
        session.refresh(config)
        return config

    existing.llm_base_url = config.llm_base_url
    existing.llm_api_key = config.llm_api_key
    existing.llm_model = config.llm_model
    existing.embedding_use_llm_credentials = config.embedding_use_llm_credentials
    existing.embedding_base_url = config.embedding_base_url
    existing.embedding_api_key = config.embedding_api_key
    existing.embedding_model = config.embedding_model
    existing.rerank_use_llm_credentials = config.rerank_use_llm_credentials
    existing.rerank_base_url = config.rerank_base_url
    existing.rerank_api_key = config.rerank_api_key
    existing.rerank_model = config.rerank_model
    existing.updated_at = utc_now()
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


def add_open_book_blueprint(session: Session, blueprint: OpenBookBlueprint) -> OpenBookBlueprint:
    session.add(blueprint)
    session.commit()
    session.refresh(blueprint)
    return blueprint


def get_open_book_blueprint(session: Session, blueprint_id: int) -> OpenBookBlueprint | None:
    return session.get(OpenBookBlueprint, blueprint_id)


def list_open_book_blueprints(session: Session) -> list[OpenBookBlueprint]:
    statement = select(OpenBookBlueprint).order_by(OpenBookBlueprint.version.desc())
    return list(session.exec(statement))
