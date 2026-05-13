from __future__ import annotations

import asyncio
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any

from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import CanonProposalRevision, CanonProposalRevisionStatus
from mynovel.domain.repositories import (
    get_book,
    get_canon_proposal_revision,
    get_latest_canon,
    get_provider_config,
)
from mynovel.llm.openai_compatible import ChatRequest, OpenAICompatibleClient
from mynovel.product_views import is_provider_config_complete
from mynovel.workflows.canon_proposal import (
    SECTION_REGISTRY,
    apply_canon_proposal_revision,
    content_hash,
    create_canon_proposal_revision,
    discard_canon_proposal_revision,
    locks_hash,
    section_locks_for_book,
    set_canon_proposal_section_lock,
)

CANON_PROPOSAL_POST_PATHS = {
    "/canon-proposal-lock",
    "/canon-proposal-revise",
    "/canon-proposal-apply",
    "/canon-proposal-discard",
}


@dataclass(frozen=True)
class CanonProposalServerResponse:
    body: str = ""
    status: HTTPStatus = HTTPStatus.OK
    redirect_to: str | None = None


class OpenAICanonProposalModelClient:
    def __init__(self, client: OpenAICompatibleClient, model: str) -> None:
        self.client = client
        self.model = model

    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        extra: dict[str, Any] = {}
        if response_format == "json":
            extra["response_format"] = {"type": "json_object"}
        response = asyncio.run(
            self.client.chat(
                ChatRequest(
                    model=self.model,
                    messages=messages,
                    temperature=0.2,
                    extra=extra,
                )
            )
        )
        return _extract_chat_content(response)


def is_canon_proposal_post_path(path: str) -> bool:
    return path in CANON_PROPOSAL_POST_PATHS


def dispatch_canon_proposal_post(
    path: str,
    form: dict[str, str],
    db_path: Path,
) -> CanonProposalServerResponse:
    if path == "/canon-proposal-lock":
        return handle_toggle_canon_proposal_section_lock(form, db_path)
    if path == "/canon-proposal-revise":
        return handle_create_canon_proposal_revision(form, db_path)
    if path == "/canon-proposal-apply":
        return handle_apply_canon_proposal_revision(form, db_path)
    if path == "/canon-proposal-discard":
        return handle_discard_canon_proposal_revision(form, db_path)
    return CanonProposalServerResponse(status=HTTPStatus.NOT_FOUND)


def handle_toggle_canon_proposal_section_lock(
    form: dict[str, str],
    db_path: Path,
) -> CanonProposalServerResponse:
    book_id = _parse_int(form.get("book_id"))
    section = form.get("section", "")
    try:
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            set_canon_proposal_section_lock(
                session,
                book_id,
                section,
                _form_truthy(form.get("locked")),
            )
    except ValueError as error:
        return _bad_request(error)
    return CanonProposalServerResponse(redirect_to=_state_anchor(book_id or 0, section))


def handle_create_canon_proposal_revision(
    form: dict[str, str],
    db_path: Path,
    model_client=None,
) -> CanonProposalServerResponse:
    book_id = _parse_int(form.get("book_id"))
    target_section = form.get("target_section", "")
    instruction = form.get("instruction", "")
    if not instruction.strip():
        return _bad_request(ValueError("Canon proposal revision instruction is required."))
    try:
        client = model_client or _model_client_from_db(db_path)
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            revision = create_canon_proposal_revision(
                session,
                book_id,
                target_section,
                instruction,
                client,
            )
    except ValueError as error:
        return _bad_request(error)
    except Exception as error:  # noqa: BLE001
        return _bad_gateway(error)
    revision_id = revision.id or 0
    anchor = SECTION_REGISTRY.get(target_section)
    fragment = anchor.anchor if anchor else "world"
    return CanonProposalServerResponse(
        redirect_to=f"/book/{book_id or 0}/state?revision_id={revision_id}#{fragment}"
    )


def handle_apply_canon_proposal_revision(
    form: dict[str, str],
    db_path: Path,
) -> CanonProposalServerResponse:
    book_id = _parse_int(form.get("book_id"))
    revision_id = _parse_int(form.get("revision_id"))
    try:
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            revision = apply_canon_proposal_revision(session, book_id or 0, revision_id or 0)
    except ValueError as error:
        return _bad_request(error)
    return CanonProposalServerResponse(
        redirect_to=_state_anchor(book_id or 0, revision.target_section)
    )


def handle_discard_canon_proposal_revision(
    form: dict[str, str],
    db_path: Path,
) -> CanonProposalServerResponse:
    book_id = _parse_int(form.get("book_id"))
    revision_id = _parse_int(form.get("revision_id"))
    try:
        engine = create_engine_for_path(db_path)
        create_db_and_tables(engine)
        with Session(engine) as session:
            revision = discard_canon_proposal_revision(session, book_id or 0, revision_id or 0)
    except ValueError as error:
        return _bad_request(error)
    return CanonProposalServerResponse(
        redirect_to=_state_anchor(book_id or 0, revision.target_section)
    )


def load_pending_canon_proposal_revision_for_book(
    db_path: Path,
    book_id: int,
    revision_id: int | None,
) -> CanonProposalRevision | None:
    if not revision_id:
        return None
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        revision = get_canon_proposal_revision(session, revision_id)
        if (
            revision is None
            or revision.book_id != book_id
            or revision.status != CanonProposalRevisionStatus.PENDING
        ):
            return None
        book = get_book(session, book_id)
        canon = get_latest_canon(session, book_id)
        if book is None or canon is None:
            return None
        if (
            canon.version != revision.base_canon_version
            or content_hash(canon.content) != revision.base_content_hash
            or locks_hash(section_locks_for_book(book)) != revision.base_locks_hash
        ):
            return None
        return revision


def _model_client_from_db(db_path: Path) -> OpenAICanonProposalModelClient:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        provider_config = get_provider_config(session)
    if not is_provider_config_complete(provider_config):
        raise ValueError("Complete provider config is required.")
    assert provider_config is not None
    return OpenAICanonProposalModelClient(
        OpenAICompatibleClient(
            base_url=provider_config.llm_base_url,
            api_key=provider_config.llm_api_key or "",
        ),
        provider_config.llm_model,
    )


def _parse_int(raw_value: str | None) -> int | None:
    try:
        return int(raw_value or "")
    except ValueError:
        return None


def _form_truthy(raw_value: str | None) -> bool:
    return raw_value in {"1", "true", "on", "yes"}


def _state_anchor(book_id: int, section: str) -> str:
    anchor = SECTION_REGISTRY.get(section)
    fragment = anchor.anchor if anchor else "world"
    return f"/book/{book_id}/state#{fragment}"


def _bad_request(error: ValueError) -> CanonProposalServerResponse:
    return CanonProposalServerResponse(body=str(error), status=HTTPStatus.BAD_REQUEST)


def _bad_gateway(error: Exception) -> CanonProposalServerResponse:
    return CanonProposalServerResponse(body=str(error), status=HTTPStatus.BAD_GATEWAY)


def _extract_chat_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Chat response did not include choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("Chat response choice is invalid.")
    message = first.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ValueError("Chat response did not include message content.")
    return message["content"]
