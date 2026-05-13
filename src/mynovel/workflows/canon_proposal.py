from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from sqlmodel import Session

from mynovel.domain.models import (
    Book,
    BookStatus,
    Canon,
    CanonProposalRevision,
    CanonProposalRevisionStatus,
    utc_now,
)
from mynovel.domain.repositories import (
    add_canon_proposal_revision,
    get_book,
    get_canon_proposal_revision,
    get_latest_canon,
    list_pending_canon_proposal_revisions_for_book,
)
from mynovel.prompts.registry import load_prompt_by_id, render_prompt_messages

CANON_PROPOSAL_KEY = "_canon_proposal"


@dataclass(frozen=True)
class CanonProposalSection:
    key: str
    anchor: str
    label: str
    editable: bool = True


SECTION_REGISTRY = {
    "world_rules": CanonProposalSection("world_rules", "world", "世界规则"),
    "characters": CanonProposalSection("characters", "characters", "人物"),
    "factions": CanonProposalSection("factions", "factions", "势力"),
    "locations": CanonProposalSection("locations", "locations", "地点"),
    "relationships": CanonProposalSection("relationships", "relationships", "关系"),
    "foreshadowing": CanonProposalSection("foreshadowing", "foreshadowing", "伏笔账本"),
    "chapter_summaries": CanonProposalSection("chapter_summaries", "chapter-summaries", "章节摘要"),
    "state_history": CanonProposalSection("state_history", "state-history", "变化历史", False),
}


class CanonProposalModelClient(Protocol):
    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        pass


def section_locks_for_book(book: Book) -> dict[str, bool]:
    proposal = book.constraints.get(CANON_PROPOSAL_KEY, {})
    raw_locks = proposal.get("section_locks", {}) if isinstance(proposal, dict) else {}
    return {
        key: bool(raw_locks.get(key, not section.editable))
        for key, section in SECTION_REGISTRY.items()
    }


def set_canon_proposal_section_lock(
    session: Session,
    book_id: int | None,
    section: str,
    locked: bool,
) -> Book:
    if book_id is None:
        raise ValueError("Book id is required.")
    book = get_book(session, book_id)
    if book is None:
        raise ValueError("Book not found.")
    if book.status != BookStatus.DRAFT:
        raise ValueError("Canon proposal locks can only be changed for draft books.")
    _editable_section(section)

    constraints = dict(book.constraints)
    proposal = constraints.get(CANON_PROPOSAL_KEY, {})
    if not isinstance(proposal, dict):
        proposal = {}
    normalized_proposal = dict(proposal)
    section_locks = section_locks_for_book(book)
    section_locks[section] = bool(locked)
    normalized_proposal["section_locks"] = section_locks
    constraints[CANON_PROPOSAL_KEY] = normalized_proposal
    book.constraints = constraints
    session.add(book)
    session.commit()
    session.refresh(book)
    return book


def content_hash(value: Any) -> str:
    return _json_sha256(value)


def locks_hash(value: Any) -> str:
    return _json_sha256(value)


def create_canon_proposal_revision(
    session: Session,
    book_id: int | None,
    target_section: str,
    instruction: str,
    client: CanonProposalModelClient,
) -> CanonProposalRevision:
    book, canon = _draft_book_and_canon(session, book_id)
    _editable_section(target_section)
    locks = section_locks_for_book(book)
    if locks[target_section]:
        raise ValueError(f"Canon proposal section is locked: {target_section}")

    allowed_sections = [
        key for key, section in SECTION_REGISTRY.items() if section.editable and not locks[key]
    ]
    locked_sections = [
        key for key, section in SECTION_REGISTRY.items() if section.editable and locks[key]
    ]
    asset = load_prompt_by_id("canon_proposal_revision")
    messages = render_prompt_messages(
        asset,
        {
            "trusted_state_proposal": canon.content,
            "target_section": target_section,
            "instruction": instruction,
            "section_locks": locks,
            "allowed_sections": allowed_sections,
            "locked_sections": locked_sections,
        },
    )
    raw_response = client.complete("canon_proposal_revision", messages, "json")
    payload = _parse_revision_payload(raw_response)
    changed_sections = _validated_changed_sections(payload, allowed_sections, locks)
    revision = CanonProposalRevision(
        book_id=book.id or 0,
        base_canon_version=canon.version,
        base_content_hash=content_hash(canon.content),
        base_locks_hash=locks_hash(locks),
        target_section=target_section,
        instruction=instruction,
        allowed_sections=allowed_sections,
        locked_sections=locked_sections,
        changed_sections=changed_sections,
        blocked_sections=_list_payload(payload.get("blocked_sections")),
        summary=str(payload.get("summary") or ""),
        risks=_list_payload(payload.get("risks")),
    )
    return add_canon_proposal_revision(session, revision)


