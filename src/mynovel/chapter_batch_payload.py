from __future__ import annotations

from typing import Any


def parse_chapter_batch_ids(value: Any) -> list[int]:
    if not isinstance(value, list):
        raise ValueError("chapterIds must contain at least one chapter id.")
    return validate_chapter_batch_ids(value)


def validate_chapter_batch_ids(chapter_ids: list[Any]) -> list[int]:
    selected: list[int] = []
    for chapter_id in chapter_ids:
        if not isinstance(chapter_id, int) or isinstance(chapter_id, bool) or chapter_id < 1:
            raise ValueError("chapterIds must contain positive integer chapter ids.")
        if chapter_id not in selected:
            selected.append(chapter_id)
    if not selected:
        raise ValueError("chapterIds must contain at least one chapter id.")
    return selected
