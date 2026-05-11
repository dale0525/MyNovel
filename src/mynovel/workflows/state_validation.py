from __future__ import annotations

from typing import Any

from mynovel.domain.models import Chapter


class StateDeltaValidationError(ValueError):
    pass


def validate_state_delta(chapter: Chapter) -> None:
    state_delta = chapter.state_delta
    if not isinstance(state_delta, dict):
        raise StateDeltaValidationError("StateDelta must be a JSON object.")
    if state_delta.get("chapter") != chapter.number:
        raise StateDeltaValidationError("StateDelta chapter must match the chapter number.")
    changes = state_delta.get("changes")
    if not isinstance(changes, list) or not changes:
        raise StateDeltaValidationError("StateDelta changes must be a non-empty list.")
    for index, change in enumerate(changes, start=1):
        _validate_change(index, change)


def _validate_change(index: int, change: Any) -> None:
    if not isinstance(change, dict):
        raise StateDeltaValidationError(f"StateDelta change #{index} must be an object.")
    for field in ("type", "target", "change"):
        value = str(change.get(field, "")).strip()
        if not value:
            raise StateDeltaValidationError(f"StateDelta change #{index} missing {field}.")
