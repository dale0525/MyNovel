from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from typing import Any, Protocol

from sqlmodel import Session

from mynovel.domain.models import BookStatus, Canon, Chapter, ChapterStatus, RunTrace, utc_now
from mynovel.domain.repositories import (
    get_active_volume_plan,
    get_book,
    get_chapter,
    get_latest_canon,
    get_provider_config,
    get_provider_config_validation,
)
from mynovel.llm.openai_compatible import ChatRequest, OpenAICompatibleClient
from mynovel.prompts.registry import load_prompt_by_id, render_prompt_messages
from mynovel.workflows.chapter_prompting import (
    build_audit_messages as _build_audit_messages,
    build_draft_messages as _build_draft_messages,
    build_extract_state_messages as _build_extract_state_messages,
    build_plan_messages as _build_plan_messages,
    build_revise_messages as _build_revise_messages,
)
from mynovel.workflows.chapter_response_parsing import (
    ChapterJsonStageFormatError,
    fallback_audit_report,
    normalize_state_delta,
    parse_json_stage_response,
)
from mynovel.workflows.embedding import TextEmbeddingClient, embedding_client_from_provider_config
from mynovel.workflows.chapter_repair import (
    RepairRequest,
    apply_word_count_patch_bounded,
    build_repair_request,
    build_word_count_patch_request,
    patch_addressed_issue_titles,
    recheck_repair_audit,
    repair_response_should_be_rejected,
    repair_text_locally,
    repair_trace_cost,
    repair_trace_metadata,
    repair_trace_prompt_id,
    repair_validation_warning,
    word_count_patch_mode,
)
from mynovel.workflows.open_book_blueprint import extract_chat_content
from mynovel.workflows.retrieval import RetrievedContext, index_text, retrieve_book_context
from mynovel.workflows.state_validation import validate_state_delta


class ChapterModelClient(Protocol):
    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        pass


class OpenAIChapterModelClient:
    def __init__(
        self,
        client: OpenAICompatibleClient,
        model: str,
        temperature: float = 0.7,
    ) -> None:
        self.client = client
        self.model = model
        self.temperature = temperature

    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        extra = {"response_format": {"type": "json_object"}} if response_format == "json" else None
        response = asyncio.run(
            self.client.chat(
                ChatRequest(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    extra=extra,
                )
            )
        )
        return extract_chat_content(response)


class ReviewGateError(ValueError):
    pass


class ChapterStageError(RuntimeError):
    def __init__(
        self,
        stage: str,
        error: Exception,
        *,
        messages: list[dict[str, str]] | None = None,
        response_format: str | None = None,
        raw_response_text: str | None = None,
    ) -> None:
        super().__init__(str(error))
        self.stage = stage
        self.error = error
        self.messages = messages or []
        self.response_format = response_format
        self.raw_response_text = raw_response_text


TRACE_STAGES = [
    ("plan", "规划本章", "chapter_plan"),
    ("context", "编译上下文", "chapter_context"),
    ("draft", "生成草稿", "chapter_draft"),
    ("extract_state", "提取状态变化", "chapter_state_extract"),
    ("audit", "审计", "chapter_audit"),
    ("revise", "修订", "chapter_revise"),
]
PROMPT_VERSION = "0.1.0"


def run_chapter_pipeline(
    session: Session,
    chapter_id: int,
    model_client: ChapterModelClient | None = None,
    model_name: str | None = None,
    *,
    embedding_client: TextEmbeddingClient | None = None,
) -> Chapter:
    chapter = _required_chapter(session, chapter_id)
    book = get_book(session, chapter.book_id)
    canon = get_latest_canon(session, chapter.book_id)
    volume_plan = get_active_volume_plan(session, chapter.book_id)
    if book is None or canon is None:
        raise ValueError("Chapter must belong to a book with trusted state.")
    if book.status == BookStatus.DRAFT:
        raise ValueError("Trusted state must be locked before chapter production.")

    chapter.status = ChapterStatus.RUNNING
    model_label = model_name or "本地演示模型"
    embedding_client = embedding_client or _embedding_client_from_session(session)
    try:
        if model_client is None:
            _run_simulated_pipeline(
                session,
                book.title,
                canon,
                chapter,
                _volume_plan_payload(volume_plan),
                embedding_client,
            )
        else:
            _run_model_pipeline(
                session,
                book.title,
                canon,
                chapter,
                model_client,
                _volume_plan_payload(volume_plan),
                embedding_client,
            )
    except Exception as error:  # noqa: BLE001
        failed_stage = error.stage if isinstance(error, ChapterStageError) else "unknown"
        return _record_pipeline_failure(session, chapter, model_label, failed_stage, error)
    chapter.summary = _summarize_chapter(chapter)
    chapter.word_count = len(chapter.revised_text)
    recheck_repair_audit(chapter)
    chapter.status = ChapterStatus.AWAITING_REVIEW
    chapter.updated_at = utc_now()
    book.status = BookStatus.PRODUCING

    session.add(book)
    session.add(chapter)
    _add_pipeline_traces(session, chapter, model_label)
    session.commit()
    session.refresh(chapter)
    return chapter


def approve_chapter(
    session: Session,
    chapter_id: int,
    reviewer_note: str | None = None,
    allow_major_changes: bool = False,
    *,
    embedding_client: TextEmbeddingClient | None = None,
) -> Chapter:
    chapter = _required_chapter(session, chapter_id)
    latest = get_latest_canon(session, chapter.book_id)
    if latest is None:
        raise ValueError("Trusted state is required before accepting a chapter.")
    if chapter.status != ChapterStatus.AWAITING_REVIEW:
        raise ValueError("Only chapters waiting for human review can be accepted.")
    validate_state_delta(chapter)
    _assert_review_gate_passed(chapter, allow_major_changes)

    chapter.status = ChapterStatus.ACCEPTED
    chapter.final_text = chapter.revised_text or chapter.draft_text
    chapter.reviewer_note = reviewer_note
    chapter.updated_at = utc_now()

    trusted_state_version = latest.version + 1
    updated_content = _content_with_accepted_chapter(latest.content, chapter)
    session.add(chapter)
    session.add(
        Canon(book_id=chapter.book_id, version=trusted_state_version, content=updated_content)
    )
    session.add(
        RunTrace(
            book_id=chapter.book_id,
            stage="accept_chapter",
            model=None,
            cost={"estimated": 0},
            metadata_={"chapter": chapter.number, "trusted_state_version": trusted_state_version},
        )
    )
    if embedding_client is None:
        embedding_client = _embedding_client_from_session(session)
    _index_accepted_chapter(
        session,
        chapter,
        updated_content,
        trusted_state_version,
        embedding_client,
    )
    session.commit()
    session.refresh(chapter)
    return chapter


def apply_manual_chapter_edit(
    session: Session,
    chapter_id: int,
    revised_text: str,
    reviewer_note: str | None = None,
) -> Chapter:
    chapter = _required_chapter(session, chapter_id)
    text = revised_text.strip()
    if not text:
        raise ValueError("Manual chapter text cannot be empty.")
    if chapter.status not in {ChapterStatus.AWAITING_REVIEW, ChapterStatus.NEEDS_REVISION}:
        raise ValueError("Only review-stage chapters can be edited.")

    chapter.revised_text = text
    chapter.word_count = len(text)
    recheck_repair_audit(chapter)
    chapter.status = ChapterStatus.AWAITING_REVIEW
    chapter.reviewer_note = reviewer_note
    chapter.updated_at = utc_now()
    session.add(chapter)
    session.add(
        RunTrace(
            book_id=chapter.book_id,
            stage="人工修正",
            model=None,
            cost={"estimated": 0},
            metadata_={"chapter": chapter.number, "status": chapter.status.value},
        )
    )
    session.commit()
    session.refresh(chapter)
    return chapter


