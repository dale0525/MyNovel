from __future__ import annotations

import hashlib
import json
from copy import deepcopy
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


@dataclass(frozen=True)
class CanonProposalReadiness:
    complete: bool
    missing_sections: list[str]
    messages: list[str]


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
TRUSTED_STATE_EXTRA_LIST_KEYS = ("accepted_chapters", "resources")
CANON_PROPOSAL_MINIMUM_COUNTS = {
    "world_rules": 1,
    "characters": 3,
    "factions": 1,
    "locations": 2,
    "relationships": 2,
    "foreshadowing": 3,
    "chapter_summaries": 3,
}
CANON_PROPOSAL_COMPLETION_INSTRUCTION = (
    "请补全开书定盘缺失的信息。重点补足主要人物、势力、地点、关系、伏笔和前 10 章节奏；"
    "保持现有世界观一致，不要改写已锁定分区。"
)


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


def canon_proposal_readiness(content: Any) -> CanonProposalReadiness:
    source = content if isinstance(content, dict) else {}
    missing_sections: list[str] = []
    messages: list[str] = []
    for section_key, minimum_count in CANON_PROPOSAL_MINIMUM_COUNTS.items():
        section = SECTION_REGISTRY[section_key]
        count = _canon_section_count(source.get(section_key))
        if count < minimum_count:
            missing_sections.append(section_key)
            messages.append(f"{section.label}至少 {minimum_count} 条")
    return CanonProposalReadiness(
        complete=not missing_sections,
        missing_sections=missing_sections,
        messages=messages,
    )


def canon_proposal_completion_target(content: Any, locks: dict[str, bool]) -> str | None:
    readiness = canon_proposal_readiness(content)
    for section_key in readiness.missing_sections:
        section = SECTION_REGISTRY[section_key]
        if section.editable and not locks.get(section_key, False):
            return section_key
    return None


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
    book, canon, locks, allowed_sections, locked_sections = _revision_context(
        session,
        book_id,
        target_section,
    )
    messages = _revision_prompt_messages(
        canon.content,
        target_section,
        instruction,
        locks,
        allowed_sections,
        locked_sections,
    )
    raw_response = client.complete("canon_proposal_revision", messages, "json")
    payload = _parse_revision_payload(raw_response)
    response_target_section = _validated_target_section(payload, target_section, locks)
    changed_sections = _validated_changed_sections(payload, allowed_sections, locks)
    revision = CanonProposalRevision(
        book_id=book.id or 0,
        base_canon_version=canon.version,
        base_content_hash=content_hash(canon.content),
        base_locks_hash=locks_hash(locks),
        target_section=response_target_section,
        instruction=instruction,
        allowed_sections=allowed_sections,
        locked_sections=locked_sections,
        changed_sections=changed_sections,
        blocked_sections=_list_payload(payload.get("blocked_sections")),
        summary=str(payload.get("summary") or ""),
        risks=_list_payload(payload.get("risks")),
    )
    return add_canon_proposal_revision(session, revision)


def create_canon_proposal_revision_job(
    session: Session,
    book_id: int | None,
    target_section: str,
    instruction: str,
) -> CanonProposalRevision:
    book, canon, locks, allowed_sections, locked_sections = _revision_context(
        session,
        book_id,
        target_section,
    )
    revision = CanonProposalRevision(
        book_id=book.id or 0,
        base_canon_version=canon.version,
        base_content_hash=content_hash(canon.content),
        base_locks_hash=locks_hash(locks),
        target_section=target_section,
        instruction=instruction,
        allowed_sections=allowed_sections,
        locked_sections=locked_sections,
        summary="AI 修订生成中。",
        status=CanonProposalRevisionStatus.RUNNING,
    )
    return add_canon_proposal_revision(session, revision)


