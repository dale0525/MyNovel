from __future__ import annotations

import json
import math
from typing import Any, Protocol

from sqlmodel import Session

from mynovel.domain.models import Book, Canon, Chapter, ChapterStatus, RunTrace, VolumePlan, utc_now
from mynovel.domain.repositories import (
    get_book,
    get_latest_canon,
    list_chapters_for_book,
    list_volume_plans_for_book,
)
from mynovel.word_targets import (
    CHAPTER_WORD_COUNT_KEY,
    DEFAULT_CHAPTER_WORD_COUNT,
    book_target_word_count,
    parse_word_count,
)


class VolumePlanningModelClient(Protocol):
    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        pass


REVISION_SCOPES = {"all_volumes", "all_chapters", "volume_summary", "volume_chapters"}
VOLUME_REVISION_SCOPES = {"volume_summary", "volume_chapters"}
GENERATED_CHAPTER_NUMBER_KEY = "_generated_chapter_number"


def generate_volume_outline(
    session: Session,
    book_id: int,
    model_client: VolumePlanningModelClient | None = None,
    model_name: str | None = None,
) -> Book:
    book = get_book(session, book_id)
    if book is None:
        raise ValueError("Book does not exist.")
    canon = get_latest_canon(session, book_id)
    if canon is None:
        raise ValueError("Trusted state is required before volume planning.")

    chapters = list_chapters_for_book(session, book_id)
    if model_client is None:
        outline = _simulated_volume_outline(book, canon, chapters)
    else:
        raw_response = model_client.complete(
            "volume_outline",
            build_volume_outline_messages(book, canon, chapters),
            "json",
        )
        outline = parse_volume_outline_json(raw_response)

    outline = _renumber_generated_outline_chapters(outline, chapters)
    outline = _ensure_target_chapter_coverage(outline, book, chapters)
    _apply_volume_outline(
        session,
        book,
        outline,
        model_name,
        preserve_existing_chapters=True,
        preserve_existing_volume_plans=True,
    )
    session.commit()
    session.refresh(book)
    return book


def revise_volume_outline(
    session: Session,
    book_id: int,
    body: dict[str, Any],
    model_client: VolumePlanningModelClient | None = None,
    model_name: str | None = None,
) -> Book:
    request = _volume_revision_request(body)
    book = get_book(session, book_id)
    if book is None:
        raise ValueError("Book does not exist.")
    canon = get_latest_canon(session, book_id)
    if canon is None:
        raise ValueError("Trusted state is required before volume planning.")

    chapters = list_chapters_for_book(session, book_id)
    volume_plans = list_volume_plans_for_book(session, book_id)
    if model_client is None:
        outline = _simulated_volume_revision(book, canon, chapters, volume_plans, request)
    else:
        raw_response = model_client.complete(
            "volume_outline_revision",
            build_volume_revision_messages(book, canon, chapters, volume_plans, request),
            "json",
        )
        outline = parse_volume_outline_json(raw_response)

    if request["scope"] in {"all_volumes", "all_chapters", "volume_chapters"}:
        outline = _renumber_generated_outline_chapters(outline, chapters)
    if request["scope"] in {"all_volumes", "all_chapters"} and _outline_has_chapters(outline):
        outline = _ensure_target_chapter_coverage(outline, book, chapters)
    scoped_outline = _scoped_revision_outline(outline, request, volume_plans)
    _apply_volume_outline(session, book, scoped_outline, model_name)
    session.commit()
    session.refresh(book)
    return book


def build_volume_outline_messages(
    book: Book,
    canon: Canon,
    chapters: list[Chapter],
) -> list[dict[str, str]]:
    system_prompt = (
        "你是长篇小说总纲规划师。请基于项目基本信息和可信设定，生成卷纲列表与每卷章节规划。"
        "必须只输出 JSON，不要 Markdown，不要解释。"
    )
    target = _volume_outline_target(book, chapters)
    schema_prompt = (
        "JSON 必须包含 volumes 数组。每个 volume 包含 volume_number, title, core_conflict, "
        "pacing_curve, payoff_distribution, key_turns, commitments, chapters。"
        "chapters 必须是单章列表，每项包含 number, title, goal，可包含 ending_hook, must_write。"
        f"必须按目标字数规划到第 {target['target_chapter_count']} 章，章节编号必须覆盖 "
        f"{target['required_chapter_range']}，不要因为卷数较少而减少章节数。"
        "只规划后续章节，不改写已接受、运行中或待审核章节。"
    )
    payload = {
        "book": {
            "title": book.title,
            "genre": book.genre,
            "audience": book.audience,
            "premise": book.premise,
            "word_targets": book.constraints or {},
        },
        "planning_targets": target,
        "trusted_state": canon.content,
        "existing_chapters": [
            {
                "number": chapter.number,
                "title": chapter.title,
                "status": chapter.status.value,
                "goal": (chapter.plan or {}).get("goal"),
            }
            for chapter in chapters
        ],
    }
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"{schema_prompt}\n{json.dumps(payload, ensure_ascii=False)}",
        },
    ]


def build_volume_revision_messages(
    book: Book,
    canon: Canon,
    chapters: list[Chapter],
    volume_plans: list[VolumePlan],
    request: dict[str, Any],
) -> list[dict[str, str]]:
    system_prompt = (
        "你是长篇小说卷纲修订师。请根据人工修改意见局部修订卷纲和章节规划。"
        "必须只输出 JSON，不要 Markdown，不要解释。"
    )
    schema_prompt = (
        "JSON 必须包含 volumes 数组，结构与卷纲生成一致。"
        "scope=all_volumes 时改卷纲列表、单卷概括和 planned 章节列表；"
        "scope=all_chapters 时只改 planned 章节列表，不改卷纲概括；"
        "scope=volume_summary 时只改目标卷概括，不改章节；"
        "scope=volume_chapters 时只改目标卷 planned 章节列表，不改卷纲概括。"
        "已生产章节是不可推翻的事实边界；locked=true 的章节摘要和正文片段必须作为既成事实，"
        "卷纲概括只能解释、承接和重排这些事实，不能把它们改写成相反事件。"
        "如果人工修改意见与 locked=true 章节冲突，以已生产章节为准。"
        "已接受、生成中、待审核和需修订章节都必须保持原编号、标题和目标。"
    )
    payload = {
        "revision": request,
        "book": {
            "title": book.title,
            "genre": book.genre,
            "audience": book.audience,
            "premise": book.premise,
            "word_targets": book.constraints or {},
        },
        "trusted_state": canon.content,
        "volume_plans": [_volume_plan_context(plan) for plan in volume_plans],
        "chapters": [_chapter_context(chapter) for chapter in chapters],
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{schema_prompt}\n{json.dumps(payload, ensure_ascii=False)}"},
    ]


def parse_volume_outline_json(raw_text: str) -> dict[str, Any]:
    text = _strip_code_fence(raw_text.strip())
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("volumes"), list):
        raise ValueError("Volume outline response must contain volumes.")

    volumes = [_normalize_volume(item, index + 1) for index, item in enumerate(data["volumes"])]
    volumes = [volume for volume in volumes if volume is not None]
    if not volumes:
        raise ValueError("Volume outline response must include at least one volume.")
    return {"volumes": volumes}


def _volume_revision_request(body: dict[str, Any]) -> dict[str, Any]:
    scope = str(body.get("scope") or "").strip()
    if scope not in REVISION_SCOPES:
        raise ValueError("Volume revision scope is invalid.")
    revision_notes = str(body.get("revisionNotes") or body.get("revision_notes") or "").strip()
    if not revision_notes:
        raise ValueError("Volume revision notes are required.")
    request: dict[str, Any] = {"scope": scope, "revision_notes": revision_notes}
    volume_number = _positive_int(body.get("volumeNumber", body.get("volume_number")), 0)
    if scope in VOLUME_REVISION_SCOPES:
        if volume_number <= 0:
            raise ValueError("Volume number is required for this revision scope.")
        request["volume_number"] = volume_number
    elif volume_number > 0:
        request["volume_number"] = volume_number
    return request


def _scoped_revision_outline(
    outline: dict[str, Any],
    request: dict[str, Any],
    existing_plans: list[VolumePlan],
) -> dict[str, Any]:
    scope = request["scope"]
    target_volume = request.get("volume_number")
    existing_by_number = {plan.volume_number: plan for plan in existing_plans}
    volumes: list[dict[str, Any]] = []
    for volume in outline["volumes"]:
        volume_number = volume["volume_number"]
        if target_volume is not None and volume_number != target_volume:
            continue
        existing_plan = existing_by_number.get(volume_number)
        if scope == "volume_summary":
            volume["chapters"] = []
        elif scope in {"all_chapters", "volume_chapters"}:
            if existing_plan is None:
                continue
            volume = {
                **volume,
                **_volume_plan_fields(existing_plan),
                "chapters": volume["chapters"],
            }
        volumes.append(volume)
    if not volumes:
        raise ValueError("Volume revision response did not include the requested volume.")
    return {"volumes": volumes}


