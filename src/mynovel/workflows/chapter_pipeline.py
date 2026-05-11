from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from typing import Any, Protocol

from sqlmodel import Session

from mynovel.domain.models import BookStatus, Canon, Chapter, ChapterStatus, RunTrace, utc_now
from mynovel.domain.repositories import get_book, get_chapter, get_latest_canon
from mynovel.llm.openai_compatible import ChatRequest, OpenAICompatibleClient
from mynovel.prompts.registry import load_prompt_by_id, render_prompt_messages
from mynovel.workflows.open_book_blueprint import extract_chat_content
from mynovel.workflows.retrieval import index_text
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
    def __init__(self, stage: str, error: Exception) -> None:
        super().__init__(str(error))
        self.stage = stage
        self.error = error


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
) -> Chapter:
    chapter = _required_chapter(session, chapter_id)
    book = get_book(session, chapter.book_id)
    canon = get_latest_canon(session, chapter.book_id)
    if book is None or canon is None:
        raise ValueError("Chapter must belong to a book with trusted state.")

    chapter.status = ChapterStatus.RUNNING
    model_label = model_name or "本地演示模型"
    try:
        if model_client is None:
            _run_simulated_pipeline(book.title, canon, chapter)
        else:
            _run_model_pipeline(book.title, canon, chapter, model_client)
    except Exception as error:  # noqa: BLE001
        failed_stage = error.stage if isinstance(error, ChapterStageError) else "unknown"
        return _record_pipeline_failure(session, chapter, model_label, failed_stage, error)
    chapter.summary = _summarize_chapter(chapter)
    chapter.word_count = len(chapter.revised_text)
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
    _index_accepted_chapter(session, chapter, updated_content, trusted_state_version)
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
    if chapter.status not in {ChapterStatus.AWAITING_REVIEW, ChapterStatus.NEEDS_REVISION}:
        raise ValueError("Only review-stage chapters can be repaired.")

    if model_client is None:
        chapter.revised_text = _repair_text_locally(chapter)
    else:
        chapter.revised_text = _complete_text_stage(
            model_client,
            "revise",
            _build_repair_messages(chapter, reviewer_note),
        )
    chapter.word_count = len(chapter.revised_text)
    chapter.status = ChapterStatus.AWAITING_REVIEW
    chapter.reviewer_note = reviewer_note
    chapter.updated_at = utc_now()

    session.add(chapter)
    session.add(
        RunTrace(
            book_id=chapter.book_id,
            stage="修复问题",
            model=model_name or "本地演示模型",
            cost={"estimated": 0},
            metadata_={"chapter": chapter.number, "status": chapter.status.value},
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


def _run_simulated_pipeline(book_title: str, canon: Canon, chapter: Chapter) -> None:
    chapter.context_package = _build_context_package(canon, chapter)
    chapter.draft_text = _generate_draft_text(book_title, chapter)
    chapter.audit_report = _audit_chapter(chapter)
    chapter.revised_text = _revise_text(chapter.draft_text, chapter.audit_report)
    chapter.state_delta = _extract_state_delta(chapter)


def _run_model_pipeline(
    book_title: str,
    canon: Canon,
    chapter: Chapter,
    model_client: ChapterModelClient,
) -> None:
    chapter.plan = _complete_json_stage(
        model_client,
        "plan",
        _build_plan_messages(book_title, canon, chapter),
        {"goal", "must_write", "forbidden_drift", "word_budget", "ending_hook"},
    )
    chapter.context_package = _build_context_package(canon, chapter)
    chapter.draft_text = _complete_text_stage(
        model_client,
        "draft",
        _build_draft_messages(book_title, chapter),
    )
    chapter.state_delta = _complete_json_stage(
        model_client,
        "extract_state",
        _build_extract_state_messages(chapter),
        {"chapter", "changes"},
    )
    chapter.audit_report = _complete_json_stage(
        model_client,
        "audit",
        _build_audit_messages(chapter),
        {"risk_level", "issues", "suggestions"},
    )
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
    try:
        raw = model_client.complete(stage, messages, "json")
        data = _parse_json_object(raw)
        missing = sorted(required_fields - set(data))
        if missing:
            raise ValueError(f"Chapter stage {stage} missing fields: {', '.join(missing)}")
        return data
    except Exception as error:  # noqa: BLE001
        raise ChapterStageError(stage, error) from error


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
        raise ChapterStageError(stage, error) from error


def _parse_json_object(raw_text: str) -> dict[str, Any]:
    text = _strip_code_fence(raw_text.strip())
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Chapter model response must be a JSON object.")
    return data


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        first = lines[0].strip()
        if first in {"```", "```json"}:
            return "\n".join(lines[1:-1]).strip()
    return text


def _build_plan_messages(book_title: str, canon: Canon, chapter: Chapter) -> list[dict[str, str]]:
    payload = {
        "book_title": book_title,
        "trusted_state": canon.content,
        "chapter": {
            "number": chapter.number,
            "title": chapter.title,
            "current_goal": chapter.plan.get("goal", ""),
        },
    }
    return _json_instruction_messages(
        "你是网文章节导演。请为当前章节生成可执行的章节计划，只输出 JSON。",
        "必须包含 goal, must_write, forbidden_drift, word_budget, ending_hook。",
        payload,
    )


def _build_draft_messages(book_title: str, chapter: Chapter) -> list[dict[str, str]]:
    payload = {
        "book_title": book_title,
        "chapter": {
            "number": chapter.number,
            "title": chapter.title,
            "plan": chapter.plan,
            "context": chapter.context_package,
        },
    }
    return _text_instruction_messages(
        "你是网文连载正文生成器。根据章节计划和可信上下文写本章草稿。",
        "只输出章节正文，不要解释，不要附加元信息。",
        payload,
    )


def _build_extract_state_messages(chapter: Chapter) -> list[dict[str, str]]:
    payload = {
        "chapter": {"number": chapter.number, "title": chapter.title, "plan": chapter.plan},
        "draft_text": chapter.draft_text,
    }
    return _json_instruction_messages(
        "你是小说状态变化提取器。从草稿提取待人工验证的状态变化，只输出 JSON。",
        "必须包含 chapter 与 changes。changes 只记录人物、关系、地点、资源、伏笔和信息暴露变化。",
        payload,
    )


def _build_audit_messages(chapter: Chapter) -> list[dict[str, str]]:
    payload = {
        "chapter": {"number": chapter.number, "title": chapter.title, "plan": chapter.plan},
        "context": chapter.context_package,
        "draft_text": chapter.draft_text,
        "state_delta": chapter.state_delta,
    }
    return _json_instruction_messages(
        "你是连载章节审计员。检查连续性、因果、动机、伏笔、节奏、字数和结尾钩子。",
        "必须包含 risk_level, issues, suggestions。issues 内每项包含 severity, title, resolved。",
        payload,
    )


def _build_revise_messages(chapter: Chapter) -> list[dict[str, str]]:
    payload = {
        "chapter": {"number": chapter.number, "title": chapter.title, "plan": chapter.plan},
        "draft_text": chapter.draft_text,
        "audit_report": chapter.audit_report,
        "state_delta": chapter.state_delta,
    }
    return _text_instruction_messages(
        "你是连载章节修订器。根据审计报告修订正文，尽量解决可自动修复的问题。",
        "只输出修订后的最终候选正文，不要解释。",
        payload,
    )


def _build_repair_messages(chapter: Chapter, reviewer_note: str | None) -> list[dict[str, str]]:
    payload = {
        "chapter": {"number": chapter.number, "title": chapter.title, "plan": chapter.plan},
        "draft_text": chapter.draft_text,
        "current_revised_text": chapter.revised_text,
        "audit_report": chapter.audit_report,
        "state_delta": chapter.state_delta,
        "reviewer_note": reviewer_note,
    }
    return _text_instruction_messages(
        "你是连载章节修复器。根据审核意见和审计问题修复正文。",
        "只输出修复后的完整正文，不要解释。",
        payload,
    )


def _json_instruction_messages(
    system_prompt: str,
    schema_prompt: str,
    payload: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"{schema_prompt}\n{json.dumps(payload, ensure_ascii=False)}",
        },
    ]


def _text_instruction_messages(
    system_prompt: str,
    instruction: str,
    payload: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"{instruction}\n{json.dumps(payload, ensure_ascii=False)}",
        },
    ]


