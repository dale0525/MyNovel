from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any

from sqlmodel import Session

from mynovel.api_serializers import blueprint_payload, book_detail_payload, chapter_review_payload
from mynovel.blueprint_content import public_blueprint_content
from mynovel.blueprint_jobs import reset_blueprint_for_retry
from mynovel.blueprint_revision import create_revision_blueprint_job, revision_notes_from_form
from mynovel.chapter_batch_payload import parse_chapter_batch_ids
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, ProviderConfig, utc_now
from mynovel.domain.repositories import (
    get_open_book_blueprint,
    get_provider_config,
)
from mynovel.llm.openai_compatible import ChatRequest, OpenAICompatibleClient
from mynovel.provider_config_status import is_provider_config_complete
from mynovel.workflows.chapter_batch import run_chapter_batch
from mynovel.chapter_server import (
    queue_chapter_batch_run,
    queue_chapter_repair,
    queue_chapter_run,
)
from mynovel.workflows.chapter_pipeline import repair_chapter_with_ai, run_chapter_pipeline
from mynovel.workflows.open_book_blueprint import (
    build_blueprint_messages,
    create_blueprint_job,
    parse_blueprint_json,
)
from mynovel.workflows.volume_planning import generate_volume_outline, revise_volume_outline
from mynovel.word_targets import book_idea_from_form

StreamEvent = dict[str, Any]
EmitEvent = Callable[[StreamEvent], None]


class OpenAIStreamingCompleteClient:
    def __init__(self, provider_config: ProviderConfig, temperature: float = 0.7) -> None:
        self.model = provider_config.llm_model
        self.temperature = temperature
        self.client = OpenAICompatibleClient(
            base_url=provider_config.llm_base_url,
            api_key=provider_config.llm_api_key or "",
        )

    def stream_complete(
        self,
        stage: str,
        messages: list[dict[str, str]],
        response_format: str,
    ) -> Iterator[str]:
        extra = {"response_format": {"type": "json_object"}} if response_format == "json" else None
        yield from self.client.stream_chat_content(
            ChatRequest(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                extra=extra,
            )
        )


class EventingCompleteClient:
    def __init__(
        self,
        source_client,
        emit: EmitEvent,
        *,
        stage_labels: dict[str, str] | None = None,
    ) -> None:
        self.source_client = source_client
        self.emit = emit
        self.stage_labels = stage_labels or {}

    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        self.emit(
            {
                "type": "stage",
                "stage": stage,
                "message": self.stage_labels.get(stage, f"{stage} 处理中"),
            }
        )
        parts: list[str] = []
        stream_complete = getattr(self.source_client, "stream_complete", None)
        if callable(stream_complete):
            for chunk in stream_complete(stage, messages, response_format):
                if not isinstance(chunk, str) or not chunk:
                    continue
                parts.append(chunk)
                self.emit({"type": "chunk", "stage": stage, "text": chunk})
        else:
            chunk = self.source_client.complete(stage, messages, response_format)
            parts.append(chunk)
            self.emit({"type": "chunk", "stage": stage, "text": chunk})
        return "".join(parts)


def stream_create_open_book_blueprint(
    db_path: Path,
    body: dict[str, Any],
    *,
    model_client=None,
) -> Iterator[StreamEvent]:
    provider_config = None if model_client is not None else _complete_provider_config(db_path)
    if model_client is None and provider_config is None:
        yield _failed("请先完成模型连接验证。")
        return
    idea = book_idea_from_form(_string_form(body))
    if not idea:
        yield _failed("请先写下故事灵感。")
        return

    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        blueprint = create_blueprint_job(session, idea=idea, version=1, instruction=None, parent_id=None)
        blueprint_id = blueprint.id
    if blueprint_id is None:
        yield _failed("蓝图任务创建失败。")
        return
    yield from _stream_blueprint_job(db_path, blueprint_id, provider_config, model_client)


def stream_retry_blueprint(
    db_path: Path,
    blueprint_id: int,
    *,
    model_client=None,
) -> Iterator[StreamEvent]:
    provider_config = None if model_client is not None else _complete_provider_config(db_path)
    if model_client is None and provider_config is None:
        yield _failed("请先完成模型连接验证。")
        return
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        blueprint = get_open_book_blueprint(session, blueprint_id)
        if blueprint is None:
            yield _failed("蓝图不存在。")
            return
        if blueprint.status != BlueprintStatus.FAILED:
            yield _failed("只有失败的蓝图可以重试。")
            return
        reset_blueprint_for_retry(session, blueprint)
    yield from _stream_blueprint_job(db_path, blueprint_id, provider_config, model_client)


