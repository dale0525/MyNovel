from __future__ import annotations

import json
import re
from typing import Any


class ChapterJsonStageFormatError(ValueError):
    pass


def parse_json_stage_response(raw_text: str, stage: str) -> dict[str, Any]:
    try:
        return _parse_json_object(raw_text)
    except (json.JSONDecodeError, ValueError) as error:
        if stage == "audit":
            audit_report = _parse_markdown_audit_report(raw_text)
            if audit_report is not None:
                return audit_report
        raise ChapterJsonStageFormatError(str(error)) from error


def normalize_state_delta(chapter_number: int, state_delta: dict[str, Any]) -> dict[str, Any]:
    raw_chapter = state_delta.get("chapter")
    if raw_chapter == chapter_number:
        normalized_chapter = chapter_number
    elif isinstance(raw_chapter, dict) and raw_chapter.get("number") == chapter_number:
        normalized_chapter = chapter_number
    else:
        normalized_chapter = chapter_number

    changes = []
    for raw_change in state_delta.get("changes", []):
        if isinstance(raw_change, str):
            text = raw_change.strip()
            if text:
                changes.append(
                    {
                        "type": "状态变化",
                        "target": "待确认",
                        "change": text,
                        "risk": "low",
                    }
                )
            continue
        if not isinstance(raw_change, dict):
            continue
        change_type = str(raw_change.get("type") or raw_change.get("category") or "状态变化").strip()
        target = str(raw_change.get("target") or raw_change.get("subject") or raw_change.get("name") or "").strip()
        change = str(
            raw_change.get("change")
            or raw_change.get("content")
            or raw_change.get("description")
            or raw_change.get("detail")
            or raw_change.get("summary")
            or ""
        ).strip()
        if not target:
            inferred_target, inferred_change = _split_target_from_change(change)
            target = inferred_target
            change = inferred_change or change
        if not change:
            continue
        changes.append(
            {
                "type": change_type,
                "target": target or "待确认",
                "change": change,
                "risk": str(raw_change.get("risk") or "low").strip() or "low",
            }
        )
    if not changes:
        changes.append(
            {
                "type": "章节进展",
                "target": f"第 {chapter_number:02d} 章",
                "change": "本章已生成，未能自动提取明确状态变化，请人工确认是否写入可信设定。",
                "risk": "medium",
            }
        )
    return {"chapter": normalized_chapter, "changes": changes}


def fallback_audit_report(error: Exception) -> dict[str, Any]:
    return {
        "risk_level": "medium",
        "issues": [
            {
                "severity": "medium",
                "title": "AI 审计返回格式异常，请人工重点检查本章",
                "resolved": False,
                "detail": str(error),
            }
        ],
        "suggestions": ["人工检查正文、状态变化与章节结尾钩子后再批准。"],
    }


def _parse_json_object(raw_text: str) -> dict[str, Any]:
    text = _json_object_text(_strip_code_fence(raw_text.strip()))
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Chapter model response must be a JSON object.")
    return data


def _json_object_text(text: str) -> str:
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


def _split_target_from_change(text: str) -> tuple[str, str]:
    for separator in ("：", ":"):
        if separator not in text:
            continue
        target, change = text.split(separator, 1)
        target = target.strip()
        change = change.strip()
        if 1 <= len(target) <= 24 and change:
            return target, change
    return "", text


def _parse_markdown_audit_report(raw_text: str) -> dict[str, Any] | None:
    risk_level = _parse_markdown_risk_level(raw_text)
    if risk_level is None:
        return None
    lines = [line.strip() for line in raw_text.splitlines()]
    return {
        "risk_level": risk_level,
        "issues": _parse_markdown_issues(lines),
        "suggestions": _parse_markdown_suggestions(lines),
    }


def _parse_markdown_risk_level(text: str) -> str | None:
    match = re.search(r"Risk\s*Level\s*:\s*(high|medium|low)", text, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    match = re.search(r"风险评估.*?\b(high|medium|low)\b", text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).lower()
    if "高风险" in text:
        return "high"
    if "中风险" in text:
        return "medium"
    if "低风险" in text:
        return "low"
    return None


def _parse_markdown_issues(lines: list[str]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for line in lines:
        if not line.startswith("|") or "---" in line:
            continue
        cells = [_clean_markdown_text(cell) for cell in line.strip("|").split("|")]
        if len(cells) < 3 or "严重程度" in cells[0] or "severity" in cells[0].lower():
            continue
        severity = _normalize_severity(cells[0])
        if severity is None:
            continue
        title = cells[1].strip()
        if not title:
            continue
        issue: dict[str, Any] = {
            "severity": severity,
            "title": title,
            "resolved": _parse_resolved(cells[2]),
        }
        if len(cells) >= 4 and cells[3]:
            issue["detail"] = cells[3]
        issues.append(issue)
    return issues


def _parse_markdown_suggestions(lines: list[str]) -> list[str]:
    suggestions: list[str] = []
    in_suggestions = False
    for line in lines:
        lower = line.lower()
        if "suggestions" in lower or "改进建议" in line:
            in_suggestions = True
            continue
        if not in_suggestions:
            continue
        if "审计结论" in line or "结论" in line:
            break
        match = re.match(r"\s*\d+[.)]\s+(.*)", line)
        if match:
            suggestion = _clean_markdown_text(match.group(1))
            if suggestion:
                suggestions.append(suggestion)
    return suggestions


def _normalize_severity(value: str) -> str | None:
    normalized = value.strip().lower()
    if normalized in {"high", "高"}:
        return "high"
    if normalized in {"medium", "mid", "中"}:
        return "medium"
    if normalized in {"low", "低"}:
        return "low"
    return None


def _parse_resolved(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"yes", "true", "resolved", "已解决", "是", "y"}


def _clean_markdown_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = cleaned.replace("**", "").replace("__", "").replace("`", "")
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()