def _apply_volume_outline(
    session: Session,
    book: Book,
    outline: dict[str, Any],
    model_name: str | None,
    *,
    preserve_existing_chapters: bool = False,
    preserve_existing_volume_plans: bool = False,
) -> None:
    if book.id is None:
        raise ValueError("Book must be persisted before volume planning.")

    existing_plans = {
        plan.volume_number: plan for plan in list_volume_plans_for_book(session, book.id)
    }
    existing_chapters = {
        chapter.number: chapter for chapter in list_chapters_for_book(session, book.id)
    }
    generated_chapter_count = 0

    for volume in outline["volumes"]:
        volume_number = volume["volume_number"]
        plan = existing_plans.get(volume_number)
        if plan is None:
            plan = VolumePlan(book_id=book.id, volume_number=volume_number, title=volume["title"])
        if plan.volume_number not in existing_plans or not preserve_existing_volume_plans:
            plan.title = volume["title"]
            plan.core_conflict = volume["core_conflict"]
            plan.pacing_curve = volume["pacing_curve"]
            plan.payoff_distribution = volume["payoff_distribution"]
            plan.key_turns = volume["key_turns"]
            plan.commitments = volume["commitments"]
            plan.updated_at = utc_now()
            session.add(plan)

        for chapter_plan in volume["chapters"]:
            number = chapter_plan["number"]
            chapter = existing_chapters.get(number)
            if chapter is not None and (
                preserve_existing_chapters or chapter.status != ChapterStatus.PLANNED
            ):
                continue
            if chapter is None:
                chapter = Chapter(book_id=book.id, number=number, title=chapter_plan["title"])
                existing_chapters[number] = chapter
            chapter.title = chapter_plan["title"]
            chapter.plan = _chapter_plan_payload(volume_number, chapter_plan, book)
            chapter.updated_at = utc_now()
            session.add(chapter)
            generated_chapter_count += 1

    session.add(
        RunTrace(
            book_id=book.id,
            stage="volume_outline",
            prompt_id="volume_outline",
            prompt_version="0.1.0",
            model=model_name,
            cost={"estimated": 0},
            metadata_={
                "volume_count": len(outline["volumes"]),
                "chapter_count": generated_chapter_count,
            },
        )
    )


def _volume_outline_target(book: Book, chapters: list[Chapter]) -> dict[str, Any]:
    chapter_word_count = (
        parse_word_count((book.constraints or {}).get(CHAPTER_WORD_COUNT_KEY))
        or DEFAULT_CHAPTER_WORD_COUNT
    )
    target_word_count = book_target_word_count(book)
    target_chapter_count = max(1, math.ceil(target_word_count / chapter_word_count))
    max_existing_number = max((chapter.number for chapter in chapters), default=0)
    target_chapter_count = max(target_chapter_count, max_existing_number)
    return {
        "target_word_count": target_word_count,
        "chapter_word_count": chapter_word_count,
        "target_chapter_count": target_chapter_count,
        "required_chapter_range": f"1-{target_chapter_count}",
        "existing_chapter_count": len(chapters),
    }


def _ensure_target_chapter_coverage(
    outline: dict[str, Any],
    book: Book,
    existing_chapters: list[Chapter],
) -> dict[str, Any]:
    target = _volume_outline_target(book, existing_chapters)
    target_chapter_count = target["target_chapter_count"]
    volumes = outline["volumes"]
    if not volumes:
        return outline
    planned_numbers = {
        chapter["number"]
        for volume in volumes
        for chapter in volume["chapters"]
        if isinstance(chapter.get("number"), int)
    }
    missing_numbers = [
        number for number in range(1, target_chapter_count + 1) if number not in planned_numbers
    ]
    if not missing_numbers:
        return outline

    existing_by_number = {chapter.number: chapter for chapter in existing_chapters}
    fallback_volume = volumes[-1]
    fallback_conflict = fallback_volume.get("core_conflict") or book.premise or "推进本卷主线。"
    for number in missing_numbers:
        existing = existing_by_number.get(number)
        fallback_volume["chapters"].append(
            {
                "number": number,
                "title": existing.title if existing is not None else f"第 {number:02d} 章",
                "goal": _chapter_goal(existing)
                if existing is not None
                else f"{fallback_conflict} 衔接第 {number} 章。",
                "ending_hook": "留下一个明确的新问题，推动读者进入下一章。",
                "must_write": _list_values(fallback_volume.get("commitments")),
                "word_budget": target["chapter_word_count"],
            }
        )
    fallback_volume["chapters"].sort(key=lambda chapter: chapter["number"])
    return outline


