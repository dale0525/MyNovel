from __future__ import annotations

import html

from mynovel.domain.models import Book
from mynovel.i18n import DEFAULT_LOCALE, t
from mynovel.word_targets import (
    CHAPTER_WORD_COUNT_KEY,
    DEFAULT_CHAPTER_WORD_COUNT,
    DEFAULT_TARGET_WORD_COUNT,
    TARGET_WORD_COUNT_KEY,
    parse_word_count,
)


def render_word_target_form(book: Book, locale: str = DEFAULT_LOCALE) -> str:
    target_word_count = (
        parse_word_count(book.constraints.get(TARGET_WORD_COUNT_KEY)) or DEFAULT_TARGET_WORD_COUNT
    )
    chapter_word_count = (
        parse_word_count(book.constraints.get(CHAPTER_WORD_COUNT_KEY)) or DEFAULT_CHAPTER_WORD_COUNT
    )
    return f"""
      <form method="post" action="/book-word-targets" class="compact-form action-form">
        <input type="hidden" name="book_id" value="{book.id or 0}">
        <label>{t("word_targets.total_label", locale)}<input name="target_word_count" type="number" value="{target_word_count}" min="1"></label>
        <label>{t("word_targets.chapter_label", locale)}<input name="chapter_word_count" type="number" value="{chapter_word_count}" min="1"></label>
        <label class="inline-check"><input name="update_existing_chapters" type="checkbox" value="1"><span>{t("word_targets.update_existing", locale)}</span></label>
        <button class="secondary" type="submit">{html.escape(t("word_targets.save", locale))}</button>
      </form>
"""
