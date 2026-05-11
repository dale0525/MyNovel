from __future__ import annotations

import json

from mynovel.domain.models import Book, Canon, Chapter, ChapterStatus


def export_book_markdown(book: Book, chapters: list[Chapter]) -> str:
    accepted = _accepted_chapters(chapters)
    sections = [f"# {book.title}", "", f"题材：{book.genre}", f"目标读者：{book.audience}", ""]
    for chapter in accepted:
        sections.extend(
            [
                f"## 第 {chapter.number:02d} 章 {chapter.title}",
                "",
                chapter.final_text,
                "",
            ]
        )
    return "\n".join(sections).strip() + "\n"


def export_book_json(book: Book, canon: Canon | None, chapters: list[Chapter]) -> str:
    payload = {
        "book": {
            "title": book.title,
            "genre": book.genre,
            "audience": book.audience,
            "premise": book.premise,
        },
        "trusted_state": {
            "version": canon.version if canon else 0,
            "content": canon.content if canon else {},
        },
        "chapters": [
            {
                "number": chapter.number,
                "title": chapter.title,
                "text": chapter.final_text,
                "word_count": chapter.word_count,
            }
            for chapter in _accepted_chapters(chapters)
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _accepted_chapters(chapters: list[Chapter]) -> list[Chapter]:
    return [
        chapter
        for chapter in sorted(chapters, key=lambda item: item.number)
        if chapter.status == ChapterStatus.ACCEPTED and chapter.final_text
    ]
