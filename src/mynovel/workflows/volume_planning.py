from __future__ import annotations

import json
from typing import Any, Protocol

from sqlmodel import Session

from mynovel.domain.models import Book, Canon, Chapter, ChapterStatus, RunTrace, VolumePlan, utc_now
from mynovel.domain.repositories import (
    get_book,
    get_latest_canon,
    list_chapters_for_book,
    list_volume_plans_for_book,
)
from mynovel.word_targets import CHAPTER_WORD_COUNT_KEY, DEFAULT_CHAPTER_WORD_COUNT, parse_word_count


class VolumePlanningModelClient(Protocol):
    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        pass


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

    _apply_volume_outline(session, book, outline, model_name)
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
    schema_prompt = (
        "JSON 必须包含 volumes 数组。每个 volume 包含 volume_number, title, core_conflict, "
        "pacing_curve, payoff_distribution, key_turns, commitments, chapters。"
        "chapters 必须是单章列表，每项包含 number, title, goal，可包含 ending_hook, must_write。"
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


def _apply_volume_outline(
    session: Session,
    book: Book,
    outline: dict[str, Any],
    model_name: str | None,
) -> None:
    if book.id is None:
        raise ValueError("Book must be persisted before volume planning.")

    existing_plans = {
        plan.volume_number: plan
        for plan in list_volume_plans_for_book(session, book.id)
    }
    existing_chapters = {
        chapter.number: chapter
        for chapter in list_chapters_for_book(session, book.id)
    }
    generated_chapter_count = 0

    for volume in outline["volumes"]:
        volume_number = volume["volume_number"]
        plan = existing_plans.get(volume_number)
        if plan is None:
            plan = VolumePlan(book_id=book.id, volume_number=volume_number, title=volume["title"])
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
            if chapter is not None and chapter.status != ChapterStatus.PLANNED:
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


def _normalize_volume(value: object, fallback_number: int) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    volume_number = _positive_int(
        value.get("volume_number", value.get("volumeNumber")),
        fallback_number,
    )
    title = _text(value.get("title")) or f"第 {volume_number} 卷"
    core_conflict = _text(value.get("core_conflict", value.get("coreConflict"))) or "推进本卷核心冲突。"
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
        number = _positive_int(item.get("number"), fallback_number)
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
                        "title": existing[number - 1].title if number <= len(existing) else f"第 {number:02d} 章",
                        "goal": _chapter_goal(existing[number - 1]) if number <= len(existing) else "推进本卷主线。",
                        "ending_hook": "留下一个明确的新问题，推动读者进入下一章。",
                        "must_write": commitments,
                        "word_budget": None,
                    }
                    for number in range(1, chapter_count + 1)
                ],
            }
        ]
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
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback
