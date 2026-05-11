from sqlmodel import Session

from mynovel.blueprint_revision import (
    REGENERATE_BLUEPRINT_NOTES,
    create_revision_blueprint_job,
    revision_notes_from_form,
)
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, OpenBookBlueprint
from mynovel.domain.repositories import add_open_book_blueprint


def test_revision_notes_from_form_combines_typed_feedback_with_batch_request() -> None:
    notes = revision_notes_from_form(
        {
            "revision_notes": "女主职业爽点更强",
            "revision_preset": REGENERATE_BLUEPRINT_NOTES,
        }
    )

    assert "女主职业爽点更强" in notes
    assert REGENERATE_BLUEPRINT_NOTES in notes


def test_revision_job_uses_clicked_blueprint_as_parent(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        first = add_open_book_blueprint(
            session,
            OpenBookBlueprint(
                idea="现代医生穿越将军府",
                version=1,
                status=BlueprintStatus.SUCCEEDED,
                content={"genre": "古言"},
                raw_response="{}",
            ),
        )
        first_id = first.id
        add_open_book_blueprint(
            session,
            OpenBookBlueprint(
                idea="另一个更新的任务",
                version=99,
                status=BlueprintStatus.SUCCEEDED,
                content={"genre": "玄幻"},
                raw_response="{}",
            ),
        )

        job = create_revision_blueprint_job(
            session,
            {"blueprint_id": str(first_id)},
            fallback_blueprints=[],
            revision_notes="保持题材但扩大差异",
        )

    assert job.parent_id == first_id
    assert job.idea == "现代医生穿越将军府"
    assert job.version == 2
    assert job.instruction == "保持题材但扩大差异"
