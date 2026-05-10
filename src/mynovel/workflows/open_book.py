from sqlmodel import Session

from mynovel.domain.models import Book, OpenBookBlueprint
from mynovel.domain.repositories import add_book


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

    return create_draft_book(
        session,
        title=title,
        idea=blueprint.idea,
        genre=_blueprint_text(blueprint.content.get("genre")),
        audience=_blueprint_text(blueprint.content.get("audience")),
    )


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