def _build_context_package(canon: Canon, chapter: Chapter) -> dict:
    return {
        "trusted_state": {
            "version": canon.version,
            "book": canon.content.get("book", {}),
            "characters": canon.content.get("characters", []),
            "foreshadowing": canon.content.get("foreshadowing", []),
            "chapter_summaries": canon.content.get("chapter_summaries", []),
        },
        "chapter_goal": chapter.plan.get("goal", ""),
        "must_write": chapter.plan.get("must_write", []),
        "forbidden_drift": ["不要改写已锁定设定", "不要让状态变化绕过人工审核"],
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


def _repair_text_locally(chapter: Chapter) -> str:
    source_text = chapter.revised_text or chapter.draft_text
    repaired = _revise_text(source_text, chapter.audit_report or {})
    if repaired != source_text:
        return repaired
    return f"{source_text}\n\n修复补充：已按审核意见补强人物动机、因果链和章节钩子。"


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

    content.setdefault(bucket, []).append(
        {
            "name": target or detail[:32],
            "detail": detail,
            "type": str(change.get("type") or "").strip(),
            "chapter": chapter.number,
            "chapter_title": chapter.title,
            "updated_at": utc_now().isoformat(),
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


def _index_accepted_chapter(
    session: Session,
    chapter: Chapter,
    trusted_state: dict[str, Any],
    trusted_state_version: int,
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
        commit=False,
    )

    state_text = _trusted_state_index_text(chapter, trusted_state)
    if state_text:
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
            commit=False,
        )


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
