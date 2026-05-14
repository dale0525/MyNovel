from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from mynovel.domain.models import (
    Book,
    Canon,
    Chapter,
    DeconstructionStudy,
    OpenBookBlueprint,
    QualitySnapshot,
    RunTrace,
    StyleAsset,
    VectorEntry,
    VolumePlan,
)

LEGACY_PLACEHOLDER_TITLE = "".join(("幽", "谷", "回", "声"))
LEGACY_PLACEHOLDER_GENRE = "奇幻连载"
LEGACY_PLACEHOLDER_AUDIENCE = "成长冒险读者"
LEGACY_PLACEHOLDER_PREMISE = "少年罗斯在幽谷边境听见远古召唤，发现自己与失落王朝有关。"
LEGACY_PLACEHOLDER_IDEA = "少年在雾谷边境发现古老召唤符号，被迫踏入失落王朝的遗迹。"


def remove_legacy_placeholder_data(engine: Engine) -> None:
    with Session(engine) as session:
        books = list(session.exec(select(Book)))
        for book in books:
            if book.id is not None and _is_legacy_placeholder_book(book):
                _delete_book_children(session, book.id)
                session.delete(book)

        blueprints = list(session.exec(select(OpenBookBlueprint)))
        for blueprint in blueprints:
            if _is_legacy_placeholder_blueprint(blueprint):
                session.delete(blueprint)

        session.commit()


def _is_legacy_placeholder_book(book: Book) -> bool:
    return (
        book.title == LEGACY_PLACEHOLDER_TITLE
        and book.genre == LEGACY_PLACEHOLDER_GENRE
        and book.audience == LEGACY_PLACEHOLDER_AUDIENCE
        and book.premise == LEGACY_PLACEHOLDER_PREMISE
    )


def _is_legacy_placeholder_blueprint(blueprint: OpenBookBlueprint) -> bool:
    if blueprint.idea == LEGACY_PLACEHOLDER_IDEA:
        return True
    title_options = blueprint.content.get("title_options")
    return isinstance(title_options, list) and LEGACY_PLACEHOLDER_TITLE in title_options


def _delete_book_children(session: Session, book_id: int) -> None:
    for chapter in session.exec(select(Chapter).where(Chapter.book_id == book_id)):
        session.delete(chapter)
    for canon in session.exec(select(Canon).where(Canon.book_id == book_id)):
        session.delete(canon)
    for volume_plan in session.exec(select(VolumePlan).where(VolumePlan.book_id == book_id)):
        session.delete(volume_plan)
    for run_trace in session.exec(select(RunTrace).where(RunTrace.book_id == book_id)):
        session.delete(run_trace)
    for vector_entry in session.exec(select(VectorEntry).where(VectorEntry.book_id == book_id)):
        session.delete(vector_entry)
    for style_asset in session.exec(select(StyleAsset).where(StyleAsset.book_id == book_id)):
        session.delete(style_asset)
    for study in session.exec(
        select(DeconstructionStudy).where(DeconstructionStudy.book_id == book_id)
    ):
        session.delete(study)
    for snapshot in session.exec(select(QualitySnapshot).where(QualitySnapshot.book_id == book_id)):
        session.delete(snapshot)
