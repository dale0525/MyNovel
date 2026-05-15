from __future__ import annotations

import asyncio
import json
from pathlib import Path
from threading import Thread
from typing import Any

from sqlmodel import Session

from mynovel.blueprint_content import public_blueprint_content
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, OpenBookBlueprint, ProviderConfig, utc_now
from mynovel.domain.repositories import get_open_book_blueprint
from mynovel.llm.openai_compatible import ChatRequest, OpenAICompatibleClient
from mynovel.workflows.open_book_blueprint import (
    build_blueprint_messages,
    extract_chat_content,
    parse_blueprint_json,
)


def start_blueprint_job(
    db_path: Path,
    blueprint_id: int,
    provider_config: ProviderConfig,
) -> None:
    thread = Thread(
        target=run_blueprint_job,
        args=(db_path, blueprint_id, provider_config),
        daemon=True,
    )
    thread.start()


def run_blueprint_job(
    db_path: Path,
    blueprint_id: int,
    provider_config: ProviderConfig,
) -> None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    previous_blueprint: dict[str, Any] | None = None
    idea = ""
    revision_notes = None

    with Session(engine) as session:
        blueprint = get_open_book_blueprint(session, blueprint_id)
        if blueprint is None:
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

    raw_response = ""
    status = BlueprintStatus.SUCCEEDED
    content: dict[str, Any] = {}
    parse_error = None
    error_message = None

    try:
        raw_response = asyncio.run(
            request_blueprint(provider_config, idea, previous_blueprint, revision_notes)
        )
        content = parse_blueprint_json(raw_response)
    except (json.JSONDecodeError, ValueError) as error:
        status = BlueprintStatus.FAILED
        parse_error = str(error)
        error_message = str(error)
    except Exception as error:  # noqa: BLE001
        status = BlueprintStatus.FAILED
        error_message = str(error)

    with Session(engine) as session:
        blueprint = get_open_book_blueprint(session, blueprint_id)
        if blueprint is None:
            return
        blueprint.status = status
        blueprint.content = content
        blueprint.raw_response = raw_response
        blueprint.parse_error = parse_error
        blueprint.error_message = error_message
        blueprint.finished_at = utc_now()
        session.add(blueprint)
        session.commit()


def reset_blueprint_for_retry(
    session: Session,
    blueprint: OpenBookBlueprint,
) -> OpenBookBlueprint:
    blueprint.status = BlueprintStatus.PENDING
    blueprint.content = {}
    blueprint.raw_response = ""
    blueprint.parse_error = None
    blueprint.error_message = None
    blueprint.started_at = None
    blueprint.finished_at = None
    session.add(blueprint)
    session.commit()
    session.refresh(blueprint)
    return blueprint


async def request_blueprint(
    provider_config: ProviderConfig,
    idea: str,
    previous_blueprint: dict[str, Any] | None,
    revision_notes: str | None,
) -> str:
    client = OpenAICompatibleClient(
        base_url=provider_config.llm_base_url,
        api_key=provider_config.llm_api_key or "",
    )
    response = await client.chat(
        ChatRequest(
            model=provider_config.llm_model,
            messages=build_blueprint_messages(
                idea=idea,
                previous_blueprint=previous_blueprint,
                revision_notes=revision_notes,
            ),
            temperature=0.7,
            extra={"response_format": {"type": "json_object"}},
        )
    )
    return extract_chat_content(response)