def stream_revise_blueprint(
    db_path: Path,
    blueprint_id: int,
    body: dict[str, Any],
    *,
    model_client=None,
) -> Iterator[StreamEvent]:
    provider_config = None if model_client is not None else _complete_provider_config(db_path)
    if model_client is None and provider_config is None:
        yield _failed("请先完成模型连接验证。")
        return
    form = _string_form(
        {
            **body,
            "blueprint_id": blueprint_id,
            "revision_notes": body.get("revisionNotes", body.get("revision_notes", "")),
            "revision_preset": body.get("revisionPreset", body.get("revision_preset", "")),
        }
    )
    revision_notes = revision_notes_from_form(form)
    if not revision_notes:
        yield _failed("请填写修订方向。")
        return

    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        parent = get_open_book_blueprint(session, blueprint_id)
        if parent is None:
            yield _failed("蓝图不存在。")
            return
        if parent.status != BlueprintStatus.SUCCEEDED:
            yield _failed("只有已生成的蓝图可以修订。")
            return
        try:
            revision = create_revision_blueprint_job(session, form, [], revision_notes)
        except ValueError:
            yield _failed("蓝图不存在。")
            return
        revision_id = revision.id
    if revision_id is None:
        yield _failed("蓝图修订任务创建失败。")
        return
    yield from _stream_blueprint_job(db_path, revision_id, provider_config, model_client)


def stream_run_chapter(
    db_path: Path,
    chapter_id: int,
    *,
    model_client=None,
    provider_config: ProviderConfig | None = None,
) -> Iterator[StreamEvent]:
    def worker(emit: EmitEvent) -> None:
        emit({"type": "started", "message": "AI 已开始生成章节。"})
        queued_chapter_id = queue_chapter_run(db_path, chapter_id, provider_config, start_background=False)
        with Session(create_engine_for_path(db_path)) as session:
            run_chapter_pipeline(
                session,
                queued_chapter_id,
                model_client=_eventing_chapter_client(db_path, model_client, provider_config, emit),
                model_name=_model_name(model_client, provider_config),
            )
        emit(
            {
                "type": "done",
                "message": "章节已生成，等待审核。",
                "chapterId": queued_chapter_id,
                "redirectTo": f"/chapters/{queued_chapter_id}",
                "chapter": chapter_review_payload(db_path, queued_chapter_id),
            }
        )

    yield from _events_from_worker(worker)


def stream_repair_chapter(
    db_path: Path,
    chapter_id: int,
    body: dict[str, Any],
    *,
    model_client=None,
    provider_config: ProviderConfig | None = None,
) -> Iterator[StreamEvent]:
    reviewer_note = _optional_text(body, "reviewerNote", "reviewer_note")

    def worker(emit: EmitEvent) -> None:
        emit({"type": "started", "message": "AI 已开始修订章节。"})
        queued_chapter_id = queue_chapter_repair(
            db_path,
            chapter_id,
            provider_config,
            reviewer_note=reviewer_note,
            start_background=False,
        )
        with Session(create_engine_for_path(db_path)) as session:
            repair_chapter_with_ai(
                session,
                queued_chapter_id,
                model_client=_eventing_chapter_client(db_path, model_client, provider_config, emit),
                model_name=_model_name(model_client, provider_config),
                reviewer_note=reviewer_note,
            )
        emit(
            {
                "type": "done",
                "message": "章节修订已完成。",
                "chapterId": queued_chapter_id,
                "redirectTo": f"/chapters/{queued_chapter_id}",
                "chapter": chapter_review_payload(db_path, queued_chapter_id),
            }
        )

    yield from _events_from_worker(worker)


