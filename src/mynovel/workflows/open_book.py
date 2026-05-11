from typing import Any

from sqlmodel import Session

from mynovel.domain.models import Book, BookStatus, Canon, Chapter, OpenBookBlueprint, VolumePlan
from mynovel.domain.repositories import add_book, add_canon, add_chapter, add_volume_plan
from mynovel.word_targets import CHAPTER_WORD_COUNT_KEY, target_word_counts_from_text


def create_draft_book(
    session: Session,
    idea: str,
    genre: str,
    audience: str,
    title: str = "Untitled",
) -> Book:
    return add_book(
        session,
        Book(
            title=title,
            genre=genre,
            audience=audience,
            premise=idea,
        ),
    )


def create_draft_book_from_blueprint(
    session: Session,
    blueprint: OpenBookBlueprint,
    selected_title: str,
) -> Book:
    title = selected_title.strip()
    if not title:
        raise ValueError("Title selection is required.")

    title_options = title_options_from_blueprint(blueprint.content)
    if title not in title_options:
        raise ValueError("Title selection must be one of the candidates.")

    target_words = target_word_counts_from_text(blueprint.idea)
    book = create_draft_book(
        session,
        title=title,
        idea=blueprint.idea,
        genre=_blueprint_text(blueprint.content.get("genre")),
        audience=_blueprint_text(blueprint.content.get("audience")),
    )
    book.status = BookStatus.CANON_LOCKED
    book.constraints = {
        "selling_points": blueprint.content.get("selling_points", []),
        "reader_promises": blueprint.content.get("reader_promises", []),
        **target_words,
    }
    session.add(book)
    session.commit()
    session.refresh(book)

    if book.id is None:
        raise ValueError("Book must be persisted before creating production state.")

    add_canon(
        session, Canon(book_id=book.id, version=1, content=_initial_canon_content(book, blueprint))
    )
    add_volume_plan(session, _volume_plan_from_blueprint(book.id, blueprint.content))
    for chapter in _chapters_from_blueprint(
        book.id,
        blueprint.content,
        target_words.get(CHAPTER_WORD_COUNT_KEY),
    ):
        add_chapter(session, chapter)

    session.refresh(book)
    return book


def title_options_from_blueprint(content: dict) -> list[str]:
    title_options = content.get("title_options")
    if not isinstance(title_options, list):
        return []
    return [title for item in title_options if (title := str(item).strip())]


def _blueprint_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _initial_canon_content(book: Book, blueprint: OpenBookBlueprint) -> dict:
    return {
        "book": {
            "title": book.title,
            "genre": book.genre,
            "audience": book.audience,
            "premise": book.premise,
        },
        "world_rules": _mapping_or_text_list(blueprint.content.get("world")),
        "characters": _mapping_or_text_list(blueprint.content.get("protagonist")),
        "relationships": [],
        "locations": [],
        "foreshadowing": _list_values(blueprint.content.get("reader_promises")),
        "chapter_summaries": [],
        "state_history": [],
    }


def _chapters_from_blueprint(
    book_id: int,
    content: dict,
    chapter_word_count: int | None = None,
) -> list[Chapter]:
    directions = content.get("chapter_directions")
    if not isinstance(directions, list):
        directions = []

    chapters = []
    for number in range(1, 11):
        raw_direction = directions[number - 1] if number <= len(directions) else {}
        title, goal = _chapter_title_and_goal(number, raw_direction)
        plan: dict[str, Any] = {
            "goal": goal,
            "must_write": _list_values(content.get("reader_promises")),
            "ending_hook": "留下一个明确的新问题，推动读者进入下一章。",
        }
        if chapter_word_count is not None:
            plan["word_budget"] = chapter_word_count
        chapters.append(
            Chapter(
                book_id=book_id,
                number=number,
                title=title,
                plan=plan,
            )
        )
    return chapters


def _volume_plan_from_blueprint(book_id: int, content: dict) -> VolumePlan:
    raw_plan = content.get("volume_plan")
    plan = raw_plan if isinstance(raw_plan, dict) else {}
    core_conflict = str(
        plan.get("core_conflict") or content.get("central_conflict") or "推进首卷核心冲突。"
    ).strip()
    return VolumePlan(
        book_id=book_id,
        volume_number=int(plan.get("volume_number", 1) or 1),
        title=str(plan.get("title") or "第一卷").strip(),
        core_conflict=core_conflict,
        pacing_curve=_list_values(plan.get("pacing_curve") or content.get("chapter_directions")),
        payoff_distribution=_list_values(plan.get("payoff_distribution")),
        key_turns=_list_values(plan.get("key_turns")),
        commitments=_list_values(plan.get("commitments") or content.get("reader_promises")),
    )


def _chapter_title_and_goal(number: int, raw_direction: object) -> tuple[str, str]:
    fallback_title = f"第 {number:02d} 章"
    if isinstance(raw_direction, dict):
        title = str(
            raw_direction.get("title") or raw_direction.get("chapter") or fallback_title
        ).strip()
        goal = str(raw_direction.get("goal") or raw_direction.get("direction") or title).strip()
        return title, goal
    if raw_direction:
        text = str(raw_direction).strip()
        return text[:24] or fallback_title, text
    return fallback_title, "按照开书方向推进主线，并保留章节结尾钩子。"


def _list_values(value: object) -> list:
    if isinstance(value, list):
        return value
    if value in (None, "", {}):
        return []
    return [value]


def _mapping_or_text_list(value: object) -> list:
    if isinstance(value, dict):
        return [{"name": str(key), "detail": item} for key, item in value.items()]
    return _list_values(value)
