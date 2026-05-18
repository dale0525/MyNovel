from __future__ import annotations

from typing import Any

from mynovel.workflows.chapter_repair_terms import (
    SIDE_DESCRIPTION_ISSUE_TERMS,
    SIDE_DESCRIPTION_OBSERVER_TERMS,
    SIDE_DESCRIPTION_REACTION_TERMS,
    TRANSITION_BRIDGE_TERMS,
    TRANSITION_CAUSAL_TERMS,
    TRANSITION_JUMP_ISSUE_TERMS,
)


def non_word_issue_repair_hint(issue: dict[str, Any]) -> str:
    if _is_transition_jump_issue(issue):
        return (
            "需要补足场景之间的承接，补清人物为什么立刻转场、下一步动作如何发生，"
            "优先用动作、心理、因果或旁人反应做过渡，不要只扩写环境。"
        )
    return ""


def non_word_issue_recheck_detail(existing_detail: object, *, source: str = "patch") -> str:
    detail = str(existing_detail or "").strip()
    if source == "text":
        recheck = "自动复核：正文已出现明确侧面反应。"
    elif source == "transition":
        recheck = "自动复核：正文已补足过渡承接。"
    else:
        recheck = "自动复核：应用补丁已覆盖该审核项。"
    if not detail:
        return recheck
    if recheck in detail:
        return detail
    return f"{detail} {recheck}"


def non_word_issue_resolution_source(
    issue: dict[str, Any],
    current_text: str,
    previous_text: str | None = None,
) -> str | None:
    if _is_side_description_issue(issue) and _has_side_description_evidence(current_text):
        return "text"
    if _is_transition_jump_issue(issue) and _has_transition_bridge_evidence(
        current_text,
        previous_text,
    ):
        return "transition"
    return None


def _is_side_description_issue(issue: dict[str, Any]) -> bool:
    return _contains_any(_issue_text(issue), SIDE_DESCRIPTION_ISSUE_TERMS)


def _is_transition_jump_issue(issue: dict[str, Any]) -> bool:
    return _contains_any(_issue_text(issue), TRANSITION_JUMP_ISSUE_TERMS)


def _issue_text(issue: dict[str, Any]) -> str:
    return " ".join(
        str(issue.get(key) or "")
        for key in ("title", "detail", "description", "message", "suggested_fix")
    )


def _has_side_description_evidence(current_text: str) -> bool:
    return any(
        _contains_any(chunk, SIDE_DESCRIPTION_OBSERVER_TERMS)
        and _contains_any(chunk, SIDE_DESCRIPTION_REACTION_TERMS)
        for chunk in _text_chunks(current_text)
    )


def _has_transition_bridge_evidence(current_text: str, previous_text: str | None) -> bool:
    if previous_text is None or current_text.strip() == previous_text.strip():
        return False
    current_chunks = _text_chunks(current_text)
    previous_chunks = _text_chunks(previous_text)
    current_bridge_score = _chunk_score(current_chunks, TRANSITION_BRIDGE_TERMS)
    current_causal_score = _chunk_score(current_chunks, TRANSITION_CAUSAL_TERMS)
    previous_bridge_score = _chunk_score(previous_chunks, TRANSITION_BRIDGE_TERMS)
    previous_causal_score = _chunk_score(previous_chunks, TRANSITION_CAUSAL_TERMS)
    bridge_gain = current_bridge_score - previous_bridge_score
    causal_gain = current_causal_score - previous_causal_score
    expanded = len(current_text) >= len(previous_text) + 40
    paragraph_added = len(_paragraphs(current_text)) > len(_paragraphs(previous_text))
    if current_bridge_score < 2 or current_causal_score < 1:
        return False
    return expanded or paragraph_added or bridge_gain + causal_gain >= 2


def _chunk_score(chunks: list[str], terms: tuple[str, ...]) -> int:
    return sum(1 for chunk in chunks if _contains_any(chunk, terms))


def _text_chunks(text: str) -> list[str]:
    return [
        chunk.strip()
        for paragraph in _paragraphs(text)
        for chunk in (
            paragraph.replace("。", "\n")
            .replace("！", "\n")
            .replace("？", "\n")
            .replace("；", "\n")
            .splitlines()
        )
        if chunk.strip()
    ]


def _paragraphs(text: str) -> list[str]:
    return [paragraph for paragraph in text.split("\n\n") if paragraph.strip()]


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    normalized = text.lower()
    return any(term.lower() in normalized for term in terms)