def return_chapter_for_revision(
    session: Session,
    chapter_id: int,
    reviewer_note: str | None = None,
) -> Chapter:
    chapter = _required_chapter(session, chapter_id)
    if chapter.status != ChapterStatus.AWAITING_REVIEW:
        raise ValueError("Only chapters waiting for human review can be returned for revision.")

    chapter.status = ChapterStatus.NEEDS_REVISION
    chapter.reviewer_note = reviewer_note
    chapter.updated_at = utc_now()
    session.add(chapter)
    session.add(
        RunTrace(
            book_id=chapter.book_id,
            stage="退回修订",
            model=None,
            cost={"estimated": 0},
            metadata_={"chapter": chapter.number, "status": chapter.status.value},
        )
    )
    session.commit()
    session.refresh(chapter)
    return chapter


def repair_chapter_with_ai(
    session: Session,
    chapter_id: int,
    model_client: ChapterModelClient | None = None,
    model_name: str | None = None,
    reviewer_note: str | None = None,
) -> Chapter:
    chapter = _required_chapter(session, chapter_id)
    if chapter.status not in {
        ChapterStatus.AWAITING_REVIEW,
        ChapterStatus.NEEDS_REVISION,
        ChapterStatus.RUNNING,
    }:
        raise ValueError("Only review-stage chapters can be repaired.")

    source_text = chapter.revised_text or chapter.final_text or chapter.draft_text
    recheck_repair_audit(chapter)
    before_word_count = len(source_text)
    repair_request: RepairRequest | None = None
    raw_response_text: str
    applied_response_text: str
    word_count_repair_mode: str | None = None
    patch_operations: list[dict[str, Any]] | None = None
    applied_patch_operations: list[dict[str, Any]] | None = None
    patch_application_strategy: str | None = None
    addressed_issue_titles: list[str] = []
    if model_client is None:
        applied_response_text = repair_text_locally(chapter, _revise_text)
        raw_response_text = applied_response_text
    else:
        repair_request = build_repair_request(chapter, reviewer_note)
        word_count_repair_mode = word_count_patch_mode(
            repair_request.before_word_count,
            repair_request.word_count_window,
        )
        if word_count_repair_mode is None:
            raw_response_text = _complete_text_stage(
                model_client,
                "revise",
                repair_request.messages,
            )
            applied_response_text = raw_response_text
        else:
            repair_request = build_word_count_patch_request(chapter, reviewer_note)
            patch_payload, raw_response_text = _complete_json_stage_with_raw(
                model_client,
                "word_count_patch",
                repair_request.messages,
                {"operations"},
            )
            patch_operations = [
                operation
                for operation in patch_payload.get("operations", [])
                if isinstance(operation, dict)
            ]
            patch_application = apply_word_count_patch_bounded(
                source_text,
                patch_payload,
                repair_request.word_count_window,
                repair_request.target_word_count,
            )
            applied_response_text = patch_application.text
            applied_patch_operations = patch_application.operations
            patch_application_strategy = patch_application.strategy
            addressed_issue_titles = patch_addressed_issue_titles(
                applied_patch_operations,
                repair_request.unresolved_audit_issues,
            )
    validation_warning = repair_validation_warning(
        repair_request, source_text, applied_response_text
    )
    rejected_response = repair_response_should_be_rejected(
        repair_request,
        source_text,
        applied_response_text,
    )
    chapter.revised_text = source_text if rejected_response else applied_response_text
    chapter.word_count = len(chapter.revised_text)
    recheck_repair_audit(
        chapter,
        addressed_issue_titles=[] if rejected_response else addressed_issue_titles,
    )
    chapter.status = (
        ChapterStatus.NEEDS_REVISION if validation_warning else ChapterStatus.AWAITING_REVIEW
    )
    chapter.reviewer_note = validation_warning or reviewer_note
    chapter.updated_at = utc_now()

    session.add(chapter)
    session.add(
        RunTrace(
            book_id=chapter.book_id,
            stage="修复问题",
            prompt_id=repair_trace_prompt_id(repair_request, word_count_repair_mode),
            prompt_version=PROMPT_VERSION if repair_request is not None else None,
            model=model_name or "本地演示模型",
            cost=repair_trace_cost(repair_request, raw_response_text),
            metadata_=repair_trace_metadata(
                chapter,
                repair_request,
                reviewer_note,
                before_word_count,
                validation_warning,
                raw_response_text,
                applied_response_text,
                rejected_response,
                word_count_repair_mode,
                patch_operations,
                applied_patch_operations,
                patch_application_strategy,
                addressed_issue_titles,
            ),
        )
    )
    session.commit()
    session.refresh(chapter)
    return chapter


