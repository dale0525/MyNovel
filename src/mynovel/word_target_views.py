from __future__ import annotations

import html

from mynovel.domain.models import Book
from mynovel.word_targets import (
    CHAPTER_WORD_COUNT_KEY,
    DEFAULT_CHAPTER_WORD_COUNT,
    DEFAULT_TARGET_WORD_COUNT,
    TARGET_WORD_COUNT_KEY,
    parse_word_count,
)


def render_word_target_form(book: Book) -> str:
    target_word_count = (
        parse_word_count(book.constraints.get(TARGET_WORD_COUNT_KEY)) or DEFAULT_TARGET_WORD_COUNT
    )
    chapter_word_count = (
        parse_word_count(book.constraints.get(CHAPTER_WORD_COUNT_KEY)) or DEFAULT_CHAPTER_WORD_COUNT
    )
    return f"""
      <form method="post" action="/book-word-targets" class="compact-form action-form">
        <input type="hidden" name="book_id" value="{book.id or 0}">
        <label>全书目标字数<input name="target_word_count" type="number" value="{target_word_count}" min="1"></label>
        <label>单章目标字数<input name="chapter_word_count" type="number" value="{chapter_word_count}" min="1"></label>
        <label class="inline-check"><input name="update_existing_chapters" type="checkbox" value="1"><span>同步更新已有章节计划</span></label>
        <button class="secondary" type="submit">{html.escape("保存目标字数")}</button>
      </form>
"""
