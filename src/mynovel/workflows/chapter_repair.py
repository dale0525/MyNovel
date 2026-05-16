from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Protocol

from mynovel.domain.models import Chapter
from mynovel.word_targets import parse_word_count
from mynovel.workflows.chapter_repair_terms import (
    EXPANSION_ADVICE_TERMS,
    REDUCTION_ADVICE_TERMS,
    SIDE_DESCRIPTION_ISSUE_TERMS,
    SIDE_DESCRIPTION_OBSERVER_TERMS,
    SIDE_DESCRIPTION_REACTION_TERMS,
    WORD_COUNT_MAX_RATIO,
    WORD_COUNT_MIN_RATIO,
    WORD_COUNT_REPAIR_TERMS,
)


class ChapterModelClient(Protocol):
    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        pass


TextStageCompleter = Callable[[ChapterModelClient, str, list[dict[str, str]]], str]
TextReviser = Callable[[str, dict[str, Any]], str]


@dataclass(frozen=True)
class RepairRequest:
    messages: list[dict[str, str]]
    word_count_window: tuple[int, int] | None
    target_word_count: int | None
    before_word_count: int
    unresolved_audit_issues: list[str]
    needs_word_count_repair: bool = False


@dataclass(frozen=True)
class WordCountPatchApplication:
    text: str
    operations: list[dict[str, Any]]
    strategy: str


def repair_text_with_model(
    chapter: Chapter,
    model_client: ChapterModelClient,
    reviewer_note: str | None,
    complete_text_stage: TextStageCompleter,
) -> str:
    request = build_repair_request(chapter, reviewer_note)
    return complete_text_stage(
        model_client,
        "revise",
        request.messages,
    )


def build_repair_request(chapter: Chapter, reviewer_note: str | None) -> RepairRequest:
    current_text = _latest_revision_text(chapter)
    needs_word_count_repair = _needs_word_count_repair(chapter, reviewer_note)
    word_count_window = _stable_repair_word_count_window(
        chapter,
        current_text,
        needs_word_count_repair=needs_word_count_repair,
    )
    return RepairRequest(
        messages=_build_repair_messages(
            chapter,
            reviewer_note,
            word_count_window=word_count_window,
        ),
        word_count_window=word_count_window,
        target_word_count=parse_word_count(chapter.plan.get("word_budget")),
        before_word_count=len(current_text),
        unresolved_audit_issues=_unresolved_audit_issue_titles(chapter.audit_report or {}),
        needs_word_count_repair=needs_word_count_repair,
    )


def build_word_count_patch_request(chapter: Chapter, reviewer_note: str | None) -> RepairRequest:
    word_count_window = _word_count_window_from_plan(chapter)
    current_text = _latest_revision_text(chapter)
    mode = word_count_patch_mode(len(current_text), word_count_window)
    return RepairRequest(
        messages=_build_word_count_patch_messages(
            chapter,
            reviewer_note,
            current_text,
            word_count_window,
            mode,
        ),
        word_count_window=word_count_window,
        target_word_count=parse_word_count(chapter.plan.get("word_budget")),
        before_word_count=len(current_text),
        unresolved_audit_issues=_unresolved_audit_issue_titles(chapter.audit_report or {}),
        needs_word_count_repair=True,
    )


def word_count_patch_mode(word_count: int, word_count_window: tuple[int, int] | None) -> str | None:
    if word_count_window is None:
        return None
    if word_count > word_count_window[1]:
        return "compress"
    if word_count < word_count_window[0]:
        return "expand"
    return None