def _renumber_generated_outline_chapters(
    outline: dict[str, Any],
    existing_chapters: list[Chapter],
) -> dict[str, Any]:
    volumes = sorted(outline["volumes"], key=lambda item: item["volume_number"])
    chapter_plans = [chapter for volume in volumes for chapter in volume["chapters"]]
    if not chapter_plans:
        outline["volumes"] = volumes
        return outline

    has_generated_number = False
    for chapter in chapter_plans:
        has_generated_number = (
            bool(chapter.pop(GENERATED_CHAPTER_NUMBER_KEY, False)) or has_generated_number
        )
    numbers = [
        chapter["number"] for chapter in chapter_plans if isinstance(chapter.get("number"), int)
    ]
    has_duplicate_number = len(numbers) != len(set(numbers))
    has_backward_number = any(
        current <= previous for previous, current in zip(numbers, numbers[1:])
    )
    if not has_generated_number and not has_duplicate_number and not has_backward_number:
        outline["volumes"] = volumes
        return outline

    next_number = _first_generated_chapter_number(volumes, existing_chapters)
    for volume in volumes:
        for chapter in volume["chapters"]:
            chapter["number"] = next_number
            next_number += 1
    outline["volumes"] = volumes
    return outline


def _first_generated_chapter_number(
    volumes: list[dict[str, Any]],
    existing_chapters: list[Chapter],
) -> int:
    if not volumes or volumes[0]["volume_number"] <= 1:
        return 1
    first_volume_number = volumes[0]["volume_number"]
    previous_chapter_numbers = [
        chapter.number
        for chapter in existing_chapters
        if _positive_int((chapter.plan or {}).get("volume_number"), 0) < first_volume_number
    ]
    if previous_chapter_numbers:
        return max(previous_chapter_numbers) + 1
    return max((chapter.number for chapter in existing_chapters), default=0) + 1


def _outline_has_chapters(outline: dict[str, Any]) -> bool:
    return any(volume["chapters"] for volume in outline["volumes"])


def _volume_plan_context(plan: VolumePlan) -> dict[str, Any]:
    return {
        "volume_number": plan.volume_number,
        "title": plan.title,
        "core_conflict": plan.core_conflict,
        "pacing_curve": plan.pacing_curve,
        "payoff_distribution": plan.payoff_distribution,
        "key_turns": plan.key_turns,
        "commitments": plan.commitments,
    }


def _volume_plan_fields(plan: VolumePlan) -> dict[str, Any]:
    return {
        "title": plan.title,
        "core_conflict": plan.core_conflict,
        "pacing_curve": plan.pacing_curve,
        "payoff_distribution": plan.payoff_distribution,
        "key_turns": plan.key_turns,
        "commitments": plan.commitments,
    }


def _chapter_context(chapter: Chapter) -> dict[str, Any]:
    locked = chapter.status != ChapterStatus.PLANNED
    context = {
        "number": chapter.number,
        "title": chapter.title,
        "status": chapter.status.value,
        "volume_number": _positive_int((chapter.plan or {}).get("volume_number"), 0) or None,
        "goal": (chapter.plan or {}).get("goal"),
        "locked": locked,
        "summary": chapter.summary,
    }
    if locked:
        context["content_excerpt"] = _chapter_content_excerpt(chapter)
    return context


def _chapter_content_excerpt(chapter: Chapter, max_length: int = 600) -> str:
    text = chapter.final_text or chapter.revised_text or chapter.draft_text
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[:max_length].rstrip() + "..."


def _normalize_volume(value: object, fallback_number: int) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    volume_number = _positive_int(
        value.get("volume_number", value.get("volumeNumber")),
        fallback_number,
    )
    title = _text(value.get("title")) or f"第 {volume_number} 卷"
    core_conflict = (
        _text(value.get("core_conflict", value.get("coreConflict"))) or "推进本卷核心冲突。"
    )
    chapters = _normalize_chapters(value.get("chapters"), volume_number)
    return {
        "volume_number": volume_number,
        "title": title,
        "core_conflict": core_conflict,
        "pacing_curve": _list_values(value.get("pacing_curve", value.get("pacingCurve"))),
        "payoff_distribution": _list_values(
            value.get("payoff_distribution", value.get("payoffDistribution"))
        ),
        "key_turns": _list_values(value.get("key_turns", value.get("keyTurns"))),
        "commitments": _list_values(value.get("commitments")),
        "chapters": chapters,
    }


