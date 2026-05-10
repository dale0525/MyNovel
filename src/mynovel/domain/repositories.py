from sqlmodel import Session

from mynovel.domain.models import Book


def add_book(session: Session, book: Book) -> Book:
    session.add(book)
    session.commit()
    session.refresh(book)
    return book
