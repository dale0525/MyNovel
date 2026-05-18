from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import Book, Chapter, ChapterStatus
from mynovel.domain.repositories import add_book, add_chapter, get_book, list_chapters_for_book
from mynovel.word_targets import count_chapter_words, update_book_word_targets


def test_count_chapter_words_ignores_whitespace_but_keeps_visible_punctuation() -> None:
    assert count_chapter_words("沈惊鸿。\n\n 百草堂\t开门  ") == 9


def test_update_book_word_targets_can_leave_existing_chapters_unchanged(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = add_book(
            session,
            Book(
                title="长夜图书馆",
                genre="奇幻连载",
                audience="成长冒险读者",
                constraints={"target_word_count": 120000, "chapter_word_count": 2800},
            ),
        )
        add_chapter(
            session, Chapter(book_id=book.id, number=1, title="召唤", plan={"word_budget": 2800})
        )

        update_book_word_targets(
            session,
            book.id,
            target_word_count=300000,
            chapter_word_count=3200,
            update_existing_chapters=False,
        )
        saved = get_book(session, book.id)
        chapters = list_chapters_for_book(session, book.id)

    assert saved is not None
    assert saved.constraints["target_word_count"] == 300000
    assert saved.constraints["chapter_word_count"] == 3200
    assert chapters[0].plan["word_budget"] == 2800


def test_update_book_word_targets_can_sync_existing_chapters(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = add_book(
            session,
            Book(
                title="长夜图书馆",
                genre="奇幻连载",
                audience="成长冒险读者",
                constraints={"selling_points": ["禁书体系"]},
            ),
        )
        add_chapter(
            session, Chapter(book_id=book.id, number=1, title="召唤", plan={"word_budget": 2800})
        )
        add_chapter(
            session, Chapter(book_id=book.id, number=2, title="迷雾", plan={"goal": "入谷"})
        )
        add_chapter(
            session,
            Chapter(
                book_id=book.id,
                number=3,
                title="定稿",
                status=ChapterStatus.ACCEPTED,
                plan={"word_budget": 2800},
            ),
        )

        update_book_word_targets(
            session,
            book.id,
            target_word_count=300000,
            chapter_word_count=3200,
            update_existing_chapters=True,
        )
        saved = get_book(session, book.id)
        chapters = list_chapters_for_book(session, book.id)

    assert saved is not None
    assert saved.constraints["selling_points"] == ["禁书体系"]
    assert saved.constraints["target_word_count"] == 300000
    assert saved.constraints["chapter_word_count"] == 3200
    assert [chapter.plan["word_budget"] for chapter in chapters] == [3200, 3200, 2800]