def stream_run_chapter_batch(
    db_path: Path,
    book_id: int,
    body: dict[str, Any],
    *,
    model_client=None,
    provider_config: ProviderConfig | None = None,
) -> Iterator[StreamEvent]:
    def worker(emit: EmitEvent) -> None:
        chapter_ids = parse_chapter_batch_ids(body.get("chapterIds"))
        emit({"type": "started", "message": "AI 已开始批量生产章节。"})
        first_chapter_id = queue_chapter_batch_run(
            db_path,
            book_id,
            chapter_ids,
            provider_config,
            start_background=False,
        )
        with Session(create_engine_for_path(db_path)) as session:
            result = run_chapter_batch(
                session,
                book_id,
                chapter_ids,
                model_client=_eventing_chapter_client(db_path, model_client, provider_config, emit),
                model_name=_model_name(model_client, provider_config),
            )
        emit(
            {
                "type": "done",
                "message": "批量生产已完成。",
                "chapterId": first_chapter_id,
                "redirectTo": f"/chapters/{first_chapter_id}",
                "chapter": chapter_review_payload(db_path, first_chapter_id),
                "batch": {
                    "completedChapterNumbers": result.completed_chapter_numbers,
                    "paused": result.paused,
                    "pauseReason": result.pause_reason,
                },
            }
        )

    yield from _events_from_worker(worker)

def stream_generate_volume_outline(
    db_path: Path,
    book_id: int,
    *,
    model_client=None,
    provider_config: ProviderConfig | None = None,
) -> Iterator[StreamEvent]:
    def worker(emit: EmitEvent) -> None:
        emit({"type": "started", "message": "AI 已开始生成卷纲。"})
        with Session(create_engine_for_path(db_path)) as session:
            generate_volume_outline(
                session,
                book_id,
                model_client=_eventing_volume_client(db_path, model_client, provider_config, emit),
                model_name=_model_name(model_client, provider_config),
            )
        payload = book_detail_payload(db_path, book_id)
        if payload is None:
            raise ValueError("Book does not exist.")
        emit(
            {
                "type": "done",
                "message": "卷纲已生成。",
                "book": payload,
            }
        )

    yield from _events_from_worker(worker)


def stream_revise_volume_outline(
    db_path: Path,
    book_id: int,
    body: dict[str, Any],
    *,
    model_client=None,
    provider_config: ProviderConfig | None = None,
) -> Iterator[StreamEvent]:
    def worker(emit: EmitEvent) -> None:
        emit({"type": "started", "message": "AI 已开始修订卷纲。"})
        with Session(create_engine_for_path(db_path)) as session:
            revise_volume_outline(
                session,
                book_id,
                body,
                model_client=_eventing_volume_client(db_path, model_client, provider_config, emit),
                model_name=_model_name(model_client, provider_config),
            )
        payload = book_detail_payload(db_path, book_id)
        if payload is None:
            raise ValueError("Book does not exist.")
        emit(
            {
                "type": "done",
                "message": "卷纲已修订。",
                "book": payload,
            }
        )

    yield from _events_from_worker(worker)


def _stream_blueprint_job(
    db_path: Path,
    blueprint_id: int,
    provider_config: ProviderConfig | None,
    model_client,
) -> Iterator[StreamEvent]:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    previous_blueprint: dict[str, Any] | None = None
    with Session(engine) as session:
        blueprint = get_open_book_blueprint(session, blueprint_id)
        if blueprint is None:
            yield _failed("蓝图不存在。")
            return
        blueprint.status = BlueprintStatus.RUNNING
        blueprint.started_at = utc_now()
        blueprint.error_message = None
        blueprint.parse_error = None
        blueprint.raw_response = ""
        blueprint.content = {}
        idea = blueprint.idea
        revision_notes = blueprint.instruction
        if blueprint.parent_id is not None:
            parent = get_open_book_blueprint(session, blueprint.parent_id)
            previous_blueprint = public_blueprint_content(parent.content) if parent else None
        session.add(blueprint)
        session.commit()

    yield {
        "type": "started",
        "message": "AI 已开始生成蓝图。",
        "blueprintId": blueprint_id,
        "redirectTo": f"/blueprints/{blueprint_id}",
    }
    messages = build_blueprint_messages(idea, previous_blueprint, revision_notes)
    client = model_client or OpenAIStreamingCompleteClient(provider_config)  # type: ignore[arg-type]
    raw_parts: list[str] = []
    try:
        for chunk in _stream_complete(client, "open_book_blueprint", messages, "json"):
            raw_parts.append(chunk)
            yield {"type": "chunk", "text": chunk}
        raw_response = "".join(raw_parts)
        content = parse_blueprint_json(raw_response)
        status = BlueprintStatus.SUCCEEDED
        parse_error = None
        error_message = None
    except (json.JSONDecodeError, ValueError) as error:
        raw_response = "".join(raw_parts)
        content = {}
        status = BlueprintStatus.FAILED
        parse_error = str(error)
        error_message = str(error)
    except Exception as error:  # noqa: BLE001
        raw_response = "".join(raw_parts)
        content = {}
        status = BlueprintStatus.FAILED
        parse_error = None
        error_message = str(error)

    with Session(engine) as session:
        blueprint = get_open_book_blueprint(session, blueprint_id)
        if blueprint is None:
            yield _failed("蓝图不存在。")
            return
        blueprint.status = status
        blueprint.content = content
        blueprint.raw_response = raw_response
        blueprint.parse_error = parse_error
        blueprint.error_message = error_message
        blueprint.finished_at = utc_now()
        session.add(blueprint)
        session.commit()
        session.refresh(blueprint)
        payload = blueprint_payload(blueprint)

    if status == BlueprintStatus.FAILED:
        yield _failed(error_message or "蓝图生成失败。")
        return
    yield {
        "type": "done",
        "message": "蓝图已生成。",
        "blueprintId": blueprint_id,
        "redirectTo": f"/blueprints/{blueprint_id}",
        "blueprint": payload,
    }