def complete_canon_proposal_revision_job(
    session: Session,
    revision_id: int,
    client: CanonProposalModelClient,
) -> CanonProposalRevision:
    revision = get_canon_proposal_revision(session, revision_id)
    if revision is None:
        raise ValueError("Canon proposal revision not found.")
    if revision.status != CanonProposalRevisionStatus.RUNNING:
        raise ValueError("Canon proposal revision is not running.")

    book = get_book(session, revision.book_id)
    canon = get_latest_canon(session, revision.book_id)
    if book is None:
        _mark_revision_failed(session, revision, "Book not found.")
        raise ValueError("Book not found.")
    if book.status != BookStatus.DRAFT:
        _mark_revision_stale(session, revision)
        raise ValueError("Canon proposal revision can only be created for draft books.")
    if canon is None:
        _mark_revision_failed(session, revision, "Trusted state proposal is required.")
        raise ValueError("Trusted state proposal is required.")

    locks = section_locks_for_book(book)
    if (
        canon.version != revision.base_canon_version
        or content_hash(canon.content) != revision.base_content_hash
        or locks_hash(locks) != revision.base_locks_hash
    ):
        _mark_revision_stale(session, revision)
        raise ValueError("Canon proposal revision is stale.")

    messages = _revision_prompt_messages(
        canon.content,
        revision.target_section,
        revision.instruction,
        locks,
        revision.allowed_sections,
        revision.locked_sections,
    )
    raw_response = client.complete("canon_proposal_revision", messages, "json")
    payload = _parse_revision_payload(raw_response)
    response_target_section = _validated_target_section(payload, revision.target_section, locks)
    changed_sections = _validated_changed_sections(payload, revision.allowed_sections, locks)

    revision.target_section = response_target_section
    revision.changed_sections = changed_sections
    revision.blocked_sections = _list_payload(payload.get("blocked_sections"))
    revision.summary = str(payload.get("summary") or "")
    revision.risks = _list_payload(payload.get("risks"))
    revision.status = CanonProposalRevisionStatus.PENDING
    session.add(revision)
    session.commit()
    session.refresh(revision)
    return revision


def mark_canon_proposal_revision_failed(
    session: Session,
    revision_id: int,
    message: str,
) -> CanonProposalRevision | None:
    revision = get_canon_proposal_revision(session, revision_id)
    if revision is None:
        return None
    if revision.status != CanonProposalRevisionStatus.RUNNING:
        return revision
    _mark_revision_failed(session, revision, message)
    return revision


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

    changed_sections = _validated_changed_sections(
        revision.__dict__, revision.allowed_sections, locks
    )
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


def sanitize_canon_content(content: Any) -> dict[str, Any]:
    normalized_content: dict[str, Any] = {}
    source = content if isinstance(content, dict) else {}
    if isinstance(source.get("book"), dict):
        normalized_content["book"] = deepcopy(source["book"])
    for section in SECTION_REGISTRY:
        value = source.get(section)
        normalized_content[section] = deepcopy(value) if isinstance(value, list) else []
    for key in TRUSTED_STATE_EXTRA_LIST_KEYS:
        value = source.get(key)
        if isinstance(value, list):
            normalized_content[key] = deepcopy(value)
    return normalized_content


def finalize_canon_proposal_for_lock(session: Session, book: Book, canon: Canon) -> None:
    canon.content = sanitize_canon_content(canon.content)
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


def _canon_section_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if value in (None, "", {}):
        return 0
    return 1


def _mark_revision_stale(session: Session, revision: CanonProposalRevision) -> None:
    revision.status = CanonProposalRevisionStatus.STALE
    session.add(revision)
    session.commit()
    session.refresh(revision)


def _mark_revision_failed(
    session: Session,
    revision: CanonProposalRevision,
    message: str,
) -> None:
    revision.status = CanonProposalRevisionStatus.FAILED
    revision.summary = "AI 修订生成失败。"
    revision.risks = [message]
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


def _revision_context(
    session: Session,
    book_id: int | None,
    target_section: str,
) -> tuple[Book, Canon, dict[str, bool], list[str], list[str]]:
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
    return book, canon, locks, allowed_sections, locked_sections


