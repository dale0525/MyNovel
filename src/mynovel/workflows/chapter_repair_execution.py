from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from mynovel.domain.models import Chapter
from mynovel.workflows.chapter_repair import (
    ChapterModelClient,
    RepairRequest,
    build_repair_request,
    build_stable_repair_patch_request,
    build_word_count_patch_request,
    patch_addressed_issue_titles,
    word_count_patch_mode,
)
from mynovel.workflows.chapter_repair_patches import apply_word_count_patch_bounded


JsonStageCompleter = Callable[
    [ChapterModelClient, str, list[dict[str, str]], set[str]],
    tuple[dict[str, Any], str],
]


@dataclass(frozen=True)
class RepairModelResult:
    request: RepairRequest
    raw_response_text: str
    applied_response_text: str
    word_count_repair_mode: str | None
    patch_operations: list[dict[str, Any]] | None
    applied_patch_operations: list[dict[str, Any]] | None
    patch_application_strategy: str | None
    addressed_issue_titles: list[str]


def complete_repair_with_model(
    chapter: Chapter,
    reviewer_note: str | None,
    source_text: str,
    model_client: ChapterModelClient,
    complete_json_stage_with_raw: JsonStageCompleter,
) -> RepairModelResult:
    request = build_repair_request(chapter, reviewer_note)
    word_count_repair_mode = word_count_patch_mode(
        request.before_word_count,
        request.word_count_window,
    )
    if word_count_repair_mode is not None:
        return _complete_patch_repair(
            chapter,
            reviewer_note,
            source_text,
            model_client,
            complete_json_stage_with_raw,
            word_count_repair_mode,
        )
    return _complete_patch_repair(
        chapter,
        reviewer_note,
        source_text,
        model_client,
        complete_json_stage_with_raw,
        None,
    )


def _complete_patch_repair(
    chapter: Chapter,
    reviewer_note: str | None,
    source_text: str,
    model_client: ChapterModelClient,
    complete_json_stage_with_raw: JsonStageCompleter,
    word_count_repair_mode: str | None,
) -> RepairModelResult:
    request = (
        build_word_count_patch_request(chapter, reviewer_note)
        if word_count_repair_mode is not None
        else build_stable_repair_patch_request(chapter, reviewer_note)
    )
    stage = "word_count_patch" if word_count_repair_mode is not None else "repair_patch"
    patch_payload, raw_response_text = complete_json_stage_with_raw(
        model_client,
        stage,
        request.messages,
        {"operations"},
    )
    patch_operations = [
        operation
        for operation in patch_payload.get("operations", [])
        if isinstance(operation, dict)
    ]
    patch_application = apply_word_count_patch_bounded(
        source_text,
        patch_payload,
        request.word_count_window,
        request.target_word_count,
    )
    addressed_issue_titles = patch_addressed_issue_titles(
        patch_application.operations,
        request.unresolved_audit_issues,
    )
    return RepairModelResult(
        request=request,
        raw_response_text=raw_response_text,
        applied_response_text=patch_application.text,
        word_count_repair_mode=word_count_repair_mode,
        patch_operations=patch_operations,
        applied_patch_operations=patch_application.operations,
        patch_application_strategy=patch_application.strategy,
        addressed_issue_titles=addressed_issue_titles,
    )