def export_chapter_text(chapter: Chapter) -> str:
    if chapter.status != ChapterStatus.ACCEPTED or not chapter.final_text:
        raise ReviewGateError("只有已批准章节可以导出最终正文。")
    return chapter.final_text


def _required_chapter(session: Session, chapter_id: int) -> Chapter:
    chapter = get_chapter(session, chapter_id)
    if chapter is None:
        raise ValueError("Chapter does not exist.")
    return chapter


def _run_simulated_pipeline(
    session: Session,
    book_title: str,
    canon: Canon,
    chapter: Chapter,
    volume_plan: dict[str, Any],
    embedding_client: TextEmbeddingClient | None,
) -> None:
    retrieved_context = _retrieved_context_for_chapter(session, chapter, canon, embedding_client)
    chapter.context_package = _build_context_package(canon, chapter, volume_plan, retrieved_context)
    chapter.draft_text = _generate_draft_text(book_title, chapter)
    chapter.audit_report = _audit_chapter(chapter)
    chapter.revised_text = _revise_text(chapter.draft_text, chapter.audit_report)
    chapter.state_delta = _extract_state_delta(chapter)


def _run_model_pipeline(
    session: Session,
    book_title: str,
    canon: Canon,
    chapter: Chapter,
    model_client: ChapterModelClient,
    volume_plan: dict[str, Any],
    embedding_client: TextEmbeddingClient | None,
) -> None:
    chapter.plan = _complete_json_stage(
        model_client,
        "plan",
        _build_plan_messages(book_title, canon, chapter, volume_plan),
        {"goal", "must_write", "forbidden_drift", "word_budget", "ending_hook"},
    )
    retrieved_context = _retrieved_context_for_chapter(session, chapter, canon, embedding_client)
    chapter.context_package = _build_context_package(canon, chapter, volume_plan, retrieved_context)
    chapter.draft_text = _complete_text_stage(
        model_client,
        "draft",
        _build_draft_messages(book_title, chapter),
    )
    chapter.state_delta = normalize_state_delta(
        chapter.number,
        _complete_json_stage(
            model_client,
            "extract_state",
            _build_extract_state_messages(chapter),
            {"chapter", "changes"},
        ),
    )
    try:
        chapter.audit_report = _complete_json_stage(
            model_client,
            "audit",
            _build_audit_messages(chapter),
            {"risk_level", "issues", "suggestions"},
        )
    except ChapterStageError as error:
        if not _is_recoverable_json_stage_error(error):
            raise
        chapter.audit_report = fallback_audit_report(error.error)
    chapter.revised_text = _complete_text_stage(
        model_client,
        "revise",
        _build_revise_messages(chapter),
    )


def _complete_json_stage(
    model_client: ChapterModelClient,
    stage: str,
    messages: list[dict[str, str]],
    required_fields: set[str],
) -> dict[str, Any]:
    data, _ = _complete_json_stage_with_raw(model_client, stage, messages, required_fields)
    return data


def _complete_json_stage_with_raw(
    model_client: ChapterModelClient,
    stage: str,
    messages: list[dict[str, str]],
    required_fields: set[str],
) -> tuple[dict[str, Any], str]:
    try:
        raw = model_client.complete(stage, messages, "json")
    except Exception as error:  # noqa: BLE001
        raise ChapterStageError(stage, error, messages=messages, response_format="json") from error
    try:
        data = parse_json_stage_response(raw, stage)
        missing = sorted(required_fields - set(data))
        if missing:
            raise ChapterJsonStageFormatError(
                f"Chapter stage {stage} missing fields: {', '.join(missing)}"
            )
        return data, raw
    except ChapterJsonStageFormatError as error:
        raise ChapterStageError(
            stage,
            error,
            messages=messages,
            response_format="json",
            raw_response_text=raw,
        ) from error