def apply_canon_proposal_revision(
    session: Session,
    book_id: int,
    revision_id: int,
) -> CanonProposalRevision:
    book = get_book(session, book_id)
    revision = get_canon_proposal_revision(session, revision_id)
    if book is None:
        raise ValueError("Book not found.")
    if revision is None or revision.book_id != book_id:
        raise ValueError("Canon proposal revision not found.")
    if revision.status != CanonProposalRevisionStatus.PENDING:
        raise ValueError("Canon proposal revision is not pending.")
    if book.status != BookStatus.DRAFT:
        _mark_revision_stale(session, revision)
        raise ValueError("Canon proposal revision can only be applied to draft books.")

    canon = get_latest_canon(session, book_id)
    if canon is None:
        _mark_revision_stale(session, revision)
        raise ValueError("Trusted state proposal is required.")

    locks = section_locks_for_book(book)
    if (
        canon.version != revision.base_canon_version
        or content_hash(canon.content) != revision.base_content_hash
        or locks_hash(locks) != revision.base_locks_hash
    ):
        _mark_revision_stale(session, revision)
        raise ValueError("Canon proposal revision is stale.")

    changed_sections = _validated_changed_sections(revision.__dict__, revision.allowed_sections, locks)
    updated_content = dict(canon.content)
    for section, replacement in changed_sections.items():
        updated_content[section] = replacement

    now = utc_now()
    changed_section_names = list(changed_sections)
    state_history = list(updated_content.get("state_history") or [])
    state_history.append(
        {
            "type": "canon_proposal_revision",
            "target_section": revision.target_section,
            "changed_sections": changed_section_names,
            "blocked_sections": revision.blocked_sections,
            "summary": revision.summary,
            "risks": revision.risks,
            "updated_at": now.isoformat(),
            "instruction": revision.instruction,
        }
    )
    updated_content["state_history"] = state_history
    canon.content = updated_content

    constraints = dict(book.constraints)
    proposal = constraints.get(CANON_PROPOSAL_KEY, {})
    if not isinstance(proposal, dict):
        proposal = {}
    normalized_proposal = dict(proposal)
    normalized_proposal["section_locks"] = locks
    normalized_proposal["last_revision"] = {
        "target_section": revision.target_section,
        "instruction": revision.instruction,
        "changed_sections": changed_section_names,
        "blocked_sections": revision.blocked_sections,
        "summary": revision.summary,
        "risks": revision.risks,
        "updated_at": now.isoformat(),
    }
    constraints[CANON_PROPOSAL_KEY] = normalized_proposal
    book.constraints = constraints
    book.updated_at = now

    revision.status = CanonProposalRevisionStatus.APPLIED
    revision.applied_at = now
    session.add(canon)
    session.add(book)
    session.add(revision)
    session.commit()
    session.refresh(revision)
    return revision


def discard_canon_proposal_revision(
    session: Session,
    book_id: int,
    revision_id: int,
) -> CanonProposalRevision:
    revision = get_canon_proposal_revision(session, revision_id)
    if revision is None or revision.book_id != book_id:
        raise ValueError("Canon proposal revision not found.")
    if revision.status != CanonProposalRevisionStatus.PENDING:
        raise ValueError("Canon proposal revision is not pending.")
    revision.status = CanonProposalRevisionStatus.DISCARDED
    session.add(revision)
    session.commit()
    session.refresh(revision)
    return revision


def mark_pending_canon_proposal_revisions_stale(session: Session, book_id: int) -> None:
    for revision in list_pending_canon_proposal_revisions_for_book(session, book_id):
        revision.status = CanonProposalRevisionStatus.STALE
        session.add(revision)


def finalize_canon_proposal_for_lock(session: Session, book: Book, canon: Canon) -> None:
    normalized_content: dict[str, Any] = {}
    if isinstance(canon.content.get("book"), dict):
        normalized_content["book"] = canon.content["book"]
    for section in SECTION_REGISTRY:
        value = canon.content.get(section)
        normalized_content[section] = value if isinstance(value, list) else []
    canon.content = normalized_content

    constraints = dict(book.constraints)
    constraints.pop(CANON_PROPOSAL_KEY, None)
    book.constraints = constraints
    mark_pending_canon_proposal_revisions_stale(session, book.id or 0)
    session.add(canon)
    session.add(book)


def _editable_section(section: str) -> CanonProposalSection:
    known = SECTION_REGISTRY.get(section)
    if known is None:
        raise ValueError(f"Unknown canon proposal section: {section}")
    if not known.editable:
        raise ValueError(f"Canon proposal section is read-only: {section}")
    return known


def _json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _mark_revision_stale(session: Session, revision: CanonProposalRevision) -> None:
    revision.status = CanonProposalRevisionStatus.STALE
    session.add(revision)
    session.commit()
    session.refresh(revision)


def _draft_book_and_canon(session: Session, book_id: int | None) -> tuple[Book, Canon]:
    if book_id is None:
        raise ValueError("Book id is required.")
    book = get_book(session, book_id)
    if book is None:
        raise ValueError("Book not found.")
    if book.status != BookStatus.DRAFT:
        raise ValueError("Canon proposal revisions can only be created for draft books.")
    canon = get_latest_canon(session, book_id)
    if canon is None:
        raise ValueError("Trusted state proposal is required.")
    return book, canon


def _parse_revision_payload(raw_response: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ValueError("Canon proposal revision response must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Canon proposal revision response must be a JSON object.")
    return payload


def _validated_changed_sections(
    payload: dict[str, Any],
    allowed_sections: list[str],
    locks: dict[str, bool],
) -> dict[str, list]:
    raw_changed = payload.get("changed_sections")
    if not isinstance(raw_changed, dict):
        raise ValueError("Canon proposal revision changed_sections must be an object.")

    allowed = set(allowed_sections)
    changed_sections: dict[str, list] = {}
    for section, replacement in raw_changed.items():
        _editable_section(str(section))
        if section not in allowed or locks.get(section, True):
            raise ValueError(f"Canon proposal revision changed a locked section: {section}")
        if not isinstance(replacement, list):
            raise ValueError(f"Canon proposal section replacement must be an array: {section}")
        changed_sections[str(section)] = replacement
    return changed_sections


def _list_payload(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    raise ValueError("Canon proposal revision list fields must be arrays.")