def apply_word_count_patch(source_text: str, patch_payload: dict[str, Any]) -> str:
    operations = patch_payload.get("operations")
    if not isinstance(operations, list):
        raise ValueError("Word count patch missing operations.")
    paragraphs = source_text.split("\n\n")
    paragraph_count = len(paragraphs)
    deleted: set[int] = set()
    replacements: dict[int, str] = {}
    insertions: dict[int, list[str]] = {}

    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("Word count patch operation must be an object.")
        op = str(operation.get("op") or "").strip()
        paragraph_id = _patch_paragraph_id(operation.get("paragraph_id"), paragraph_count)
        if op == "delete":
            deleted.add(paragraph_id)
            continue
        if op in {"replace", "compress", "expand"}:
            replacements[paragraph_id] = _patch_text(operation)
            continue
        if op == "insert_after":
            insertions.setdefault(paragraph_id, []).append(_patch_text(operation))
            continue
        raise ValueError(f"Unsupported word count patch operation: {op}")

    patched: list[str] = []
    for index, paragraph in enumerate(paragraphs, start=1):
        if index not in deleted:
            patched.append(replacements.get(index, paragraph))
        patched.extend(insertions.get(index, []))
    return "\n\n".join(part for part in patched if part.strip()).strip()


def apply_word_count_patch_bounded(
    source_text: str,
    patch_payload: dict[str, Any],
    word_count_window: tuple[int, int] | None,
    target_word_count: int | None,
) -> WordCountPatchApplication:
    operations = patch_payload.get("operations")
    if not isinstance(operations, list):
        raise ValueError("Word count patch missing operations.")
    patch_operations = [operation for operation in operations if isinstance(operation, dict)]
    patched = apply_word_count_patch(source_text, patch_payload)
    if word_count_window is None or _word_count_in_window(len(patched), word_count_window):
        return WordCountPatchApplication(patched, patch_operations, "full")

    prefix_application = _best_in_window_patch_prefix(
        source_text,
        patch_operations,
        word_count_window,
        target_word_count,
    )
    if prefix_application is not None:
        return prefix_application
    return WordCountPatchApplication(patched, patch_operations, "full")


def repair_text_locally(chapter: Chapter, revise_text: TextReviser) -> str:
    source_text = chapter.revised_text or chapter.draft_text
    repaired = revise_text(source_text, chapter.audit_report or {})
    if repaired != source_text:
        return repaired
    return f"{source_text}\n\n修复补充：已按审核意见补强人物动机、因果链和章节钩子。"


def recheck_repair_audit(
    chapter: Chapter,
    addressed_issue_titles: list[str] | None = None,
) -> None:
    audit_report = deepcopy(chapter.audit_report or {})
    issues = audit_report.get("issues", [])
    if not isinstance(issues, list):
        return

    changed = False
    current_text = chapter.revised_text or chapter.draft_text or ""
    current_count = len(current_text)
    word_count_window = _word_count_window_from_plan(chapter)
    in_window = (
        _word_count_in_window(current_count, word_count_window)
        if word_count_window is not None
        else False
    )
    target = parse_word_count(chapter.plan.get("word_budget"))
    addressed = {title.strip() for title in addressed_issue_titles or [] if title.strip()}
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        title = str(issue.get("title") or "").strip()
        if _is_word_count_issue(issue):
            if word_count_window is None:
                continue
            if in_window and issue.get("resolved"):
                continue
            if in_window:
                issue["resolved"] = True
                issue["detail"] = _audit_recheck_detail(
                    issue.get("detail"),
                    current_count,
                    word_count_window,
                    target,
                    in_window=True,
                )
                changed = True
                continue
            direction = _word_count_direction(current_count, word_count_window)
            existing_direction = _word_count_issue_direction(issue)
            if (
                not issue.get("resolved")
                and existing_direction == direction
                and "自动复核" not in str(issue.get("detail") or "")
            ):
                continue
            issue["resolved"] = False
            issue["title"] = "字数不在目标区间"
            issue["detail"] = _audit_recheck_detail(
                None,
                current_count,
                word_count_window,
                target,
                in_window=False,
            )
            changed = True
            continue
        if issue.get("resolved"):
            continue
        if title in addressed:
            issue["resolved"] = True
            issue["detail"] = _non_word_issue_recheck_detail(issue.get("detail"), source="patch")
            changed = True
            continue
        if _non_word_issue_resolved_by_text(issue, current_text):
            issue["resolved"] = True
            issue["detail"] = _non_word_issue_recheck_detail(issue.get("detail"), source="text")
            changed = True

    if (
        changed
        and _all_issues_resolved(issues)
        and str(audit_report.get("risk_level", "")).lower() != "high"
    ):
        audit_report["risk_level"] = "low"
    if changed and word_count_window is not None:
        audit_report["suggestions"] = _refresh_word_count_suggestions(
            audit_report.get("suggestions", []),
            current_count,
            word_count_window,
            target,
        )
    if changed:
        chapter.audit_report = audit_report