def _is_recoverable_json_stage_error(error: ChapterStageError) -> bool:
    return isinstance(error.error, ChapterJsonStageFormatError)


def _complete_text_stage(
    model_client: ChapterModelClient,
    stage: str,
    messages: list[dict[str, str]],
) -> str:
    try:
        text = model_client.complete(stage, messages, "text").strip()
        if not text:
            raise ValueError(f"Chapter stage {stage} returned empty text.")
        return text
    except Exception as error:  # noqa: BLE001
        raise ChapterStageError(stage, error, messages=messages, response_format="text") from error


def _build_context_package(
    canon: Canon,
    chapter: Chapter,
    volume_plan: dict[str, Any],
    retrieved_context: list[dict[str, Any]] | None = None,
) -> dict:
    return {
        "trusted_state": {
            "version": canon.version,
            "book": canon.content.get("book", {}),
            "characters": canon.content.get("characters", []),
            "foreshadowing": canon.content.get("foreshadowing", []),
            "chapter_summaries": canon.content.get("chapter_summaries", []),
        },
        "volume_plan": volume_plan,
        "chapter_goal": chapter.plan.get("goal", ""),
        "word_budget": chapter.plan.get("word_budget"),
        "must_write": chapter.plan.get("must_write", []),
        "retrieved_context": retrieved_context or [],
        "forbidden_drift": ["不要改写已锁定设定", "不要让状态变化绕过人工审核"],
    }


def _retrieved_context_for_chapter(
    session: Session, chapter: Chapter, canon: Canon, client: TextEmbeddingClient | None
) -> list[dict[str, Any]]:
    query = _chapter_retrieval_query(chapter, canon)
    query_embedding = None
    embedding_model = None
    if client is not None:
        try:
            query_embedding = client.embed_text(query)
            embedding_model = client.model
        except Exception:  # noqa: BLE001
            query_embedding = embedding_model = None
    contexts = retrieve_book_context(
        session,
        chapter.book_id,
        query,
        query_embedding=query_embedding,
        embedding_model=embedding_model,
    )
    return [_retrieved_context_payload(item) for item in contexts]


def _chapter_retrieval_query(chapter: Chapter, canon: Canon) -> str:
    content = canon.content or {}
    return json.dumps(
        {
            "chapter": {"number": chapter.number, "title": chapter.title},
            "chapter_goal": chapter.plan.get("goal", ""),
            "must_write": chapter.plan.get("must_write", []),
            "characters": _recent_items(content.get("characters"), 8),
            "foreshadowing": _recent_items(content.get("foreshadowing"), 8),
            "chapter_summaries": _recent_items(content.get("chapter_summaries"), 3),
        },
        ensure_ascii=False,
    )


def _recent_items(value: Any, limit: int) -> Any:
    return value[-limit:] if isinstance(value, list) else value


def _retrieved_context_payload(item: RetrievedContext) -> dict[str, Any]:
    return {"source_type": item.source_type, "source_id": item.source_id, "score": round(item.score, 4), "text": item.text, "metadata": dict(item.metadata or {})}


def _volume_plan_payload(volume_plan: Any) -> dict[str, Any]:
    if volume_plan is None:
        return {}
    return {
        "volume_number": volume_plan.volume_number,
        "title": volume_plan.title,
        "core_conflict": volume_plan.core_conflict,
        "pacing_curve": volume_plan.pacing_curve,
        "payoff_distribution": volume_plan.payoff_distribution,
        "key_turns": volume_plan.key_turns,
        "commitments": volume_plan.commitments,
    }


