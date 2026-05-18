from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from mynovel.domain.models import Chapter, utc_now


def accepted_chapter_content(content: dict[str, Any], chapter: Chapter) -> dict[str, Any]:
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


def trusted_state_index_text(chapter: Chapter, trusted_state: dict[str, Any]) -> str:
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
