from pathlib import Path

from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import CanonProposalRevision, CanonProposalRevisionStatus
from mynovel.domain.repositories import (
    add_canon_proposal_revision,
    get_canon_proposal_revision,
    list_pending_canon_proposal_revisions_for_book,
)


def test_canon_proposal_revision_persists_structured_preview(tmp_path: Path) -> None:
    engine = create_engine_for_path(tmp_path / "test.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        revision = add_canon_proposal_revision(
            session,
            CanonProposalRevision(
                book_id=1,
                base_canon_version=1,
                base_content_hash="content-hash",
                base_locks_hash="locks-hash",
                target_section="characters",
                instruction="主角改成外冷内热",
                allowed_sections=["characters", "relationships"],
                locked_sections=["world_rules"],
                changed_sections={"characters": [{"name": "林烬"}]},
                blocked_sections=[{"section": "world_rules", "reason": "已锁定"}],
                summary="已调整人物。",
                risks=["关系需要同步检查。"],
            ),
        )

        loaded = get_canon_proposal_revision(session, revision.id or 0)
        pending = list_pending_canon_proposal_revisions_for_book(session, 1)

    assert loaded is not None
    assert loaded.status == CanonProposalRevisionStatus.PENDING
    assert loaded.changed_sections["characters"][0]["name"] == "林烬"
    assert [item.id for item in pending] == [revision.id]
