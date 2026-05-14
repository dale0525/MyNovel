from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CANDIDATE_TITLE_KEYS = ("title", "selected_title", "title_option", "book_title")


@dataclass(frozen=True)
class BlueprintCandidate:
    index: int
    title: str
    content: dict[str, Any]


def blueprint_candidates_from_content(content: dict[str, Any]) -> list[BlueprintCandidate]:
    titles = _title_options_from_content(content)
    if not titles:
        return []
    raw_candidates = content.get("candidates")
    candidates = raw_candidates if isinstance(raw_candidates, list) else []
    matched_candidates = [_candidate_for_title(candidates, title, index) for index, title in enumerate(titles)]
    return [
        BlueprintCandidate(index=index, title=title, content=_candidate_content(content, title, raw))
        for index, (title, raw) in enumerate(zip(titles, matched_candidates, strict=True))
    ]


def content_for_selected_title(content: dict[str, Any], selected_title: str) -> dict[str, Any]:
    title = selected_title.strip()
    for candidate in blueprint_candidates_from_content(content):
        if candidate.title == title:
            return candidate.content
    return content


def _candidate_for_title(candidates: list[Any], title: str, index: int) -> dict[str, Any]:
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if _candidate_title(candidate) == title:
            return candidate
    if index < len(candidates) and isinstance(candidates[index], dict):
        return candidates[index]
    return {}


def _candidate_content(
    base_content: dict[str, Any],
    title: str,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(base_content)
    merged.update({key: value for key, value in candidate.items() if key not in CANDIDATE_TITLE_KEYS})
    merged["title_options"] = [title]
    merged["selected_title"] = title
    return merged


def _candidate_title(candidate: dict[str, Any]) -> str:
    for key in CANDIDATE_TITLE_KEYS:
        title = str(candidate.get(key) or "").strip()
        if title:
            return title
    return ""


def _title_options_from_content(content: dict[str, Any]) -> list[str]:
    title_options = content.get("title_options")
    if not isinstance(title_options, list):
        return []
    return [title for item in title_options if (title := str(item).strip())]
