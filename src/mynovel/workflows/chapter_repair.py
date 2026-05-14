from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any, Protocol

from mynovel.domain.models import Chapter
from mynovel.word_targets import parse_word_count

WORD_COUNT_REPAIR_TERMS = ("字数", "篇幅", "达成率", "word count")
EXPANSION_ADVICE_TERMS = ("扩写", "扩充", "增加", "补充", "加入更多", "更多", "拉长", "拉升", "远低于", "低于", "不足", "偏短")
REDUCTION_ADVICE_TERMS = ("删减", "压缩", "合并", "缩短", "超出", "过长", "偏长")
WORD_COUNT_MIN_RATIO = 0.9
WORD_COUNT_MAX_RATIO = 1.15


class ChapterModelClient(Protocol):
    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        pass


TextStageCompleter = Callable[[ChapterModelClient, str, list[dict[str, str]]], str]
TextReviser = Callable[[str, dict[str, Any]], str]


def repair_text_with_model(
    chapter: Chapter,
    model_client: ChapterModelClient,
    reviewer_note: str | None,
    complete_text_stage: TextStageCompleter,
) -> str:
    word_count_window = _repair_word_count_window(chapter, reviewer_note)
    return complete_text_stage(
        model_client,
        "revise",
        _build_repair_messages(
            chapter,
            reviewer_note,
            word_count_window=word_count_window,
        ),
    )


def repair_text_locally(chapter: Chapter, revise_text: TextReviser) -> str:
    source_text = chapter.revised_text or chapter.draft_text
    repaired = revise_text(source_text, chapter.audit_report or {})
    if repaired != source_text:
        return repaired
    return f"{source_text}\n\n修复补充：已按审核意见补强人物动机、因果链和章节钩子。"


def recheck_repair_audit(chapter: Chapter) -> None:
    audit_report = deepcopy(chapter.audit_report or {})
    issues = audit_report.get("issues", [])
    if not isinstance(issues, list):
        return

    word_count_window = _word_count_window_from_plan(chapter)
    if word_count_window is None:
        return

    changed = False
    current_count = len(chapter.revised_text or chapter.draft_text or "")
    in_window = _word_count_in_window(current_count, word_count_window)
    target = parse_word_count(chapter.plan.get("word_budget"))
    for issue in issues:
        if not isinstance(issue, dict) or issue.get("resolved"):
            continue
        if not _is_word_count_issue(issue):
            continue
        if not in_window:
            continue
        issue["resolved"] = True
        issue["detail"] = _audit_recheck_detail(
            issue.get("detail"),
            current_count,
            word_count_window,
            target,
        )
        changed = True

    if changed and _all_issues_resolved(issues) and str(audit_report.get("risk_level", "")).lower() != "high":
        audit_report["risk_level"] = "low"
    if changed:
        chapter.audit_report = audit_report


def _repair_word_count_window(
    chapter: Chapter,
    reviewer_note: str | None,
) -> tuple[int, int] | None:
    if not _needs_word_count_repair(chapter, reviewer_note):
        return None
    return _word_count_window_from_plan(chapter)


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
        {"role": "user", "content": "\n".join(part for part in instructions if part) + "\n\n" + body},
    ]


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
        f"{target_text}建议区间：{minimum}-{maximum} 字\n"
        "不要用提纲、摘要、重复段落或冗余扩写凑字。"
    )
    if current_count > maximum:
        return f"{base}\n当前正文已经超出目标，请以删减和合并为主，不要新增支线、回忆或环境铺陈。"
    if current_count < minimum:
        return f"{base}\n当前正文低于目标，请只补必要的动作、因果和结尾钩子，不要重复已有信息。"
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
    trusted_state = context.get("trusted_state") if isinstance(context.get("trusted_state"), dict) else {}
    book = trusted_state.get("book") if isinstance(trusted_state.get("book"), dict) else {}
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
        issue for issue in audit_report.get("issues", []) if isinstance(issue, dict) and not issue.get("resolved")
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
        suggestions = _filter_stale_word_count_suggestions(suggestions, len(current_text), word_count_window)
    if suggestions:
        lines.append("AI 建议：")
        lines.extend(f"- {suggestion}" for suggestion in suggestions)
    return "\n".join(lines)


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
        return [suggestion for suggestion in suggestions if not _contains_any(suggestion, EXPANSION_ADVICE_TERMS)]
    if current_count < minimum:
        return [suggestion for suggestion in suggestions if not _contains_any(suggestion, REDUCTION_ADVICE_TERMS)]
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
) -> str:
    target = target_word_count or round((word_count_window[0] + word_count_window[1]) / 2)
    ratio = round(current_count / target * 100) if target else 0
    recheck = (
        f"自动复核：当前 {current_count} 字，目标 {target} 字，"
        f"达成率 {ratio}%（目标区间 {word_count_window[0]}-{word_count_window[1]} 字）。"
    )
    detail = str(existing_detail or "").strip()
    if not detail:
        return recheck
    if "自动复核" in detail:
        return recheck
    return f"{detail} {recheck}"


def _is_word_count_issue(issue: dict[str, Any]) -> bool:
    return any(
        _has_word_count_term(str(issue.get(key) or ""))
        for key in ("title", "detail", "description", "message", "suggested_fix")
    )


def _has_word_count_term(text: str) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in WORD_COUNT_REPAIR_TERMS)


def _word_count_in_window(word_count: int, word_count_window: tuple[int, int]) -> bool:
    minimum, maximum = word_count_window
    return minimum <= word_count <= maximum


def _all_issues_resolved(issues: list[Any]) -> bool:
    return all(not isinstance(issue, dict) or bool(issue.get("resolved")) for issue in issues)