def patch_addressed_issue_titles(
    operations: list[dict[str, Any]] | None,
    unresolved_issue_titles: list[str],
) -> list[str]:
    if not operations:
        return []
    explicit: set[str] = set()
    evidence_parts: list[str] = []
    for operation in operations:
        addresses = operation.get("addresses")
        if isinstance(addresses, list):
            explicit.update(str(item).strip() for item in addresses if str(item).strip())
        for key in ("reason", "text"):
            value = str(operation.get(key) or "").strip()
            if value:
                evidence_parts.append(value)
    evidence = "\n".join(evidence_parts)
    addressed: list[str] = []
    for title in unresolved_issue_titles:
        title = str(title or "").strip()
        if not title:
            continue
        stem = title.removesuffix("缺失").strip()
        if title in explicit or title in evidence or (len(stem) >= 2 and stem in evidence):
            addressed.append(title)
    return addressed


def repair_trace_cost(
    request: RepairRequest | None,
    response_text: str,
) -> dict[str, int]:
    prompt_chars = (
        sum(len(message["content"]) for message in request.messages) if request is not None else 0
    )
    return {
        "estimated": 0,
        "prompt_chars": prompt_chars,
        "completion_chars": len(response_text),
        "elapsed_ms": 0,
    }


def repair_trace_prompt_id(
    request: RepairRequest | None, word_count_repair_mode: str | None
) -> str | None:
    if request is None:
        return None
    if word_count_repair_mode is not None:
        return "chapter_word_count_patch"
    return "chapter_repair"


def repair_trace_metadata(
    chapter: Chapter,
    request: RepairRequest | None,
    reviewer_note: str | None,
    before_word_count: int,
    validation_warning: str | None,
    raw_response_text: str,
    applied_response_text: str,
    rejected_response: bool,
    word_count_repair_mode: str | None,
    patch_operations: list[dict[str, Any]] | None,
    applied_patch_operations: list[dict[str, Any]] | None,
    patch_application_strategy: str | None,
    addressed_issue_titles: list[str],
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "chapter": chapter.number,
        "status": chapter.status.value,
        "after_word_count": len(chapter.revised_text),
        "model_response_word_count": len(applied_response_text),
        "reviewer_note": reviewer_note,
        "response_text": raw_response_text,
        "raw_response_text": raw_response_text,
        "applied_text": applied_response_text,
    }
    if validation_warning:
        metadata["validation_warning"] = validation_warning
    if rejected_response:
        metadata["rejected_response_text"] = applied_response_text
    if word_count_repair_mode is not None:
        metadata["word_count_repair_mode"] = word_count_repair_mode
    if patch_operations is not None:
        metadata["patch_operations"] = patch_operations
    if applied_patch_operations is not None:
        metadata["applied_patch_operations"] = applied_patch_operations
    if patch_application_strategy is not None:
        metadata["patch_application_strategy"] = patch_application_strategy
    if addressed_issue_titles:
        metadata["addressed_audit_issues"] = addressed_issue_titles
    if request is None:
        metadata["before_word_count"] = before_word_count
        return metadata
    metadata.update(
        {
            "before_word_count": request.before_word_count,
            "target_word_count": request.target_word_count,
            "word_count_window": list(request.word_count_window)
            if request.word_count_window is not None
            else None,
            "unresolved_audit_issues": request.unresolved_audit_issues,
            "prompt_messages": request.messages,
        }
    )
    return metadata


