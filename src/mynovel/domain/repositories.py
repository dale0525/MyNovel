from sqlmodel import Session, select
from typing import Any, cast

from mynovel.domain.models import (
    Book,
    Canon,
    Chapter,
    DeconstructionStudy,
    OpenBookBlueprint,
    ProviderConfig,
    QualitySnapshot,
    RunTrace,
    StyleAsset,
    VectorEntry,
    VolumePlan,
    utc_now,
)


def _orm(value: object) -> Any:
    return cast(Any, value)


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
        .order_by(_orm(Canon.version).desc(), _orm(Canon.created_at).desc())
        .limit(1)
    )
    return session.exec(statement).first()


def add_volume_plan(session: Session, volume_plan: VolumePlan) -> VolumePlan:
    session.add(volume_plan)
    session.commit()
    session.refresh(volume_plan)
    return volume_plan


def list_volume_plans_for_book(session: Session, book_id: int) -> list[VolumePlan]:
    statement = (
        select(VolumePlan)
        .where(VolumePlan.book_id == book_id)
        .order_by(_orm(VolumePlan.volume_number), _orm(VolumePlan.id))
    )
    return list(session.exec(statement))


def get_active_volume_plan(session: Session, book_id: int) -> VolumePlan | None:
    statement = (
        select(VolumePlan)
        .where(VolumePlan.book_id == book_id)
        .order_by(_orm(VolumePlan.volume_number))
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
    statement = select(Chapter).where(Chapter.book_id == book_id).order_by(_orm(Chapter.number))
    return list(session.exec(statement))


def add_run_trace(session: Session, trace: RunTrace) -> RunTrace:
    session.add(trace)
    session.commit()
    session.refresh(trace)
    return trace


def list_run_traces_for_book(session: Session, book_id: int) -> list[RunTrace]:
    statement = (
        select(RunTrace).where(RunTrace.book_id == book_id).order_by(_orm(RunTrace.created_at))
    )
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
        .order_by(_orm(VectorEntry.created_at), _orm(VectorEntry.id))
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
        .order_by(_orm(VectorEntry.created_at), _orm(VectorEntry.id))
    )
    return list(session.exec(statement))


def add_style_asset(session: Session, asset: StyleAsset) -> StyleAsset:
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


def list_style_assets_for_book(session: Session, book_id: int) -> list[StyleAsset]:
    statement = (
        select(StyleAsset)
        .where(StyleAsset.book_id == book_id)
        .order_by(_orm(StyleAsset.created_at), _orm(StyleAsset.id))
    )
    return list(session.exec(statement))


def add_deconstruction_study(
    session: Session,
    study: DeconstructionStudy,
) -> DeconstructionStudy:
    session.add(study)
    session.commit()
    session.refresh(study)
    return study


def list_deconstruction_studies_for_book(
    session: Session,
    book_id: int,
) -> list[DeconstructionStudy]:
    statement = (
        select(DeconstructionStudy)
        .where(DeconstructionStudy.book_id == book_id)
        .order_by(_orm(DeconstructionStudy.created_at), _orm(DeconstructionStudy.id))
    )
    return list(session.exec(statement))


def add_quality_snapshot(session: Session, snapshot: QualitySnapshot) -> QualitySnapshot:
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return snapshot


def list_quality_snapshots_for_book(session: Session, book_id: int) -> list[QualitySnapshot]:
    statement = (
        select(QualitySnapshot)
        .where(QualitySnapshot.book_id == book_id)
        .order_by(_orm(QualitySnapshot.created_at), _orm(QualitySnapshot.id))
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
    statement = select(OpenBookBlueprint).order_by(_orm(OpenBookBlueprint.version).desc())
    return list(session.exec(statement))
