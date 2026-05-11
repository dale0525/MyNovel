from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, Book, OpenBookBlueprint
from mynovel.domain.repositories import get_open_book_blueprint
from mynovel.workflows.open_book import create_draft_book_from_blueprint, lock_canon_foundation


class BlueprintAcceptanceError(ValueError):
    pass


class BlueprintNotFoundError(BlueprintAcceptanceError):
    pass


class BlueprintNotReadyError(BlueprintAcceptanceError):
    pass


class BlueprintTitleSelectionError(BlueprintAcceptanceError):
    def __init__(self, blueprint: OpenBookBlueprint) -> None:
        super().__init__("Blueprint title selection is invalid.")
        self.blueprint = blueprint


def accept_blueprint_for_foundation_review(db_path: Path, form: dict[str, str]) -> Book:
    blueprint_id = int(form.get("blueprint_id", "0"))
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        blueprint = get_open_book_blueprint(session, blueprint_id)
        if blueprint is None:
            raise BlueprintNotFoundError("Blueprint not found.")
        if blueprint.status != BlueprintStatus.SUCCEEDED:
            raise BlueprintNotReadyError("Blueprint is not ready.")
        try:
            return create_draft_book_from_blueprint(
                session,
                blueprint,
                selected_title=form.get("selected_title", ""),
                lock_foundation=False,
            )
        except ValueError as error:
            raise BlueprintTitleSelectionError(blueprint) from error


def lock_canon_from_form(db_path: Path, form: dict[str, str]) -> Book:
    book_id = int(form.get("book_id", "0"))
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        return lock_canon_foundation(session, book_id)
