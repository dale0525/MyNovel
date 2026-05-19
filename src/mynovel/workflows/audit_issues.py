from __future__ import annotations

from typing import Any


def audit_issue_resolved(issue: dict[str, Any]) -> bool:
    value = issue.get("resolved")
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value == 1
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {
            "true",
            "1",
            "yes",
            "y",
            "resolved",
            "fixed",
            "已解决",
            "已修正",
            "已满足",
        }
    return False