def _eventing_chapter_client(
    db_path: Path,
    model_client,
    provider_config: ProviderConfig | None,
    emit: EmitEvent,
):
    source_client = model_client
    if source_client is None:
        provider_config = provider_config or _load_provider_config(db_path)
        if not is_provider_config_complete(provider_config):
            return None
        source_client = OpenAIStreamingCompleteClient(provider_config)
    return EventingCompleteClient(
        source_client,
        emit,
        stage_labels={
            "plan": "正在规划本章。",
            "draft": "正在生成草稿。",
            "extract_state": "正在提取状态变化。",
            "audit": "正在审计风险。",
            "revise": "正在修订正文。",
            "word_count_patch": "正在修补字数。",
        },
    )


def _eventing_volume_client(
    db_path: Path,
    model_client,
    provider_config: ProviderConfig | None,
    emit: EmitEvent,
):
    source_client = model_client
    if source_client is None:
        provider_config = provider_config or _load_provider_config(db_path)
        if not is_provider_config_complete(provider_config):
            return None
        source_client = OpenAIStreamingCompleteClient(provider_config, temperature=0.35)
    return EventingCompleteClient(
        source_client,
        emit,
        stage_labels={
            "volume_outline": "正在生成卷纲与章节规划。",
            "volume_outline_revision": "正在按修改意见修订卷纲。",
        },
    )


def _events_from_worker(worker: Callable[[EmitEvent], None]) -> Iterator[StreamEvent]:
    sentinel = object()
    events: Queue[StreamEvent | object] = Queue()

    def emit(event: StreamEvent) -> None:
        events.put(event)

    def run() -> None:
        try:
            worker(emit)
        except Exception as error:  # noqa: BLE001
            emit(_failed(str(error)))
        finally:
            events.put(sentinel)

    thread = Thread(target=run, daemon=True)
    thread.start()
    while True:
        event = events.get()
        if event is sentinel:
            break
        yield event  # type: ignore[misc]
    thread.join()


def _stream_complete(
    client,
    stage: str,
    messages: list[dict[str, str]],
    response_format: str,
) -> Iterator[str]:
    stream_complete = getattr(client, "stream_complete", None)
    if callable(stream_complete):
        yield from stream_complete(stage, messages, response_format)
        return
    complete = getattr(client, "complete")
    yield complete(stage, messages, response_format)


def _complete_provider_config(db_path: Path) -> ProviderConfig | None:
    provider_config = _load_provider_config(db_path)
    return provider_config if is_provider_config_complete(provider_config) else None


def _load_provider_config(db_path: Path) -> ProviderConfig | None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        return get_provider_config(session)


def _model_name(model_client, provider_config: ProviderConfig | None) -> str | None:
    model = getattr(model_client, "model", None)
    if isinstance(model, str) and model.strip():
        return model
    if provider_config is not None and provider_config.llm_model.strip():
        return provider_config.llm_model
    return None


def _optional_text(body: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = body.get(key)
        if value is None:
            continue
        text = str(value).strip()
        return text or None
    return None


def _int_value(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_form(body: dict[str, Any]) -> dict[str, str]:
    return {key: "" if value is None else str(value).strip() for key, value in body.items()}


def _failed(message: str) -> StreamEvent:
    return {"type": "failed", "message": message or "AI 处理失败。"}
