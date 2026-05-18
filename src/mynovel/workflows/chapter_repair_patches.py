from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from mynovel.word_targets import count_chapter_words


@dataclass(frozen=True)
class WordCountPatchApplication:
    text: str
    operations: list[dict[str, Any]]
    strategy: str


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
            if op in {"replace", "compress"}:
                merged_end = _patch_merged_end(operation, paragraph_id, paragraph_count)
                deleted.update(range(paragraph_id + 1, merged_end + 1))
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
    if word_count_window is None or _word_count_in_window(
        count_chapter_words(patched),
        word_count_window,
    ):
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


def _patch_merged_end(operation: dict[str, Any], paragraph_id: int, paragraph_count: int) -> int:
    explicit_end = operation.get("end_paragraph_id")
    if explicit_end is not None:
        return max(paragraph_id, _patch_paragraph_id(explicit_end, paragraph_count))
    reason = str(operation.get("reason") or "")
    pattern = r"(?:合并|整合)(?:段落)?\s*(\d+)\s*(?:[-－—~～到至]|与)\s*(\d+)\s*段?"
    for match in re.finditer(pattern, reason):
        start, end = int(match.group(1)), int(match.group(2))
        if start == paragraph_id and end >= start:
            return min(end, paragraph_count)
    return paragraph_id


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
        word_count = count_chapter_words(patched)
        if not _word_count_in_window(word_count, word_count_window):
            continue
        distance = abs(word_count - target)
        if best is None or best_distance is None or distance < best_distance:
            best = WordCountPatchApplication(patched, prefix, "bounded_prefix")
            best_distance = distance
    return best


def _word_count_in_window(word_count: int, word_count_window: tuple[int, int]) -> bool:
    minimum, maximum = word_count_window
    return minimum <= word_count <= maximum