def _add_pipeline_traces(session: Session, chapter: Chapter, model_name: str) -> None:
    for stage_key, stage_label, prompt_id in TRACE_STAGES:
        prompt_version, prompt_source, prompt_chars = _trace_prompt_metadata(chapter, prompt_id)
        completion_chars = max(1, len(_stage_completion_text(chapter, stage_key)))
        session.add(
            RunTrace(
                book_id=chapter.book_id,
                stage=stage_label,
                prompt_id=prompt_id,
                prompt_version=prompt_version,
                model=model_name,
                cost={
                    "estimated": 0,
                    "prompt_chars": prompt_chars,
                    "completion_chars": completion_chars,
                    "elapsed_ms": 0,
                },
                metadata_={
                    "chapter": chapter.number,
                    "status": chapter.status.value,
                    "stage_key": stage_key,
                    "prompt_source": prompt_source,
                },
            )
        )


def _record_pipeline_failure(
    session: Session,
    chapter: Chapter,
    model_name: str,
    failed_stage: str,
    error: Exception,
) -> Chapter:
    root_error = error.error if isinstance(error, ChapterStageError) else error
    chapter.status = ChapterStatus.NEEDS_REVISION
    chapter.reviewer_note = f"生成失败：{root_error}"
    chapter.updated_at = utc_now()
    session.add(chapter)
    session.add(
        RunTrace(
            book_id=chapter.book_id,
            stage="生产失败",
            model=model_name,
            cost={"estimated": 0},
            metadata_={
                "chapter": chapter.number,
                "status": chapter.status.value,
                "failed_stage": failed_stage,
                "error": str(root_error),
                "retryable": True,
            },
        )
    )
    session.commit()
    session.refresh(chapter)
    return chapter


def _generate_draft_text(book_title: str, chapter: Chapter) -> str:
    goal = chapter.plan.get("goal") or "推进本章目标。"
    return (
        f"《{book_title}》第 {chapter.number:02d} 章：{chapter.title}\n\n"
        f"{goal}\n\n"
        "雾气贴着山谷缓慢流动，像一层尚未揭开的旧纸。主角沿着潮湿石阶向前，"
        "每一步都把熟悉的生活留在身后。远处传来低低的回响，仿佛有人在破碎的墙后"
        "读出一段被抹去的历史。\n\n"
        "她停下脚步，确认那枚符号仍在掌心发热。它不是答案，更像一道邀请。"
        "如果继续向前，她会失去安全的退路；如果回头，真相也会从此沉入雾中。"
    )


def _audit_chapter(chapter: Chapter) -> dict:
    return {
        "risk_level": "medium",
        "issues": [
            {"severity": "medium", "title": "人物动机需要更明确", "resolved": True},
            {"severity": "low", "title": "环境描写略有重复", "resolved": True},
            {"severity": "medium", "title": "结尾钩子需要更强", "resolved": False},
        ],
        "suggestions": ["强化主角继续前进的理由", "把最后一句改成新的悬念"],
    }


def _revise_text(draft_text: str, audit_report: dict) -> str:
    unresolved = [
        issue["title"]
        for issue in audit_report.get("issues", [])
        if isinstance(issue, dict) and not issue.get("resolved")
    ]
    hook = "石门深处忽然亮起第二枚符号，像是在回应她掌心的热度。"
    if unresolved:
        return f"{draft_text}\n\n修订后钩子：{hook}"
    return draft_text


def _extract_state_delta(chapter: Chapter) -> dict:
    return {
        "chapter": chapter.number,
        "changes": [
            {"type": "人物状态", "target": "主角", "change": "离开安全区，主动追查真相"},
            {"type": "地点", "target": chapter.title, "change": "首次进入本章关键地点"},
            {"type": "伏笔", "target": "发热符号", "change": "符号与遗迹产生呼应"},
        ],
    }


def _summarize_chapter(chapter: Chapter) -> str:
    return f"第 {chapter.number:02d} 章《{chapter.title}》完成本章目标，并留下新的遗迹线索。"


