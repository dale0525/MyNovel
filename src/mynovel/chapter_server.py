from __future__ import annotations

from pathlib import Path
from threading import Thread

from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BookStatus, ChapterStatus, ProviderConfig, utc_now
from mynovel.domain.repositories import get_book, get_chapter, get_latest_canon, list_chapters_for_book
from mynovel.llm.openai_compatible import OpenAICompatibleClient
from mynovel.workflows.chapter_batch import run_chapter_batch
from mynovel.workflows.chapter_pipeline import (
    OpenAIChapterModelClient,
    repair_chapter_with_ai,
    run_chapter_pipeline,
)


def queue_chapter_run(
    db_path: Path,
    chapter_id: int,
    provider_config: ProviderConfig | None = None,
    *,
    start_background: bool = True,
) -> int:
    queued_chapter_id = _mark_chapter_running(db_path, chapter_id)
    if start_background:
        thread = Thread(
            target=_run_chapter_job,
            args=(db_path, queued_chapter_id, provider_config),
            daemon=True,
        )
        thread.start()
    return queued_chapter_id


def queue_chapter_repair(
    db_path: Path,
    chapter_id: int,
    provider_config: ProviderConfig | None = None,
    reviewer_note: str | None = None,
    *,
    start_background: bool = True,
) -> int:
    queued_chapter_id = _mark_chapter_repair_running(db_path, chapter_id, reviewer_note)
    if start_background:
        thread = Thread(
            target=_run_chapter_repair_job,
            args=(db_path, queued_chapter_id, provider_config, reviewer_note),
            daemon=True,
        )
        thread.start()
    return queued_chapter_id


def queue_chapter_batch_run(
    db_path: Path,
    book_id: int,
    limit: int,
    provider_config: ProviderConfig | None = None,
    *,
    start_background: bool = True,
) -> int:
    first_chapter_id = _mark_next_batch_chapter_running(db_path, book_id)
    if start_background:
        thread = Thread(
            target=_run_chapter_batch_job,
            args=(db_path, book_id, limit, provider_config),
            daemon=True,
        )
        thread.start()
    return first_chapter_id


def _mark_chapter_running(db_path: Path, chapter_id: int) -> int:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        chapter = get_chapter(session, chapter_id)
        if chapter is None or chapter.id is None:
            raise ValueError("Chapter does not exist.")
        book = get_book(session, chapter.book_id)
        canon = get_latest_canon(session, chapter.book_id)
        if book is None or canon is None:
            raise ValueError("Chapter must belong to a book with trusted state.")
        if book.status == BookStatus.DRAFT:
            raise ValueError("Trusted state must be locked before chapter production.")
        if chapter.status in {ChapterStatus.AWAITING_REVIEW, ChapterStatus.ACCEPTED}:
            raise ValueError("Chapter is not eligible for production.")
        if chapter.status != ChapterStatus.RUNNING:
            chapter.status = ChapterStatus.RUNNING
            chapter.updated_at = utc_now()
            session.add(chapter)
            session.commit()
            session.refresh(chapter)
        return chapter.id


def _mark_chapter_repair_running(
    db_path: Path,
    chapter_id: int,
    reviewer_note: str | None,
) -> int:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        chapter = get_chapter(session, chapter_id)
        if chapter is None or chapter.id is None:
            raise ValueError("Chapter does not exist.")
        if chapter.status not in {ChapterStatus.AWAITING_REVIEW, ChapterStatus.NEEDS_REVISION}:
            raise ValueError("Only review-stage chapters can be repaired.")
        chapter.status = ChapterStatus.RUNNING
        note = reviewer_note.strip() if reviewer_note else ""
        chapter.reviewer_note = f"AI 修复中：{note}" if note else "AI 修复中。"
        chapter.updated_at = utc_now()
        session.add(chapter)
        session.commit()
        session.refresh(chapter)
        return chapter.id


def _mark_next_batch_chapter_running(db_path: Path, book_id: int) -> int:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = get_book(session, book_id)
        if book is None:
            raise ValueError("Book does not exist.")
        for chapter in list_chapters_for_book(session, book_id):
            if chapter.status not in {
                ChapterStatus.PLANNED,
                ChapterStatus.NEEDS_REVISION,
                ChapterStatus.RUNNING,
            }:
                continue
            if chapter.id is None:
                raise ValueError("Chapter must be persisted before production.")
            chapter.status = ChapterStatus.RUNNING
            chapter.updated_at = utc_now()
            session.add(chapter)
            session.commit()
            session.refresh(chapter)
            return chapter.id
    raise ValueError("No chapter is eligible for batch production.")


def _run_chapter_job(
    db_path: Path,
    chapter_id: int,
    provider_config: ProviderConfig | None,
) -> None:
    model_client, model_name = _chapter_model_client_from_provider_config(provider_config)
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    try:
        with Session(engine) as session:
            run_chapter_pipeline(
                session,
                chapter_id,
                model_client=model_client,
                model_name=model_name,
            )
    except Exception as error:  # noqa: BLE001
        _mark_chapter_job_failed(db_path, chapter_id, error)


def _run_chapter_repair_job(
    db_path: Path,
    chapter_id: int,
    provider_config: ProviderConfig | None,
    reviewer_note: str | None,
) -> None:
    model_client, model_name = chapter_model_client_from_provider_config(provider_config)
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    try:
        with Session(engine) as session:
            repair_chapter_with_ai(
                session,
                chapter_id,
                model_client=model_client,
                model_name=model_name,
                reviewer_note=reviewer_note,
            )
    except Exception as error:  # noqa: BLE001
        _mark_chapter_job_failed(db_path, chapter_id, error)


def _run_chapter_batch_job(
    db_path: Path,
    book_id: int,
    limit: int,
    provider_config: ProviderConfig | None,
) -> None:
    model_client, model_name = chapter_model_client_from_provider_config(provider_config)
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    try:
        with Session(engine) as session:
            run_chapter_batch(
                session,
                book_id,
                limit,
                model_client=model_client,
                model_name=model_name,
            )
    except Exception as error:  # noqa: BLE001
        first_running = _first_running_chapter_id(db_path, book_id)
        if first_running is not None:
            _mark_chapter_job_failed(db_path, first_running, error)


def _first_running_chapter_id(db_path: Path, book_id: int) -> int | None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        for chapter in list_chapters_for_book(session, book_id):
            if chapter.status == ChapterStatus.RUNNING and chapter.id is not None:
                return chapter.id
    return None


def _mark_chapter_job_failed(db_path: Path, chapter_id: int, error: Exception) -> None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        chapter = get_chapter(session, chapter_id)
        if chapter is None:
            return
        chapter.status = ChapterStatus.NEEDS_REVISION
        chapter.reviewer_note = f"生成失败：{error}"
        chapter.updated_at = utc_now()
        session.add(chapter)
        session.commit()


def chapter_model_client_from_provider_config(
    provider_config: ProviderConfig | None,
) -> tuple[OpenAIChapterModelClient | None, str | None]:
    if (
        provider_config is None
        or not provider_config.llm_base_url.strip()
        or not provider_config.llm_model.strip()
    ):
        return None, None
    return (
        OpenAIChapterModelClient(
            OpenAICompatibleClient(
                base_url=provider_config.llm_base_url,
                api_key=provider_config.llm_api_key or "",
            ),
            provider_config.llm_model,
        ),
        provider_config.llm_model,
    )


_chapter_model_client_from_provider_config = chapter_model_client_from_provider_config
