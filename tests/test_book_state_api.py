from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from sqlmodel import Session, select

from mynovel.api_routes import dispatch_api_get, dispatch_api_post
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import (
    Book,
    BookStatus,
    Canon,
    CanonProposalRevision,
    CanonProposalRevisionStatus,
    Chapter,
    ChapterStatus,
    RunTrace,
    VolumePlan,
)
from mynovel.domain.repositories import (
    add_book,
    add_canon,
    add_canon_proposal_revision,
    add_chapter,
    add_run_trace,
    add_volume_plan,
    get_book,
    get_canon_proposal_revision,
)
from mynovel.workflows.canon_proposal import content_hash, locks_hash, section_locks_for_book


def test_book_workspace_returns_chapters_canon_traces_and_volume_plans(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id = _create_workspace_fixture(db_path)

    response = dispatch_api_get(f"/api/books/{book_id}", "", db_path)

    assert response.status == HTTPStatus.OK
    assert response.body["book"]["title"] == "星港遗梦"
    assert response.body["chapters"] == [
        {
            "id": response.body["chapters"][0]["id"],
            "bookId": book_id,
            "number": 1,
            "title": "失落灯塔",
            "status": "running",
            "summary": "领航员发现星港残影。",
            "wordCount": 1200,
            "reviewerNote": "补强悬念。",
            "updatedAt": response.body["chapters"][0]["updatedAt"],
        }
    ]
    assert response.body["latestCanon"]["version"] == 2
    assert response.body["latestCanon"]["content"]["world_rules"][0]["rule"] == "灯塔会记录航线"
    assert response.body["runTraces"][0]["stage"] == "chapter_draft"
    assert response.body["runTraces"][0]["metadata"]["chapter"] == 1
    assert response.body["volumePlans"][0]["title"] == "星港卷"
    assert response.body["volumePlans"][0]["keyTurns"] == ["发现灯塔", "进入星港"]


def test_trusted_state_returns_canon_sections_pending_revision_and_selected_detail(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id = _create_workspace_fixture(db_path)
    revision_id = _add_pending_revision(db_path, book_id)

    response = dispatch_api_get(f"/api/books/{book_id}/state", f"revisionId={revision_id}", db_path)

    assert response.status == HTTPStatus.OK
    assert response.body["book"]["id"] == book_id
    assert response.body["latestCanon"]["content"]["characters"][0]["name"] == "岑星"
    assert response.body["canonSections"][0] == {
        "key": "world_rules",
        "anchor": "world",
        "label": "世界规则",
        "editable": True,
        "locked": False,
        "content": [{"rule": "灯塔会记录航线"}],
    }
    assert response.body["sectionLocks"]["state_history"] is True
    assert response.body["pendingRevisions"][0]["id"] == revision_id
    assert response.body["selectedRevision"]["changedSections"]["characters"][0]["trait"] == "谨慎"
    assert response.body["selectedRevision"]["blockedSections"] == [
        {"section": "world_rules", "reason": "已锁定"}
    ]


def test_trusted_state_ignores_revision_from_another_book(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id = _create_workspace_fixture(db_path)
    other_book_id = _create_workspace_fixture(db_path, title="黑潮地图")
    other_revision_id = _add_pending_revision(db_path, other_book_id)

    response = dispatch_api_get(
        f"/api/books/{book_id}/state",
        f"revisionId={other_revision_id}",
        db_path,
    )

    assert response.status == HTTPStatus.OK
    assert response.body["selectedRevision"] is None


def test_trusted_state_ignores_applied_revision_detail(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id = _create_workspace_fixture(db_path)
    revision_id = _add_pending_revision(db_path, book_id)
    with Session(create_engine_for_path(db_path)) as session:
        revision = get_canon_proposal_revision(session, revision_id)
        assert revision is not None
        revision.status = CanonProposalRevisionStatus.APPLIED
        session.add(revision)
        session.commit()

    response = dispatch_api_get(f"/api/books/{book_id}/state", f"revisionId={revision_id}", db_path)

    assert response.status == HTTPStatus.OK
    assert response.body["selectedRevision"] is None


def test_trusted_state_ignores_stale_revision_detail(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id = _create_workspace_fixture(db_path)
    revision_id = _add_pending_revision(db_path, book_id)
    with Session(create_engine_for_path(db_path)) as session:
        canon = session.exec(select(Canon).where(Canon.book_id == book_id)).first()
        assert canon is not None
        canon.content = {**canon.content, "characters": [{"name": "新版本"}]}
        session.add(canon)
        session.commit()

    response = dispatch_api_get(f"/api/books/{book_id}/state", f"revisionId={revision_id}", db_path)

    assert response.status == HTTPStatus.OK
    assert response.body["selectedRevision"] is None


def test_state_lock_marks_book_canon_locked_and_returns_trusted_state(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id = _create_workspace_fixture(db_path)

    response = dispatch_api_post(f"/api/books/{book_id}/state/lock", {}, db_path)

    assert response.status == HTTPStatus.OK
    assert response.body["book"]["status"] == "canon_locked"
    assert response.body["redirectTo"] == f"/books/{book_id}"
    with Session(create_engine_for_path(db_path)) as session:
        book = get_book(session, book_id)
        assert book is not None
        assert book.status == BookStatus.CANON_LOCKED


def test_canon_proposal_apply_discard_and_revise_routes_map_to_workflow(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id = _create_workspace_fixture(db_path)
    apply_revision_id = _add_pending_revision(db_path, book_id)

    applied = dispatch_api_post(
        f"/api/books/{book_id}/canon-proposals/apply",
        {"revisionId": apply_revision_id},
        db_path,
    )

    assert applied.status == HTTPStatus.OK
    assert applied.body["revision"]["status"] == "applied"
    with Session(create_engine_for_path(db_path)) as session:
        canon = session.exec(select(Canon).where(Canon.book_id == book_id)).first()
        assert canon is not None
        assert canon.content["characters"][0]["trait"] == "谨慎"

    discard_revision_id = _add_pending_revision(db_path, book_id)
    discarded = dispatch_api_post(
        f"/api/books/{book_id}/canon-proposals/discard",
        {"revisionId": discard_revision_id},
        db_path,
    )

    assert discarded.status == HTTPStatus.OK
    assert discarded.body["revision"]["status"] == "discarded"
    with Session(create_engine_for_path(db_path)) as session:
        revision = get_canon_proposal_revision(session, discard_revision_id)
        assert revision is not None
        assert revision.status == CanonProposalRevisionStatus.DISCARDED

    invalid_revise = dispatch_api_post(
        f"/api/books/{book_id}/canon-proposals/revise",
        {"targetSection": "characters", "instruction": "   "},
        db_path,
    )

    assert invalid_revise.status == HTTPStatus.BAD_REQUEST
    assert invalid_revise.body["error"]["code"] == "canon_proposal_action_failed"


def test_canon_proposal_lock_parses_false_string_as_false(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id = _create_workspace_fixture(db_path)

    locked = dispatch_api_post(
        f"/api/books/{book_id}/canon-proposals/lock",
        {"section": "world_rules", "locked": True},
        db_path,
    )
    unlocked = dispatch_api_post(
        f"/api/books/{book_id}/canon-proposals/lock",
        {"section": "world_rules", "locked": "false"},
        db_path,
    )

    assert locked.status == HTTPStatus.OK
    assert locked.body["sectionLocks"]["world_rules"] is True
    assert unlocked.status == HTTPStatus.OK
    assert unlocked.body["sectionLocks"]["world_rules"] is False


def test_canon_proposal_lock_rejects_invalid_locked_value(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    book_id = _create_workspace_fixture(db_path)

    response = dispatch_api_post(
        f"/api/books/{book_id}/canon-proposals/lock",
        {"section": "world_rules", "locked": "not-a-bool"},
        db_path,
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["error"]["code"] == "canon_proposal_action_failed"


def _create_workspace_fixture(db_path: Path, title: str = "星港遗梦") -> int:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = add_book(
            session,
            Book(
                title=title,
                genre="科幻",
                audience="成人",
                premise="领航员追查失落星港的真相。",
            ),
        )
        book_id = book.id or 0
        add_canon(
            session,
            Canon(
                book_id=book_id,
                version=2,
                content={
                    "world_rules": [{"rule": "灯塔会记录航线"}],
                    "characters": [{"name": "岑星"}],
                    "state_history": [],
                },
            ),
        )
        add_chapter(
            session,
            Chapter(
                book_id=book_id,
                number=1,
                title="失落灯塔",
                status=ChapterStatus.RUNNING,
                summary="领航员发现星港残影。",
                reviewer_note="补强悬念。",
                word_count=1200,
            ),
        )
        add_run_trace(
            session,
            RunTrace(
                book_id=book_id,
                stage="chapter_draft",
                prompt_id="chapter_draft",
                prompt_version="1",
                model="gpt-test",
                cost={"tokens": 1200},
                metadata_={"chapter": 1},
            ),
        )
        add_volume_plan(
            session,
            VolumePlan(
                book_id=book_id,
                volume_number=1,
                title="星港卷",
                core_conflict="寻找失落星港。",
                pacing_curve=["悬疑", "突破"],
                payoff_distribution=["灯塔真相"],
                key_turns=["发现灯塔", "进入星港"],
                commitments=["不背离星港谜题"],
            ),
        )
        return book_id


def _add_pending_revision(db_path: Path, book_id: int) -> int:
    engine = create_engine_for_path(db_path)
    with Session(engine) as session:
        book = get_book(session, book_id)
        canon = session.exec(select(Canon).where(Canon.book_id == book_id)).first()
        assert book is not None
        assert canon is not None
        revision = add_canon_proposal_revision(
            session,
            CanonProposalRevision(
                book_id=book_id,
                base_canon_version=canon.version,
                base_content_hash=content_hash(canon.content),
                base_locks_hash=locks_hash(section_locks_for_book(book)),
                target_section="characters",
                instruction="让主角更谨慎",
                allowed_sections=["characters"],
                locked_sections=["world_rules"],
                changed_sections={"characters": [{"name": "岑星", "trait": "谨慎"}]},
                blocked_sections=[{"section": "world_rules", "reason": "已锁定"}],
                summary="补强人物风险意识。",
            ),
        )
        return revision.id or 0