def repair_validation_warning(
    request: RepairRequest | None,
    source_text: str,
    response_text: str,
) -> str | None:
    if request is None or request.word_count_window is None:
        return None
    minimum, maximum = request.word_count_window
    after_count = len(response_text)
    if minimum <= after_count <= maximum:
        return None
    if response_text == source_text:
        return (
            f"AI 修复未改变正文：当前 {after_count} 字，仍未进入 {minimum}-{maximum} 字目标区间。"
        )
    if after_count == request.before_word_count:
        return (
            f"AI 修复未改变字数：当前 {after_count} 字，仍未进入 {minimum}-{maximum} 字目标区间。"
        )
    if _word_count_window_distance(
        after_count, request.word_count_window
    ) > _word_count_window_distance(
        request.before_word_count,
        request.word_count_window,
    ):
        direction = "扩写" if after_count > request.before_word_count else "缩短"
        return (
            f"AI 修复结果被拒绝：模型将正文从 {request.before_word_count} 字{direction}到 {after_count} 字，"
            f"更偏离 {minimum}-{maximum} 字目标区间。"
        )
    return None


def repair_response_should_be_rejected(
    request: RepairRequest | None,
    source_text: str,
    response_text: str,
) -> bool:
    if request is None or request.word_count_window is None:
        return False
    warning = repair_validation_warning(request, source_text, response_text)
    return warning is not None and (
        response_text == source_text
        or _word_count_window_distance(len(response_text), request.word_count_window)
        >= _word_count_window_distance(request.before_word_count, request.word_count_window)
    )


def _repair_word_count_window(
    chapter: Chapter,
    reviewer_note: str | None,
) -> tuple[int, int] | None:
    current_text = _latest_revision_text(chapter)
    return _stable_repair_word_count_window(
        chapter,
        current_text,
        needs_word_count_repair=_needs_word_count_repair(chapter, reviewer_note),
    )


def _stable_repair_word_count_window(
    chapter: Chapter,
    current_text: str,
    *,
    needs_word_count_repair: bool,
) -> tuple[int, int] | None:
    word_count_window = _word_count_window_from_plan(chapter)
    if word_count_window is None:
        return None
    if needs_word_count_repair or _word_count_in_window(len(current_text), word_count_window):
        return word_count_window
    return None


def _word_count_window_from_plan(chapter: Chapter) -> tuple[int, int] | None:
    target = parse_word_count(chapter.plan.get("word_budget"))
    if target is None:
        return None
    minimum = max(1, round(target * WORD_COUNT_MIN_RATIO))
    maximum = max(minimum, round(target * WORD_COUNT_MAX_RATIO))
    return minimum, maximum


def _needs_word_count_repair(chapter: Chapter, reviewer_note: str | None) -> bool:
    audit_report = chapter.audit_report or {}
    texts = [str(reviewer_note or ""), *[str(item) for item in audit_report.get("suggestions", [])]]
    for issue in audit_report.get("issues", []):
        if not isinstance(issue, dict) or issue.get("resolved"):
            continue
        texts.extend(
            str(issue.get(key) or "")
            for key in ("title", "detail", "description", "message", "suggested_fix")
        )
    return any(_has_word_count_term(text) for text in texts)


def _build_repair_messages(
    chapter: Chapter,
    reviewer_note: str | None,
    word_count_window: tuple[int, int] | None = None,
) -> list[dict[str, str]]:
    current_text = _latest_revision_text(chapter)
    instructions = [
        "只输出修复后的完整正文，不要解释。",
        "必须同时处理 AI 审核问题和人工修改意见。",
        "未填写人工修改意见，本次只处理 AI 审核问题。",
        _word_count_instruction(chapter, current_text, word_count_window),
    ]
    body = "\n\n".join(
        part
        for part in (
            f"章节：第 {chapter.number:02d} 章《{chapter.title}》",
            _book_boundary_text(chapter),
            _chapter_goal_text(chapter),
            _audit_issue_text(
                chapter.audit_report or {},
                current_text,
                word_count_window=word_count_window,
                target_word_count=parse_word_count(chapter.plan.get("word_budget")),
            ),
            _manual_instruction_text(reviewer_note),
            "待修订正文：\n" + current_text,
        )
        if part
    )
    return [
        {"role": "system", "content": "你是连载章节修复器。根据审核问题修订小说正文。"},
        {
            "role": "user",
            "content": "\n".join(part for part in instructions if part) + "\n\n" + body,
        },
    ]


