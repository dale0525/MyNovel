import json
from pathlib import Path

import pytest
from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import (
    Book,
    Canon,
    CanonProposalRevision,
    CanonProposalRevisionStatus,
)
from mynovel.domain.repositories import (
    add_book,
    add_canon,
    add_canon_proposal_revision,
    get_book,
    get_canon_proposal_revision,
    get_latest_canon,
    list_pending_canon_proposal_revisions_for_book,
)
from mynovel.workflows.canon_proposal import (
    CANON_PROPOSAL_KEY,
    apply_canon_proposal_revision,
    content_hash,
    create_canon_proposal_revision,
    locks_hash,
    section_locks_for_book,
    set_canon_proposal_section_lock,
)
from mynovel.workflows.open_book import lock_canon_foundation


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


def test_section_locks_default_to_unlocked_for_editable_sections() -> None:
    book = Book(id=1, title="长夜图书馆", genre="奇幻", audience="连载读者")

    locks = section_locks_for_book(book)

    assert locks["characters"] is False
    assert locks["world_rules"] is False
    assert locks["state_history"] is True


def test_draft_book_can_toggle_section_lock(tmp_path: Path) -> None:
    engine = create_engine_for_path(tmp_path / "test.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(session, Book(title="长夜图书馆", genre="奇幻", audience="连载读者"))
        set_canon_proposal_section_lock(session, book.id, "world_rules", True)
        loaded = get_book(session, book.id or 0)

    assert loaded is not None
    assert loaded.constraints[CANON_PROPOSAL_KEY]["section_locks"]["world_rules"] is True


class FakeCanonRevisionClient:
    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        assert stage == "canon_proposal_revision"
        assert response_format == "json"
        return """
        {
          "target_section": "characters",
          "changed_sections": {
            "characters": [{"name": "林烬", "trait": "外冷内热"}],
            "relationships": [{"from": "林烬", "to": "旧王朝", "detail": "血缘牵连"}]
          },
          "blocked_sections": [],
          "summary": "已调整人物和关系。",
          "risks": ["第 3-5 章动机需要同步。"]
        }
        """


class TargetSectionClient:
    def __init__(self, target_section: str | None, *, include_target: bool = True) -> None:
        self.target_section = target_section
        self.include_target = include_target

    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        assert stage == "canon_proposal_revision"
        assert response_format == "json"
        payload: dict[str, object] = {
            "changed_sections": {"characters": [{"name": "林烬", "trait": "外冷内热"}]},
            "blocked_sections": [],
            "summary": "已调整人物。",
            "risks": [],
        }
        if self.include_target:
            payload["target_section"] = self.target_section
        return json.dumps(payload, ensure_ascii=False)


def test_create_revision_preview_persists_ai_output_with_base_hashes(tmp_path: Path) -> None:
    engine = create_engine_for_path(tmp_path / "test.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(session, Book(title="长夜图书馆", genre="奇幻", audience="连载读者"))
        add_canon(session, Canon(book_id=book.id or 0, version=1, content={"characters": []}))

        revision = create_canon_proposal_revision(
            session,
            book.id,
            "characters",
            "主角改成外冷内热",
            FakeCanonRevisionClient(),
        )

    assert revision.status == CanonProposalRevisionStatus.PENDING
    assert revision.allowed_sections
    assert revision.base_content_hash
    assert revision.changed_sections["relationships"][0]["to"] == "旧王朝"


@pytest.mark.parametrize(
    ("ai_target_section", "include_target", "lock_world_rules"),
    [
        (None, False, False),
        ("unknown", True, False),
        ("state_history", True, False),
        ("world_rules", True, True),
        ("world_rules", True, False),
    ],
)
def test_create_revision_preview_rejects_invalid_ai_target_section(
    tmp_path: Path,
    ai_target_section: str | None,
    include_target: bool,
    lock_world_rules: bool,
) -> None:
    engine = create_engine_for_path(tmp_path / "test.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(session, Book(title="长夜图书馆", genre="奇幻", audience="连载读者"))
        add_canon(session, Canon(book_id=book.id or 0, version=1, content={"characters": []}))
        if lock_world_rules:
            set_canon_proposal_section_lock(session, book.id, "world_rules", True)

        with pytest.raises(ValueError):
            create_canon_proposal_revision(
                session,
                book.id,
                "characters",
                "主角改成外冷内热",
                TargetSectionClient(ai_target_section, include_target=include_target),
            )


def test_apply_revision_replaces_unlocked_sections_and_appends_history(
    tmp_path: Path,
) -> None:
    engine = create_engine_for_path(tmp_path / "test.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(session, Book(title="长夜图书馆", genre="奇幻", audience="连载读者"))
        canon = add_canon(
            session,
            Canon(
                book_id=book.id or 0,
                version=1,
                content={
                    "characters": [{"name": "林烬", "trait": "冷淡"}],
                    "relationships": [],
                    "state_history": [],
                },
            ),
        )
        revision = add_canon_proposal_revision(
            session,
            CanonProposalRevision(
                book_id=book.id or 0,
                base_canon_version=canon.version,
                base_content_hash=content_hash(canon.content),
                base_locks_hash=locks_hash(section_locks_for_book(book)),
                target_section="characters",
                instruction="主角改成外冷内热",
                allowed_sections=["characters", "relationships"],
                locked_sections=[],
                changed_sections={
                    "characters": [{"name": "林烬", "trait": "外冷内热"}],
                    "relationships": [
                        {"from": "林烬", "to": "旧王朝", "detail": "血缘牵连"}
                    ],
                },
                summary="已调整人物和关系。",
                risks=["第 3-5 章动机需要同步。"],
            ),
        )

        applied = apply_canon_proposal_revision(session, book.id or 0, revision.id or 0)
        updated_canon = get_latest_canon(session, book.id or 0)
        updated_book = get_book(session, book.id or 0)

    assert applied.status == CanonProposalRevisionStatus.APPLIED
    assert updated_canon is not None
    assert updated_canon.content["characters"] == [{"name": "林烬", "trait": "外冷内热"}]
    assert updated_canon.content["relationships"][0]["to"] == "旧王朝"
    assert updated_canon.content["state_history"][-1]["summary"] == "已调整人物和关系。"
    assert updated_book is not None
    last_revision = updated_book.constraints[CANON_PROPOSAL_KEY]["last_revision"]
    assert last_revision["target_section"] == "characters"
    assert last_revision["changed_sections"] == ["characters", "relationships"]


def test_apply_revision_rejects_locked_section_atomically(tmp_path: Path) -> None:
    engine = create_engine_for_path(tmp_path / "test.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(session, Book(title="长夜图书馆", genre="奇幻", audience="连载读者"))
        canon = add_canon(
            session,
            Canon(
                book_id=book.id or 0,
                version=1,
                content={
                    "world_rules": [{"name": "雾墙规则", "detail": "不能复活"}],
                    "characters": [{"name": "林烬", "trait": "冷淡"}],
                },
            ),
        )
        set_canon_proposal_section_lock(session, book.id, "world_rules", True)
        locked_book = get_book(session, book.id or 0)
        assert locked_book is not None
        revision = add_canon_proposal_revision(
            session,
            CanonProposalRevision(
                book_id=book.id or 0,
                base_canon_version=canon.version,
                base_content_hash=content_hash(canon.content),
                base_locks_hash=locks_hash(section_locks_for_book(locked_book)),
                target_section="characters",
                instruction="让主角能复活死人",
                allowed_sections=["characters"],
                locked_sections=["world_rules"],
                changed_sections={
                    "characters": [{"name": "林烬", "trait": "能复活死人"}],
                    "world_rules": [{"name": "复活规则", "detail": "可以复活"}],
                },
                summary="尝试修改世界规则。",
            ),
        )

        with pytest.raises(ValueError):
            apply_canon_proposal_revision(session, book.id or 0, revision.id or 0)
        unchanged_canon = get_latest_canon(session, book.id or 0)
        unchanged_revision = get_canon_proposal_revision(session, revision.id or 0)

    assert unchanged_canon is not None
    assert unchanged_canon.content == canon.content
    assert unchanged_canon.content["characters"] == [{"name": "林烬", "trait": "冷淡"}]
    assert unchanged_revision is not None
    assert unchanged_revision.status != CanonProposalRevisionStatus.APPLIED


def test_apply_revision_marks_preview_stale_when_content_changes(tmp_path: Path) -> None:
    engine = create_engine_for_path(tmp_path / "test.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(session, Book(title="长夜图书馆", genre="奇幻", audience="连载读者"))
        canon = add_canon(
            session,
            Canon(book_id=book.id or 0, version=1, content={"characters": []}),
        )
        revision = add_canon_proposal_revision(
            session,
            CanonProposalRevision(
                book_id=book.id or 0,
                base_canon_version=canon.version,
                base_content_hash=content_hash(canon.content),
                base_locks_hash=locks_hash(section_locks_for_book(book)),
                target_section="characters",
                instruction="主角改成外冷内热",
                allowed_sections=["characters"],
                locked_sections=[],
                changed_sections={"characters": [{"name": "林烬"}]},
                summary="已调整人物。",
            ),
        )
        canon.content = {"characters": [{"name": "别人"}]}
        session.add(canon)
        session.commit()

        with pytest.raises(ValueError):
            apply_canon_proposal_revision(session, book.id or 0, revision.id or 0)
        stale_revision = get_canon_proposal_revision(session, revision.id or 0)
        unchanged_canon = get_latest_canon(session, book.id or 0)

    assert stale_revision is not None
    assert stale_revision.status == CanonProposalRevisionStatus.STALE
    assert unchanged_canon is not None
    assert unchanged_canon.content == {"characters": [{"name": "别人"}]}


def test_apply_revision_after_global_lock_marks_preview_stale(tmp_path: Path) -> None:
    engine = create_engine_for_path(tmp_path / "test.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(session, Book(title="长夜图书馆", genre="奇幻", audience="连载读者"))
        canon = add_canon(
            session,
            Canon(
                book_id=book.id or 0,
                version=1,
                content={
                    "world_rules": [],
                    "characters": [{"name": "林烬", "trait": "冷淡"}],
                    "factions": [],
                    "locations": [],
                    "relationships": [],
                    "foreshadowing": [],
                    "chapter_summaries": [],
                    "state_history": [],
                },
            ),
        )
        revision = add_canon_proposal_revision(
            session,
            CanonProposalRevision(
                book_id=book.id or 0,
                base_canon_version=canon.version,
                base_content_hash=content_hash(canon.content),
                base_locks_hash=locks_hash(section_locks_for_book(book)),
                target_section="characters",
                instruction="主角改成外冷内热",
                allowed_sections=["characters"],
                locked_sections=[],
                changed_sections={"characters": [{"name": "林烬", "trait": "外冷内热"}]},
                summary="已调整人物。",
            ),
        )
        lock_canon_foundation(session, book.id)

        with pytest.raises(ValueError):
            apply_canon_proposal_revision(session, book.id or 0, revision.id or 0)
        stale_revision = get_canon_proposal_revision(session, revision.id or 0)
        latest = get_latest_canon(session, book.id or 0)

    assert stale_revision is not None
    assert stale_revision.status == CanonProposalRevisionStatus.STALE
    assert latest is not None
    assert latest.content["characters"] == [{"name": "林烬", "trait": "冷淡"}]


def test_apply_revision_after_section_lock_change_marks_preview_stale(tmp_path: Path) -> None:
    engine = create_engine_for_path(tmp_path / "test.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(session, Book(title="长夜图书馆", genre="奇幻", audience="连载读者"))
        canon = add_canon(
            session,
            Canon(
                book_id=book.id or 0,
                version=1,
                content={"characters": [{"name": "林烬", "trait": "冷淡"}]},
            ),
        )
        revision = add_canon_proposal_revision(
            session,
            CanonProposalRevision(
                book_id=book.id or 0,
                base_canon_version=canon.version,
                base_content_hash=content_hash(canon.content),
                base_locks_hash=locks_hash(section_locks_for_book(book)),
                target_section="characters",
                instruction="主角改成外冷内热",
                allowed_sections=["characters"],
                locked_sections=[],
                changed_sections={"characters": [{"name": "林烬", "trait": "外冷内热"}]},
                summary="已调整人物。",
            ),
        )
        set_canon_proposal_section_lock(session, book.id, "characters", True)

        with pytest.raises(ValueError):
            apply_canon_proposal_revision(session, book.id or 0, revision.id or 0)
        stale_revision = get_canon_proposal_revision(session, revision.id or 0)
        latest = get_latest_canon(session, book.id or 0)

    assert stale_revision is not None
    assert stale_revision.status == CanonProposalRevisionStatus.STALE
    assert latest is not None
    assert latest.content["characters"] == [{"name": "林烬", "trait": "冷淡"}]
