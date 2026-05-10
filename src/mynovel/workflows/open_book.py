from sqlmodel import Session

from mynovel.domain.models import Book
from mynovel.domain.repositories import add_book


def create_draft_book(session: Session, idea: str, genre: str, audience: str) -> Book:
    return add_book(
        session,
        Book(
            title="Untitled",
            genre=genre,
            audience=audience,
            premise=idea,
        ),
    )