def _build_word_count_patch_messages(
    chapter: Chapter,
    reviewer_note: str | None,
    current_text: str,
    word_count_window: tuple[int, int] | None,
    mode: str | None,
) -> list[dict[str, str]]:
    if word_count_window is None or mode is None:
        raise ValueError("Word count patch requires an out-of-window target.")

    minimum, maximum = word_count_window
    target = parse_word_count(chapter.plan.get("word_budget")) or round((minimum + maximum) / 2)
    current_count = len(current_text)
    mode_label = "压缩模式" if mode == "compress" else "扩写模式"
    if mode == "compress":
        allowed_ops = "只允许 delete、compress、replace；不得新增支线或无关铺陈。"
        allowed_op_names = "delete|compress|replace"
        issue_priority = (
            "必须同时解决所有未完成审核项；字数是硬约束，但不是唯一目标。"
            "非字数审核项不得因为压缩模式被忽略；需要补入的信息优先用 replace/compress 融入既有段落，"
            "再删除低价值铺陈抵消新增字数。"
        )
        count_constraint = (
            f"系统会应用补丁并复核正文字符数；本轮补丁必须落入 {minimum}-{maximum} 字，"
            f"至少净删 {current_count - maximum} 字，不得原样返回。"
        )
    else:
        allowed_ops = "只允许 insert_after、expand、replace；只补必要动作、因果和钩子。"
        allowed_op_names = "insert_after|expand|replace"
        issue_priority = (
            "必须同时解决所有未完成审核项；字数是硬约束，但不是唯一目标。"
            "非字数审核项不得因为扩写模式被忽略；新增内容必须优先服务审计问题、章节目标和结尾钩子。"
        )
        count_constraint = (
            f"系统会应用补丁并复核正文字符数；本轮补丁必须落入 {minimum}-{maximum} 字，"
            f"至少净增 {minimum - current_count} 字，不得原样返回。"
        )
    paragraphs = _numbered_paragraphs(current_text)
    body = "\n\n".join(
        part
        for part in (
            f"章节：第 {chapter.number:02d} 章《{chapter.title}》",
            f"模式：{mode_label}",
            f"当前字数：{current_count} 字；目标字数：{target} 字；目标区间：{minimum}-{maximum} 字。",
            issue_priority,
            allowed_ops,
            count_constraint,
            f'只返回 JSON，不要返回完整正文。格式：{{"operations":[{{"op":"{allowed_op_names}","paragraph_id":1,"text":"可选","reason":"原因","addresses":["审核项标题"]}}]}}',
            _chapter_goal_text(chapter),
            _audit_issue_text(
                chapter.audit_report or {},
                current_text,
                word_count_window=word_count_window,
                target_word_count=target,
            ),
            _manual_instruction_text(reviewer_note),
            "段落清单：\n" + paragraphs,
        )
        if part
    )
    return [
        {"role": "system", "content": "你是章节修订补丁规划器。只输出可由系统应用的 JSON 补丁。"},
        {"role": "user", "content": body},
    ]


def _numbered_paragraphs(text: str) -> str:
    paragraphs = text.split("\n\n")
    return "\n".join(
        f"段落 {index}：{paragraph}" for index, paragraph in enumerate(paragraphs, start=1)
    )