def _assert_review_gate_passed(chapter: Chapter, allow_major_changes: bool) -> None:
    audit_report = chapter.audit_report or {}
    if str(audit_report.get("risk_level", "")).lower() == "high":
        raise ReviewGateError("高风险问题未解决，不能写入可信设定。")
    for issue in audit_report.get("issues", []):
        if not isinstance(issue, dict):
            continue
        severity = str(issue.get("severity", "")).lower()
        if severity == "high" and not issue.get("resolved"):
            raise ReviewGateError("高风险问题未解决，不能写入可信设定。")
    major_changes = _major_state_changes(chapter)
    if major_changes and not allow_major_changes:
        raise ReviewGateError("存在重大变化，需要人工显式确认后才能写入可信设定。")


def _major_state_changes(chapter: Chapter) -> list[dict[str, Any]]:
    return [
        change
        for change in chapter.state_delta.get("changes", [])
        if isinstance(change, dict) and _is_major_state_change(change)
    ]


def _is_major_state_change(change: dict[str, Any]) -> bool:
    impact = str(change.get("impact", "")).lower()
    if impact in {"major", "critical", "high"}:
        return True
    text = " ".join(str(change.get(key, "")) for key in ("type", "target", "change"))
    major_terms = ("角色死亡", "人物死亡", "死亡", "牺牲", "退场", "核心设定", "改写设定")
    return any(term in text for term in major_terms)


def _content_with_accepted_chapter(content: dict, chapter: Chapter) -> dict:
    updated = deepcopy(content)
    updated.setdefault("chapter_summaries", []).append(
        {
            "chapter": chapter.number,
            "title": chapter.title,
            "summary": chapter.summary,
            "word_count": chapter.word_count,
        }
    )
    updated.setdefault("state_history", []).append(chapter.state_delta)
    for change in chapter.state_delta.get("changes", []):
        if isinstance(change, dict):
            _append_structured_state_change(updated, chapter, change)
    updated.setdefault("accepted_chapters", []).append(
        {"chapter": chapter.number, "title": chapter.title, "accepted_at": utc_now().isoformat()}
    )
    return updated


def _append_structured_state_change(
    content: dict[str, Any],
    chapter: Chapter,
    change: dict[str, Any],
) -> None:
    bucket = _state_bucket_for_change(change)
    if bucket is None:
        return

    target = str(change.get("target") or change.get("name") or "").strip()
    detail = str(change.get("change") or change.get("detail") or "").strip()
    if not target and not detail:
        return
    if _is_low_information_state_change(target, detail):
        return

    content.setdefault(bucket, []).append(
        {
            "name": target or detail[:32],
            "detail": detail,
            "type": str(change.get("type") or "").strip(),
            "chapter": chapter.number,
        }
    )


def _state_bucket_for_change(change: dict[str, Any]) -> str | None:
    text = " ".join(str(change.get(key, "")) for key in ("type", "target", "change"))
    if any(term in text for term in ("人物", "角色")):
        return "characters"
    if "关系" in text:
        return "relationships"
    if any(term in text for term in ("地点", "场景", "位置")):
        return "locations"
    if any(term in text for term in ("势力", "组织", "阵营")):
        return "factions"
    if any(term in text for term in ("资源", "道具", "物品", "地图")):
        return "resources"
    if any(term in text for term in ("伏笔", "线索", "信息")):
        return "foreshadowing"
    return None


def _is_low_information_state_change(target: str, detail: str) -> bool:
    if target != "待确认":
        return False
    return detail in {
        "人物",
        "关系",
        "地点",
        "资源",
        "伏笔",
        "信息暴露",
        "characters",
        "relationships",
        "locations",
        "resources",
        "foreshadowing",
        "information_exposure",
        "foreshadowing_and_info",
        "foreshadowing_and_information",
    }


