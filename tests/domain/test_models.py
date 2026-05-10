from mynovel.domain.models import Book, BookStatus


def test_book_defaults_to_draft() -> None:
    book = Book(title="Untitled", genre="xianxia", audience="web novel readers")

    assert book.status == BookStatus.DRAFT