def _revision_prompt_messages(
    trusted_state_proposal: dict,
    target_section: str,
    instruction: str,
    locks: dict[str, bool],
    allowed_sections: list[str],
    locked_sections: list[str],
) -> list[dict[str, str]]:
    asset = load_prompt_by_id("canon_proposal_revision")
    return render_prompt_messages(
        asset,
        {
            "trusted_state_proposal": trusted_state_proposal,
            "target_section": target_section,
            "instruction": instruction,
            "section_locks": locks,
            "allowed_sections": allowed_sections,
            "locked_sections": locked_sections,
        },
    )


def _parse_revision_payload(raw_response: str) -> dict[str, Any]:
    try:
        payload = json.loads(_json_object_text(_strip_code_fence(raw_response.strip())))
    except json.JSONDecodeError as exc:
        raise ValueError("Canon proposal revision response must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Canon proposal revision response must be a JSON object.")
    return payload


def _json_object_text(text: str) -> str:
    if text.startswith("{"):
        return text
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            _, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        return text[index : index + end]
    return text


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        first = lines[0].strip()
        if first in {"```", "```json"}:
            return "\n".join(lines[1:-1]).strip()
    return text


def _validated_target_section(
    payload: dict[str, Any],
    expected_section: str,
    locks: dict[str, bool],
) -> str:
    raw_target = payload.get("target_section")
    if not isinstance(raw_target, str) or not raw_target.strip():
        return expected_section
    target_section = raw_target.strip()
    _editable_section(target_section)
    if locks.get(target_section, True):
        raise ValueError(f"Canon proposal revision targeted a locked section: {target_section}")
    if target_section != expected_section:
        raise ValueError("Canon proposal revision target_section does not match request.")
    return target_section


def _validated_changed_sections(
    payload: dict[str, Any],
    allowed_sections: list[str],
    locks: dict[str, bool],
) -> dict[str, list]:
    raw_changed = _changed_sections_payload(payload)

    allowed = set(allowed_sections)
    changed_sections: dict[str, list] = {}
    for section, replacement in raw_changed.items():
        section_key = str(section).strip()
        _editable_section(section_key)
        if section_key not in allowed or locks.get(section_key, True):
            raise ValueError(f"Canon proposal revision changed a locked section: {section_key}")
        replacement = _replacement_array(replacement)
        if not isinstance(replacement, list):
            raise ValueError(f"Canon proposal section replacement must be an array: {section_key}")
        changed_sections[section_key] = replacement
    return changed_sections


def _changed_sections_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "changed_sections" in payload:
        return _normalized_changed_sections_payload(payload.get("changed_sections"))

    bare_sections = {
        section_key: payload[section_key]
        for section_key, section in SECTION_REGISTRY.items()
        if section.editable and section_key in payload
    }
    if bare_sections:
        return bare_sections
    raise ValueError("Canon proposal revision changed_sections must be an object.")


def _normalized_changed_sections_payload(raw_changed: Any) -> dict[str, Any]:
    if isinstance(raw_changed, dict):
        return raw_changed
    if not isinstance(raw_changed, list):
        raise ValueError("Canon proposal revision changed_sections must be an object.")

    normalized: dict[str, Any] = {}
    for index, item in enumerate(raw_changed, start=1):
        if not isinstance(item, dict):
            raise ValueError(
                f"Canon proposal revision changed_sections item #{index} must be an object."
            )
        section = item.get("section") or item.get("section_key") or item.get("key")
        if not isinstance(section, str) or not section.strip():
            raise ValueError(
                f"Canon proposal revision changed_sections item #{index} must include section."
            )
        section_key = section.strip()
        if section_key in normalized:
            raise ValueError(f"Canon proposal revision changed section twice: {section_key}")
        normalized[section_key] = _changed_section_item_replacement(item, index)
    return normalized


def _changed_section_item_replacement(item: dict[str, Any], index: int) -> Any:
    for key in ("replacement", "items", "value", "content", "entries"):
        if key in item:
            return item[key]
    raise ValueError(
        f"Canon proposal revision changed_sections item #{index} must include a replacement array."
    )


def _replacement_array(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    for key in ("replacement", "items", "value", "content", "entries"):
        if key in value:
            return value[key]
    return value


def _list_payload(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    raise ValueError("Canon proposal revision list fields must be arrays.")