def _index_accepted_chapter(
    session: Session,
    chapter: Chapter,
    trusted_state: dict[str, Any],
    trusted_state_version: int,
    embedding_client: TextEmbeddingClient | None,
) -> None:
    chapter_text = "\n".join(
        part
        for part in (
            f"第 {chapter.number:02d} 章《{chapter.title}》",
            chapter.summary,
            chapter.final_text,
        )
        if part
    )
    embedding_vector, embedding_model, embedding_error = _embedding_for_index(
        embedding_client,
        chapter_text,
    )
    index_text(
        session,
        book_id=chapter.book_id,
        source_type="accepted_chapter",
        source_id=str(chapter.id),
        text=chapter_text,
        metadata={
            "kind": "章节正文",
            "chapter": chapter.number,
            "trusted_state_version": trusted_state_version,
        },
        embedding_vector=embedding_vector,
        embedding_model=embedding_model,
        embedding_error=embedding_error,
        commit=False,
    )

    state_text = _trusted_state_index_text(chapter, trusted_state)
    if state_text:
        embedding_vector, embedding_model, embedding_error = _embedding_for_index(
            embedding_client,
            state_text,
        )
        index_text(
            session,
            book_id=chapter.book_id,
            source_type="trusted_state",
            source_id=f"chapter-{chapter.id}",
            text=state_text,
            metadata={
                "kind": "可信状态",
                "chapter": chapter.number,
                "trusted_state_version": trusted_state_version,
            },
            embedding_vector=embedding_vector,
            embedding_model=embedding_model,
            embedding_error=embedding_error,
            commit=False,
        )


def _embedding_client_from_session(session: Session) -> TextEmbeddingClient | None:
    return embedding_client_from_provider_config(
        get_provider_config(session),
        get_provider_config_validation(session),
    )


def _embedding_for_index(
    client: TextEmbeddingClient | None,
    text: str,
) -> tuple[list[float] | None, str | None, str | None]:
    if client is None:
        return None, None, None
    try:
        return client.embed_text(text), client.model, None
    except Exception as error:  # noqa: BLE001
        return None, None, str(error) or type(error).__name__


def _trusted_state_index_text(chapter: Chapter, trusted_state: dict[str, Any]) -> str:
    lines = [f"第 {chapter.number:02d} 章《{chapter.title}》状态变化"]
    for change in chapter.state_delta.get("changes", []):
        if not isinstance(change, dict):
            continue
        lines.append(
            " / ".join(
                text
                for text in (
                    str(change.get("type") or "").strip(),
                    str(change.get("target") or "").strip(),
                    str(change.get("change") or "").strip(),
                )
                if text
            )
        )
    for bucket in (
        "characters",
        "relationships",
        "locations",
        "factions",
        "resources",
        "foreshadowing",
    ):
        values = trusted_state.get(bucket, [])
        if values:
            lines.append(f"{bucket}: {json.dumps(values[-3:], ensure_ascii=False)}")
    return "\n".join(line for line in lines if line)


def _trace_prompt_metadata(chapter: Chapter, prompt_id: str) -> tuple[str, str, int]:
    try:
        asset = load_prompt_by_id(prompt_id)
        messages = render_prompt_messages(asset, _trace_payload(chapter))
        prompt_chars = sum(len(message["content"]) for message in messages)
        return asset.version, asset.source, max(1, prompt_chars)
    except FileNotFoundError:
        return PROMPT_VERSION, "unknown", 1


def _trace_payload(chapter: Chapter) -> dict[str, Any]:
    return {
        "chapter_number": chapter.number,
        "chapter_title": chapter.title,
        "plan": chapter.plan,
        "context_package": chapter.context_package,
        "draft_text": chapter.draft_text,
        "state_delta": chapter.state_delta,
        "audit_report": chapter.audit_report,
    }


def _stage_completion_text(chapter: Chapter, stage_key: str) -> str:
    match stage_key:
        case "plan":
            return json.dumps(chapter.plan, ensure_ascii=False, sort_keys=True)
        case "context":
            return json.dumps(chapter.context_package, ensure_ascii=False, sort_keys=True)
        case "draft":
            return chapter.draft_text
        case "extract_state":
            return json.dumps(chapter.state_delta, ensure_ascii=False, sort_keys=True)
        case "audit":
            return json.dumps(chapter.audit_report, ensure_ascii=False, sort_keys=True)
        case "revise":
            return chapter.revised_text
    return ""
