from __future__ import annotations

from mynovel.domain.models import Book, Chapter

TARGET_WORD_COUNT_KEY = "target_word_count"
CHAPTER_WORD_COUNT_KEY = "chapter_word_count"
DEFAULT_TARGET_WORD_COUNT = 120_000
DEFAULT_CHAPTER_WORD_COUNT = 2_800

BOOK_TARGET_LABEL = "全书目标字数"
CHAPTER_TARGET_LABEL = "单章目标字数"


def parse_word_count(value: object) -> int | None:
    text = str(value or "").strip()
    digits = "".join(character for character in text if character.isdigit())
    if not digits:
        return None
    count = int(digits)
    return count if count > 0 else None


def book_idea_from_form(form: dict[str, str]) -> str:
    idea = form.get("idea", "").strip()
    if not idea:
        return ""
    preferences = [
        ("题材", form.get("genre", "").strip()),
        ("目标读者", form.get("audience", "").strip()),
        (BOOK_TARGET_LABEL, _word_count_preference(form.get(TARGET_WORD_COUNT_KEY, ""))),
        (CHAPTER_TARGET_LABEL, _word_count_preference(form.get(CHAPTER_WORD_COUNT_KEY, ""))),
    ]
    filled_preferences = [f"- {label}：{value}" for label, value in preferences if value]
    if not filled_preferences:
        return idea
    return "\n".join(["一句灵感：" + idea, "可选偏好：", *filled_preferences])


def target_word_counts_from_text(text: str) -> dict[str, int]:
    targets: dict[str, int] = {}
    label_keys = {
        BOOK_TARGET_LABEL: TARGET_WORD_COUNT_KEY,
        CHAPTER_TARGET_LABEL: CHAPTER_WORD_COUNT_KEY,
    }
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("-").strip()
        for label, key in label_keys.items():
            prefix = f"{label}："
            if line.startswith(prefix):
                count = parse_word_count(line.removeprefix(prefix))
                if count is not None:
                    targets[key] = count
    return targets


def book_target_word_count(book: Book) -> int:
    return parse_word_count(book.constraints.get(TARGET_WORD_COUNT_KEY)) or DEFAULT_TARGET_WORD_COUNT


def chapter_word_budget(chapter: Chapter) -> int:
    return parse_word_count(chapter.plan.get("word_budget")) or DEFAULT_CHAPTER_WORD_COUNT


def format_word_count(count: object) -> str:
    parsed = parse_word_count(count)
    if parsed is None:
        return "未设置"
    return f"{parsed:,} 字"


def _word_count_preference(value: object) -> str:
    count = parse_word_count(value)
    if count is None:
        return ""
    return f"{count} 字"
