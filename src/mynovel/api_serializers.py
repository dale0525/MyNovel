from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from sqlmodel import Session, select

from mynovel.blueprint_content import public_blueprint_content
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import (
    Book,
    Canon,
    CanonProposalRevision,
    CanonProposalRevisionStatus,
    Chapter,
    OpenBookBlueprint,
    ProviderConfig,
    ProviderConfigValidation,
    RunTrace,
    VolumePlan,
)
from mynovel.domain.repositories import (
    get_canon_proposal_revision,
    get_chapter,
    get_latest_canon,
    get_provider_config,
    get_provider_config_validation,
    list_chapters_for_book,
    list_pending_canon_proposal_revisions_for_book,
    list_run_traces_for_book,
    list_volume_plans_for_book,
)
from mynovel.provider_config_validation import provider_model_fingerprint
from mynovel.workflows.canon_proposal import (
    SECTION_REGISTRY,
    canon_proposal_readiness,
    content_hash,
    locks_hash,
    section_locks_for_book,
)


def app_bootstrap_payload(db_path: Path) -> dict[str, Any]:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        configured = is_provider_config_validated(
            get_provider_config(session),
            get_provider_config_validation(session),
        )
    return {
        "providerConfigured": configured,
        "initialRoute": "/" if configured else "/setup",
        "message": None,
    }


def book_payload(book: Book) -> dict[str, Any]:
    return {
        "id": book.id,
        "title": book.title,
        "genre": book.genre,
        "audience": book.audience,
        "status": book.status.value,
        "premise": book.premise,
    }


def chapter_payload(chapter: Chapter) -> dict[str, Any]:
    return {
        "id": chapter.id,
        "bookId": chapter.book_id,
        "number": chapter.number,
        "title": chapter.title,
        "status": chapter.status.value,
        "summary": chapter.summary,
        "wordCount": chapter.word_count,
        "reviewerNote": chapter.reviewer_note,
        "updatedAt": _isoformat(chapter.updated_at),
    }


def chapter_detail_payload(chapter: Chapter) -> dict[str, Any]:
    payload = chapter_payload(chapter)
    payload.update(
        {
            "plan": chapter.plan,
            "contextPackage": chapter.context_package,
            "draftText": chapter.draft_text,
            "revisedText": chapter.revised_text,
            "finalText": chapter.final_text,
            "auditReport": chapter.audit_report,
            "stateDelta": chapter.state_delta,
        }
    )
    return payload


def chapter_stage_slots(chapter: Chapter) -> list[dict[str, Any]]:
    return [
        _stage_slot("plan", "章节规划", bool(chapter.plan), _plan_summary(chapter.plan)),
        _stage_slot(
            "context",
            "上下文",
            bool(chapter.context_package),
            _context_summary(chapter.context_package),
        ),
        _stage_slot("draft", "草稿", bool(chapter.draft_text), _text_summary(chapter.draft_text)),
        _stage_slot(
            "delta",
            "状态变化",
            bool(_state_delta_changes(chapter.state_delta)),
            _delta_summary(chapter.state_delta),
        ),
        _stage_slot(
            "audit",
            "审计",
            bool(chapter.audit_report),
            _audit_summary(chapter.audit_report),
        ),
    ]


def canon_payload(canon: Canon) -> dict[str, Any]:
    return {
        "id": canon.id,
        "bookId": canon.book_id,
        "version": canon.version,
        "content": canon.content,
        "createdAt": _isoformat(canon.created_at),
    }


def run_trace_payload(trace: RunTrace) -> dict[str, Any]:
    return {
        "id": trace.id,
        "bookId": trace.book_id,
        "stage": trace.stage,
        "promptId": trace.prompt_id,
        "promptVersion": trace.prompt_version,
        "model": trace.model,
        "cost": trace.cost,
        "metadata": trace.metadata_,
        "createdAt": _isoformat(trace.created_at),
    }


def volume_plan_payload(volume_plan: VolumePlan) -> dict[str, Any]:
    return {
        "id": volume_plan.id,
        "bookId": volume_plan.book_id,
        "volumeNumber": volume_plan.volume_number,
        "title": volume_plan.title,
        "coreConflict": volume_plan.core_conflict,
        "pacingCurve": volume_plan.pacing_curve,
        "payoffDistribution": volume_plan.payoff_distribution,
        "keyTurns": volume_plan.key_turns,
        "commitments": volume_plan.commitments,
    }


def canon_proposal_revision_payload(revision: CanonProposalRevision) -> dict[str, Any]:
    return {
        "id": revision.id,
        "bookId": revision.book_id,
        "baseCanonVersion": revision.base_canon_version,
        "targetSection": revision.target_section,
        "instruction": revision.instruction,
        "allowedSections": revision.allowed_sections,
        "lockedSections": revision.locked_sections,
        "changedSections": revision.changed_sections,
        "blockedSections": revision.blocked_sections,
        "summary": revision.summary,
        "risks": revision.risks,
        "status": revision.status.value,
        "createdAt": _isoformat(revision.created_at),
        "appliedAt": _isoformat(revision.applied_at),
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


def book_detail_payload(db_path: Path, book_id: int) -> dict[str, Any] | None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = session.get(Book, book_id)
        if book is None:
            return None
        canon = get_latest_canon(session, book_id)
        chapters = list_chapters_for_book(session, book_id)
        run_traces = list_run_traces_for_book(session, book_id)
        volume_plans = list_volume_plans_for_book(session, book_id)
        return {
            "book": book_payload(book),
            "chapters": [chapter_payload(chapter) for chapter in chapters],
            "latestCanon": canon_payload(canon) if canon is not None else None,
            "runTraces": [run_trace_payload(trace) for trace in run_traces],
            "volumePlans": [volume_plan_payload(volume_plan) for volume_plan in volume_plans],
        }


def chapter_review_payload(db_path: Path, chapter_id: int) -> dict[str, Any] | None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        chapter = get_chapter(session, chapter_id)
        if chapter is None:
            return None
        book = session.get(Book, chapter.book_id)
        if book is None:
            return None
        canon = get_latest_canon(session, chapter.book_id)
        chapters = list_chapters_for_book(session, chapter.book_id)
        run_traces = _chapter_run_traces(list_run_traces_for_book(session, chapter.book_id), chapter)
        return {
            "book": book_payload(book),
            "chapter": chapter_detail_payload(chapter),
            "siblingChapters": [chapter_payload(item) for item in chapters],
            "latestCanon": canon_payload(canon) if canon is not None else None,
            "traces": [run_trace_payload(trace) for trace in run_traces],
            "stageSlots": chapter_stage_slots(chapter),
        }


def _chapter_run_traces(run_traces: list[RunTrace], chapter: Chapter) -> list[RunTrace]:
    identifiers = {chapter.number, str(chapter.number), chapter.id, str(chapter.id)}
    return sorted(
        [
            trace
            for trace in run_traces
            if (trace.metadata_ or {}).get("chapter") in identifiers
        ],
        key=lambda trace: (trace.created_at, trace.id or 0),
    )


def trusted_state_payload(
    db_path: Path,
    book_id: int,
    revision_id: int | None = None,
) -> dict[str, Any] | None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = session.get(Book, book_id)
        if book is None:
            return None
        canon = get_latest_canon(session, book_id)
        content = canon.content if canon is not None else {}
        locks = section_locks_for_book(book)
        readiness = canon_proposal_readiness(content)
        selected_revision = None
        if revision_id is not None:
            revision = get_canon_proposal_revision(session, revision_id)
            if (
                revision is not None
                and revision.book_id == book_id
                and revision.status
                in {
                    CanonProposalRevisionStatus.RUNNING,
                    CanonProposalRevisionStatus.PENDING,
                    CanonProposalRevisionStatus.FAILED,
                }
                and canon is not None
                and revision.base_canon_version == canon.version
                and revision.base_content_hash == content_hash(canon.content)
                and revision.base_locks_hash == locks_hash(locks)
            ):
                selected_revision = revision
        return {
            "book": book_payload(book),
            "latestCanon": canon_payload(canon) if canon is not None else None,
            "canonSections": _canon_section_payloads(content, locks),
            "sectionLocks": locks,
            "readiness": {
                "complete": readiness.complete,
                "missingSections": readiness.missing_sections,
                "messages": readiness.messages,
            },
            "pendingRevisions": [
                canon_proposal_revision_payload(revision)
                for revision in list_pending_canon_proposal_revisions_for_book(session, book_id)
            ],
            "selectedRevision": (
                canon_proposal_revision_payload(selected_revision)
                if selected_revision is not None
                else None
            ),
        }


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


def _canon_section_payloads(
    content: dict[str, Any], locks: dict[str, bool]
) -> list[dict[str, Any]]:
    return [
        {
            "key": section.key,
            "anchor": section.anchor,
            "label": section.label,
            "editable": section.editable,
            "locked": locks.get(section.key, not section.editable),
            "content": content.get(section.key, []),
        }
        for section in SECTION_REGISTRY.values()
    ]


def _isoformat(value) -> str | None:
    return value.isoformat() if value is not None else None


def _stage_slot(key: str, label: str, ready: bool, summary: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "ready": ready,
        "status": "ready" if ready else "empty",
        "summary": summary,
    }


def _plan_summary(plan: dict[str, Any]) -> str:
    goal = str(plan.get("goal") or "").strip()
    word_budget = plan.get("word_budget")
    if goal and word_budget:
        return f"{goal} · {word_budget} 字目标"
    if goal:
        return goal
    if word_budget:
        return f"{word_budget} 字目标"
    return ""


def _context_summary(context_package: dict[str, Any]) -> str:
    trusted_state = context_package.get("trusted_state")
    if isinstance(trusted_state, dict) and trusted_state.get("version"):
        return f"可信设定 v{trusted_state['version']}"
    if context_package:
        return f"{len(context_package)} 个上下文分区"
    return ""


def _text_summary(text: str) -> str:
    return f"{len(text)} 字" if text else ""


def _delta_summary(state_delta: dict[str, Any]) -> str:
    changes = _state_delta_changes(state_delta)
    return f"{len(changes)} 条状态变化" if changes else ""


def _state_delta_changes(state_delta: dict[str, Any]) -> list[Any]:
    changes = state_delta.get("changes")
    return changes if isinstance(changes, list) else []


def _audit_summary(audit_report: dict[str, Any]) -> str:
    if not audit_report:
        return ""
    risk = str(audit_report.get("risk_level") or "").strip()
    issues = audit_report.get("issues")
    issue_count = len(issues) if isinstance(issues, list) else 0
    if risk and issue_count:
        return f"{risk} 风险 · {issue_count} 个问题"
    if risk:
        return f"{risk} 风险"
    return f"{issue_count} 个问题" if issue_count else "已生成审计报告"