def _normalize_chapters(value: object, volume_number: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    chapters: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        fallback_number = (volume_number - 1) * 10 + index
        number = _positive_int(item.get("number"), 0)
        generated_number = number <= 0
        if generated_number:
            number = fallback_number
        title = _text(item.get("title")) or f"第 {number:02d} 章"
        goal = _text(item.get("goal", item.get("direction"))) or title
        chapters.append(
            {
                "number": number,
                "title": title,
                "goal": goal,
                "ending_hook": _text(item.get("ending_hook", item.get("endingHook"))),
                "must_write": _list_values(item.get("must_write", item.get("mustWrite"))),
                "word_budget": parse_word_count(item.get("word_budget", item.get("wordBudget"))),
                GENERATED_CHAPTER_NUMBER_KEY: generated_number,
            }
        )
    return chapters


def _chapter_plan_payload(
    volume_number: int,
    chapter_plan: dict[str, Any],
    book: Book,
) -> dict[str, Any]:
    word_budget = (
        parse_word_count(chapter_plan.get("word_budget"))
        or parse_word_count((book.constraints or {}).get(CHAPTER_WORD_COUNT_KEY))
        or DEFAULT_CHAPTER_WORD_COUNT
    )
    return {
        "volume_number": volume_number,
        "goal": chapter_plan["goal"],
        "must_write": chapter_plan["must_write"],
        "ending_hook": chapter_plan["ending_hook"] or "留下一个明确的新问题，推动读者进入下一章。",
        "word_budget": word_budget,
    }


def _simulated_volume_outline(book: Book, canon: Canon, chapters: list[Chapter]) -> dict[str, Any]:
    existing = chapters or []
    chapter_count = max(len(existing), 10)
    commitments = _list_values((canon.content or {}).get("foreshadowing"))
    return {
        "volumes": [
            {
                "volume_number": 1,
                "title": "第一卷",
                "core_conflict": book.premise or "推进项目主线。",
                "pacing_curve": ["开局钩子", "中段升级", "卷末兑现"],
                "payoff_distribution": commitments[:3],
                "key_turns": ["建立问题", "扩大冲突", "卷末转折"],
                "commitments": commitments,
                "chapters": [
                    {
                        "number": number,
                        "title": existing[number - 1].title
                        if number <= len(existing)
                        else f"第 {number:02d} 章",
                        "goal": _chapter_goal(existing[number - 1])
                        if number <= len(existing)
                        else "推进本卷主线。",
                        "ending_hook": "留下一个明确的新问题，推动读者进入下一章。",
                        "must_write": commitments,
                        "word_budget": None,
                    }
                    for number in range(1, chapter_count + 1)
                ],
            }
        ]
    }


def _simulated_volume_revision(
    book: Book,
    canon: Canon,
    chapters: list[Chapter],
    volume_plans: list[VolumePlan],
    request: dict[str, Any],
) -> dict[str, Any]:
    outline = _current_volume_outline(book, canon, chapters, volume_plans)
    notes = request["revision_notes"]
    target_volume = request.get("volume_number")
    for volume in outline["volumes"]:
        if target_volume is not None and volume["volume_number"] != target_volume:
            continue
        if request["scope"] in {"all_volumes", "volume_summary"}:
            volume["core_conflict"] = f"{volume['core_conflict']} 修订方向：{notes}"
    return outline


def _current_volume_outline(
    book: Book,
    canon: Canon,
    chapters: list[Chapter],
    volume_plans: list[VolumePlan],
) -> dict[str, Any]:
    if not volume_plans:
        return _simulated_volume_outline(book, canon, chapters)
    return {
        "volumes": [
            {
                **_volume_plan_context(plan),
                "chapters": [
                    _chapter_plan_from_chapter(chapter)
                    for chapter in chapters
                    if _positive_int((chapter.plan or {}).get("volume_number"), 0)
                    == plan.volume_number
                ],
            }
            for plan in volume_plans
        ]
    }


def _chapter_plan_from_chapter(chapter: Chapter) -> dict[str, Any]:
    plan = chapter.plan or {}
    return {
        "number": chapter.number,
        "title": chapter.title,
        "goal": _text(plan.get("goal")) or chapter.title,
        "ending_hook": _text(plan.get("ending_hook", plan.get("endingHook"))),
        "must_write": _list_values(plan.get("must_write", plan.get("mustWrite"))),
        "word_budget": parse_word_count(plan.get("word_budget", plan.get("wordBudget"))),
    }


def _chapter_goal(chapter: Chapter) -> str:
    goal = _text((chapter.plan or {}).get("goal"))
    return goal or chapter.summary or chapter.title


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        first = lines[0].strip()
        if first == "```" or first.startswith("```json"):
            return "\n".join(lines[1:-1]).strip()
    return text


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _list_values(value: object) -> list:
    if isinstance(value, list):
        return value
    if value in (None, "", {}):
        return []
    return [value]


def _positive_int(value: object, fallback: int) -> int:
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        return fallback
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback
