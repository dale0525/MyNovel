from __future__ import annotations

from pathlib import Path
from threading import Thread

from sqlmodel import Session

from mynovel.chapter_batch_payload import validate_chapter_batch_ids
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BookStatus, ChapterStatus, ProviderConfig, RunTrace, utc_now
from mynovel.domain.repositories import (
    get_book,
    get_chapter,
    get_latest_canon,
    list_chapters_for_book,
)
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
    chapter_ids: list[int],
    provider_config: ProviderConfig | None = None,
    *,
    start_background: bool = True,
) -> int:
    first_chapter_id = _mark_selected_batch_chapters_running(db_path, book_id, chapter_ids)
    if start_background:
        thread = Thread(
            target=_run_chapter_batch_job,
            args=(db_path, book_id, chapter_ids, provider_config),
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
        _assert_book_ready_for_chapter_production(
            session,
            chapter.book_id,
            missing_book_message="Chapter must belong to a book with trusted state.",
            missing_canon_message="Chapter must belong to a book with trusted state.",
        )
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


def _mark_selected_batch_chapters_running(
    db_path: Path,
    book_id: int,
    chapter_ids: list[int],
) -> int:
    selected_chapter_ids = validate_chapter_batch_ids(chapter_ids)
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        _assert_book_ready_for_chapter_production(
            session,
            book_id,
            missing_book_message="Book does not exist.",
            missing_canon_message="Trusted state must be locked before chapter production.",
        )
        chapters_by_id = {
            chapter.id: chapter
            for chapter in list_chapters_for_book(session, book_id)
            if chapter.id is not None
        }
        selected_chapters = []
        for chapter_id in selected_chapter_ids:
            chapter = chapters_by_id.get(chapter_id)
            if chapter is None:
                raise ValueError("Selected chapter does not belong to this book.")
            if chapter.status not in {ChapterStatus.PLANNED, ChapterStatus.NEEDS_REVISION}:
                raise ValueError("Selected chapter is not eligible for production.")
            selected_chapters.append(chapter)
        selected_chapters.sort(key=lambda chapter: chapter.number)
        for chapter in selected_chapters:
            chapter.status = ChapterStatus.RUNNING
            chapter.updated_at = utc_now()
            session.add(chapter)
        session.commit()
        first_chapter = selected_chapters[0]
        session.refresh(first_chapter)
        return first_chapter.id or selected_chapter_ids[0]


def _assert_book_ready_for_chapter_production(
    session: Session,
    book_id: int,
    *,
    missing_book_message: str,
    missing_canon_message: str,
) -> None:
    book = get_book(session, book_id)
    if book is None:
        raise ValueError(missing_book_message)
    canon = get_latest_canon(session, book_id)
    if canon is None:
        raise ValueError(missing_canon_message)
    if book.status == BookStatus.DRAFT:
        raise ValueError("Trusted state must be locked before chapter production.")


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
    chapter_ids: list[int],
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
                chapter_ids,
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
        error_message = _job_error_message(error)
        chapter.status = ChapterStatus.NEEDS_REVISION
        chapter.reviewer_note = f"生成失败：{error_message}"
        chapter.updated_at = utc_now()
        session.add(chapter)
        metadata: dict[str, object] = {
            "chapter": chapter.number,
            "status": chapter.status.value,
            "error_type": type(error).__name__,
            "error_message": error_message,
            "error_repr": repr(error),
        }
        failed_stage = getattr(error, "stage", None)
        if failed_stage:
            metadata["failed_stage"] = failed_stage
        response_format = getattr(error, "response_format", None)
        if response_format:
            metadata["response_format"] = response_format
        raw_response_text = getattr(error, "raw_response_text", None)
        if raw_response_text:
            metadata["raw_response_text"] = raw_response_text
        prompt_messages = getattr(error, "messages", None)
        if prompt_messages:
            metadata["prompt_messages"] = prompt_messages
        session.add(
            RunTrace(
                book_id=chapter.book_id,
                stage="修复失败",
                cost={"estimated": 0},
                metadata_=metadata,
            )
        )
        session.commit()


def _job_error_message(error: Exception) -> str:
    message = str(error).strip()
    return message or type(error).__name__


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