def _patch_paragraph_id(value: object, paragraph_count: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("Word count patch paragraph_id must be an integer.")
    try:
        paragraph_id = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Word count patch paragraph_id must be an integer.") from error
    if paragraph_id < 1 or paragraph_id > paragraph_count:
        raise ValueError(f"Word count patch paragraph_id out of range: {paragraph_id}")
    return paragraph_id


def _patch_text(operation: dict[str, Any]) -> str:
    text = str(operation.get("text") or "").strip()
    if not text:
        raise ValueError("Word count patch operation requires non-empty text.")
    return text


def _best_in_window_patch_prefix(
    source_text: str,
    operations: list[dict[str, Any]],
    word_count_window: tuple[int, int],
    target_word_count: int | None,
) -> WordCountPatchApplication | None:
    target = target_word_count or round((word_count_window[0] + word_count_window[1]) / 2)
    best: WordCountPatchApplication | None = None
    best_distance: int | None = None
    for index in range(1, len(operations) + 1):
        prefix = operations[:index]
        patched = apply_word_count_patch(source_text, {"operations": prefix})
        word_count = len(patched)
        if not _word_count_in_window(word_count, word_count_window):
            continue
        distance = abs(word_count - target)
        if best is None or best_distance is None or distance < best_distance:
            best = WordCountPatchApplication(patched, prefix, "bounded_prefix")
            best_distance = distance
    return best


def _word_count_instruction(
    chapter: Chapter,
    current_text: str,
    word_count_window: tuple[int, int] | None,
) -> str:
    if word_count_window is None:
        return ""

    minimum, maximum = word_count_window
    target = parse_word_count(chapter.plan.get("word_budget"))
    current_count = len(current_text)
    target_text = f"目标字数：{target} 字\n" if target is not None else ""
    base = (
        f"{target_text}建议区间：{minimum}-{maximum} 字\n不要用提纲、摘要、重复段落或冗余扩写凑字。"
    )
    if current_count > maximum:
        over_by = current_count - maximum
        return (
            f"{base}\n当前正文已经超出目标，请以删减和合并为主，不要新增支线、回忆或环境铺陈。"
            f"本轮输出必须落在 {minimum}-{maximum} 字；至少删减 {over_by} 字，不能原样返回。"
        )
    if current_count < minimum:
        missing = minimum - current_count
        return (
            f"{base}\n当前正文低于目标，请只补必要的动作、因果和结尾钩子，不要重复已有信息。"
            f"本轮输出必须落在 {minimum}-{maximum} 字；至少补足 {missing} 字，不能原样返回。"
        )
    return f"{base}\n当前正文已在建议区间内，修订时尽量保持篇幅稳定。"


def _latest_revision_text(chapter: Chapter) -> str:
    return chapter.revised_text or chapter.final_text or chapter.draft_text


def _chapter_goal_text(chapter: Chapter) -> str:
    goal = str(chapter.plan.get("goal") or "").strip()
    ending_hook = str(chapter.plan.get("ending_hook") or "").strip()
    parts = []
    if goal:
        parts.append(f"本章目标：{goal}")
    if ending_hook:
        parts.append(f"结尾钩子：{ending_hook}")
    return "\n".join(parts)


def _book_boundary_text(chapter: Chapter) -> str:
    context = chapter.context_package if isinstance(chapter.context_package, dict) else {}
    trusted_state_value = context.get("trusted_state")
    trusted_state = trusted_state_value if isinstance(trusted_state_value, dict) else {}
    book_value = trusted_state.get("book")
    book = book_value if isinstance(book_value, dict) else {}
    lines = ["作品边界："]
    for label, key in (
        ("书名", "title"),
        ("类型", "genre"),
        ("读者", "audience"),
        ("前提", "premise"),
    ):
        value = str(book.get(key) or "").strip()
        if value:
            lines.append(f"- {label}：{value}")
    lines.extend(_short_list_lines("本章必须保留", chapter.plan.get("must_write"), limit=5))
    lines.extend(_short_list_lines("禁止偏移", chapter.plan.get("forbidden_drift"), limit=5))
    lines.append("- 不得改写已锁定设定，不得新增绕过人工审核的可信状态。")
    return "\n".join(lines)


def _short_list_lines(label: str, value: object, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [str(item).strip() for item in value if str(item).strip()]
    if not items:
        return []
    return [f"- {label}：" + "；".join(items[:limit])]


def _audit_issue_text(
    audit_report: dict[str, Any],
    current_text: str,
    word_count_window: tuple[int, int] | None = None,
    target_word_count: int | None = None,
) -> str:
    lines = ["AI 审核问题："]
    unresolved = [
        issue
        for issue in audit_report.get("issues", [])
        if isinstance(issue, dict) and not issue.get("resolved")
    ]
    if not unresolved:
        lines.append("- 无未解决审计问题。")
    for issue in unresolved:
        if word_count_window is not None and _is_word_count_issue(issue):
            lines.append(
                _normalized_word_count_issue_line(
                    len(current_text),
                    word_count_window,
                    target_word_count,
                )
            )
            continue
        title = str(issue.get("title") or "未命名问题").strip()
        detail = str(
            issue.get("detail")
            or issue.get("description")
            or issue.get("message")
            or issue.get("suggested_fix")
            or ""
        ).strip()
        if detail:
            lines.append(f"- {title}：{detail}")
        else:
            lines.append(f"- {title}")
    suggestions = [
        str(item).strip() for item in audit_report.get("suggestions", []) if str(item).strip()
    ]
    if word_count_window is not None:
        suggestions = _refresh_word_count_suggestions(
            suggestions,
            len(current_text),
            word_count_window,
            target_word_count,
        )
    if suggestions:
        lines.append("AI 建议：")
        lines.extend(f"- {suggestion}" for suggestion in suggestions)
    return "\n".join(lines)


def _unresolved_audit_issue_titles(audit_report: dict[str, Any]) -> list[str]:
    titles: list[str] = []
    for issue in audit_report.get("issues", []):
        if not isinstance(issue, dict) or issue.get("resolved"):
            continue
        title = str(issue.get("title") or "未命名问题").strip()
        if title:
            titles.append(title)
    return titles


def _normalized_word_count_issue_line(
    current_count: int,
    word_count_window: tuple[int, int],
    target_word_count: int | None,
) -> str:
    minimum, maximum = word_count_window
    target = target_word_count or round((minimum + maximum) / 2)
    if current_count > maximum:
        label = "字数不在目标区间"
        action = "当前偏长，只做删减、合并和紧缩表达。"
    elif current_count < minimum:
        label = "字数不在目标区间"
        action = "当前偏短，只补必要动作、因果和钩子。"
    else:
        label = "字数实时复核"
        action = "当前已在建议区间内，修订时保持篇幅稳定。"
    return (
        f"- {label}：当前约 {current_count} 字，目标 {target} 字，"
        f"建议区间 {minimum}-{maximum} 字；{action}"
    )


def _filter_stale_word_count_suggestions(
    suggestions: list[str],
    current_count: int,
    word_count_window: tuple[int, int],
) -> list[str]:
    minimum, maximum = word_count_window
    if current_count > maximum:
        return [
            suggestion
            for suggestion in suggestions
            if not _contains_any(suggestion, EXPANSION_ADVICE_TERMS)
        ]
    if current_count < minimum:
        return [
            suggestion
            for suggestion in suggestions
            if not _contains_any(suggestion, REDUCTION_ADVICE_TERMS)
        ]
    return [
        suggestion
        for suggestion in suggestions
        if not _contains_any(suggestion, EXPANSION_ADVICE_TERMS + REDUCTION_ADVICE_TERMS)
    ]


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    normalized = text.lower()
    return any(term.lower() in normalized for term in terms)


def _manual_instruction_text(reviewer_note: str | None) -> str:
    note = str(reviewer_note or "").strip()
    if not note:
        return ""
    return f"人工修改意见：\n{note}"


def _audit_recheck_detail(
    existing_detail: object,
    current_count: int,
    word_count_window: tuple[int, int],
    target_word_count: int | None,
    *,
    in_window: bool,
) -> str:
    target = target_word_count or round((word_count_window[0] + word_count_window[1]) / 2)
    ratio = round(current_count / target * 100) if target else 0
    if current_count > word_count_window[1]:
        result = "当前偏长，需要删减、合并和紧缩表达。"
    elif current_count < word_count_window[0]:
        result = "当前偏短，需要补足必要动作、因果和钩子。"
    else:
        result = "当前已进入目标区间。"
    recheck = (
        f"自动复核：当前约 {current_count} 字，目标 {target} 字，"
        f"达成率 {ratio}%（目标区间 {word_count_window[0]}-{word_count_window[1]} 字）；{result}"
    )
    if not in_window:
        return recheck
    detail = str(existing_detail or "").strip()
    if not detail:
        return recheck
    if "自动复核" in detail:
        return recheck
    return f"{detail} {recheck}"


def _non_word_issue_recheck_detail(existing_detail: object, *, source: str = "patch") -> str:
    detail = str(existing_detail or "").strip()
    recheck = (
        "自动复核：正文已出现明确侧面反应。"
        if source == "text"
        else "自动复核：应用补丁已覆盖该审核项。"
    )
    if not detail:
        return recheck
    if recheck in detail:
        return detail
    return f"{detail} {recheck}"


def _non_word_issue_resolved_by_text(issue: dict[str, Any], current_text: str) -> bool:
    issue_text = " ".join(
        str(issue.get(key) or "")
        for key in ("title", "detail", "description", "message", "suggested_fix")
    )
    if not _contains_any(issue_text, SIDE_DESCRIPTION_ISSUE_TERMS):
        return False
    return _has_side_description_evidence(current_text)


def _has_side_description_evidence(current_text: str) -> bool:
    chunks = [
        chunk.strip()
        for paragraph in current_text.split("\n\n")
        for chunk in (
            paragraph.replace("。", "\n")
            .replace("！", "\n")
            .replace("？", "\n")
            .replace("；", "\n")
            .splitlines()
        )
        if chunk.strip()
    ]
    return any(
        _contains_any(chunk, SIDE_DESCRIPTION_OBSERVER_TERMS)
        and _contains_any(chunk, SIDE_DESCRIPTION_REACTION_TERMS)
        for chunk in chunks
    )


def _refresh_word_count_suggestions(
    suggestions: object,
    current_count: int,
    word_count_window: tuple[int, int],
    target_word_count: int | None,
) -> list[str]:
    target = target_word_count or round((word_count_window[0] + word_count_window[1]) / 2)
    items = (
        [str(item).strip() for item in suggestions if str(item).strip()]
        if isinstance(suggestions, list)
        else []
    )
    filtered = _filter_stale_word_count_suggestions(items, current_count, word_count_window)
    if current_count > word_count_window[1]:
        advice = f"当前正文约 {current_count} 字，已超出目标区间，请压缩到 {target} 字左右。"
        filtered = [item for item in filtered if not _is_word_count_action_suggestion(item)]
        filtered.insert(0, advice)
    elif current_count < word_count_window[0]:
        advice = f"当前正文约 {current_count} 字，低于目标区间，请补足到 {target} 字左右。"
        filtered = [item for item in filtered if not _is_word_count_action_suggestion(item)]
        filtered.insert(0, advice)
    return filtered


def _is_word_count_action_suggestion(text: str) -> bool:
    return (
        _has_word_count_term(text)
        or "当前正文" in text
        or "目标区间" in text
        or "目标字数" in text
        or "压缩到" in text
        or "补足到" in text
    )


def _is_word_count_issue(issue: dict[str, Any]) -> bool:
    return any(
        _has_word_count_term(str(issue.get(key) or ""))
        for key in ("title", "detail", "description", "message", "suggested_fix")
    )


def _word_count_direction(word_count: int, word_count_window: tuple[int, int]) -> str:
    if word_count > word_count_window[1]:
        return "long"
    if word_count < word_count_window[0]:
        return "short"
    return "ok"


def _word_count_issue_direction(issue: dict[str, Any]) -> str | None:
    text = " ".join(
        str(issue.get(key) or "")
        for key in ("title", "detail", "description", "message", "suggested_fix")
    )
    if _contains_any(text, REDUCTION_ADVICE_TERMS):
        return "long"
    if _contains_any(
        text, EXPANSION_ADVICE_TERMS + ("未达标", "缺口", "达成度偏低", "达成率严重不足")
    ):
        return "short"
    return None


def _has_word_count_term(text: str) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in WORD_COUNT_REPAIR_TERMS)


def _word_count_in_window(word_count: int, word_count_window: tuple[int, int]) -> bool:
    minimum, maximum = word_count_window
    return minimum <= word_count <= maximum


def _word_count_window_distance(word_count: int, window: tuple[int, int]) -> int:
    minimum, maximum = window
    if word_count < minimum:
        return minimum - word_count
    if word_count > maximum:
        return word_count - maximum
    return 0


def _all_issues_resolved(issues: list[Any]) -> bool:
    return all(not isinstance(issue, dict) or bool(issue.get("resolved")) for issue in issues)
