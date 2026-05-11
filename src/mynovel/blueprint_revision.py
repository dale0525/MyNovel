from __future__ import annotations

from sqlmodel import Session

from mynovel.domain.models import OpenBookBlueprint
from mynovel.domain.repositories import get_open_book_blueprint
from mynovel.workflows.open_book_blueprint import create_blueprint_job

REGENERATE_BLUEPRINT_NOTES = "请重新生成一组方向，保持题材但扩大差异。"


def revision_notes_from_form(form: dict[str, str]) -> str:
    notes = form.get("revision_notes", "").strip()
    preset = form.get("revision_preset", "").strip()
    if notes and preset:
        return "\n".join([notes, preset])
    return notes or preset


def create_revision_blueprint_job(
    session: Session,
    form: dict[str, str],
    fallback_blueprints: list[OpenBookBlueprint],
    revision_notes: str,
) -> OpenBookBlueprint:
    parent = _parent_blueprint_from_form(session, form)
    if parent is None and fallback_blueprints:
        fallback_id = fallback_blueprints[0].id
        parent = get_open_book_blueprint(session, fallback_id) if fallback_id is not None else None
    if parent is None or parent.id is None:
        raise ValueError("Blueprint to revise was not found.")
    return create_blueprint_job(
        session,
        idea=parent.idea,
        version=parent.version + 1,
        instruction=revision_notes,
        parent_id=parent.id,
    )


def _parent_blueprint_from_form(
    session: Session,
    form: dict[str, str],
) -> OpenBookBlueprint | None:
    try:
        blueprint_id = int(form.get("blueprint_id", "0") or "0")
    except ValueError:
        return None
    if blueprint_id <= 0:
        return None
    return get_open_book_blueprint(session, blueprint_id)
