# Canon Proposal AI Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `可信设定提案 · 待确认` page inspectable and AI-revisable, with reversible section locks, server-side revision previews, and safe application before global canon lock.

**Architecture:** Keep canon proposal business logic in a focused workflow module, keep HTTP handlers out of `dev_server.py` to avoid crossing 1000 lines, and move the expanded page UI into a dedicated view module. `Canon.content` remains proposal/trusted-state content only; proposal metadata lives in `Book.constraints`, and pending AI revision payloads live in a new `CanonProposalRevision` table.

**Tech Stack:** Python, SQLModel, SQLite, pixi, pytest, OpenAI-compatible chat API, existing prompt registry and HTML string-rendered product UI.

---

## Scope Check

This is one subsystem: open-book canon proposal review before global lock. It touches domain persistence, workflow validation, dev-server routes, and UI rendering, but all changes support the same user journey and can be tested together.

Do not implement post-lock canon editing or proposal version trees. Those remain future work from the spec.

## Target File Structure

- Create: `src/mynovel/workflows/canon_proposal.py`  
  Section registry, proposal lock metadata, content hashing, AI revision preview creation, apply/discard/stale transitions, and lock-finalization cleanup.
- Create: `src/mynovel/canon_proposal_views.py`  
  Canon gate section cards, full section details, lock controls, AI revision form, and revision preview markup.
- Create: `src/mynovel/canon_proposal_server.py`  
  POST handlers for section lock toggles, AI revision generation, apply, and discard. Return response objects so `dev_server.py` stays small.
- Create: `src/mynovel/prompts/assets/canon_proposal_revision.yaml`  
  Traceable prompt asset for AI proposal revisions.
- Modify: `src/mynovel/domain/models.py`  
  Add `CanonProposalRevisionStatus` and `CanonProposalRevision`.
- Modify: `src/mynovel/domain/repositories.py`  
  Add repository helpers for proposal revisions.
- Modify: `src/mynovel/db.py`  
  Ensure existing SQLite databases create the new table. Add explicit migration guard only if tests reveal `create_all` is insufficient.
- Modify: `src/mynovel/workflows/open_book.py`  
  Add `factions` default in initial canon and call proposal-finalization cleanup when locking.
- Modify: `src/mynovel/product_components.py`  
  Replace canon gate rendering internals with calls into `canon_proposal_views.py`; keep public function names stable.
- Modify: `src/mynovel/product_views.py`  
  Thread optional `CanonProposalRevision` into `render_trusted_state_page`.
- Modify: `src/mynovel/dev_server.py`  
  Add minimal route dispatch only; delegate request bodies to `canon_proposal_server.py`.
- Modify: `tests/workflows/test_open_book.py`  
  Cover global lock cleanup and initial `factions`.
- Create: `tests/workflows/test_canon_proposal.py`  
  Core workflow tests for locks, revision preview, apply, stale, and atomic rejection.
- Modify: `tests/test_dev_server.py`  
  HTTP handler route tests for new POST actions.
- Modify: `tests/test_product_ui.py`  
  UI tests for clickable sections, locks, AI form, and preview.
- Modify: `tests/prompts/test_registry.py`  
  Prompt asset metadata test.

Keep each touched file below 1000 lines. If `product_components.py`, `product_views.py`, or `dev_server.py` approaches the limit, move more code into the new focused modules instead of appending.

## Task 1: Domain Model, Repository, and Prompt Asset

**Files:**
- Modify: `src/mynovel/domain/models.py`
- Modify: `src/mynovel/domain/repositories.py`
- Modify: `src/mynovel/db.py`
- Create: `src/mynovel/prompts/assets/canon_proposal_revision.yaml`
- Modify: `tests/prompts/test_registry.py`
- Create: `tests/workflows/test_canon_proposal.py`

- [ ] **Step 1: Write failing model and repository tests**

Create the first tests in `tests/workflows/test_canon_proposal.py`:

```python
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

    assert loaded is not None
    assert loaded.status == CanonProposalRevisionStatus.PENDING
    assert loaded.changed_sections["characters"][0]["name"] == "林烬"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pixi run pytest tests/workflows/test_canon_proposal.py::test_canon_proposal_revision_persists_structured_preview -v`  
Expected: FAIL with import errors for `CanonProposalRevision` or repository helpers.

- [ ] **Step 3: Implement the model**

Add to `src/mynovel/domain/models.py`:

```python
class CanonProposalRevisionStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    DISCARDED = "discarded"
    STALE = "stale"


class CanonProposalRevision(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(index=True, foreign_key="book.id")
    base_canon_version: int
    base_content_hash: str
    base_locks_hash: str
    target_section: str
    instruction: str
    allowed_sections: list = Field(default_factory=list, sa_column=Column(JSON))
    locked_sections: list = Field(default_factory=list, sa_column=Column(JSON))
    changed_sections: dict = Field(default_factory=dict, sa_column=Column(JSON))
    blocked_sections: list = Field(default_factory=list, sa_column=Column(JSON))
    summary: str = ""
    risks: list = Field(default_factory=list, sa_column=Column(JSON))
    status: CanonProposalRevisionStatus = CanonProposalRevisionStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)
    applied_at: datetime | None = None
```

- [ ] **Step 4: Implement repository helpers**

Add to `src/mynovel/domain/repositories.py`:

```python
def add_canon_proposal_revision(
    session: Session,
    revision: CanonProposalRevision,
) -> CanonProposalRevision:
    session.add(revision)
    session.commit()
    session.refresh(revision)
    return revision


def get_canon_proposal_revision(
    session: Session,
    revision_id: int,
) -> CanonProposalRevision | None:
    return session.get(CanonProposalRevision, revision_id)


def list_pending_canon_proposal_revisions_for_book(
    session: Session,
    book_id: int,
) -> list[CanonProposalRevision]:
    statement = (
        select(CanonProposalRevision)
        .where(CanonProposalRevision.book_id == book_id)
        .where(CanonProposalRevision.status == CanonProposalRevisionStatus.PENDING)
        .order_by(_orm(CanonProposalRevision.created_at), _orm(CanonProposalRevision.id))
    )
    return list(session.exec(statement))
```

Add imports for `CanonProposalRevision` and `CanonProposalRevisionStatus`.

- [ ] **Step 5: Run the model/repository test**

Run: `pixi run pytest tests/workflows/test_canon_proposal.py::test_canon_proposal_revision_persists_structured_preview -v`  
Expected: PASS.

- [ ] **Step 6: Write failing prompt asset test**

Append to `tests/prompts/test_registry.py`:

```python
def test_canon_proposal_revision_prompt_declares_json_contract() -> None:
    asset = load_prompt_by_id("canon_proposal_revision")

    assert asset.id == "canon_proposal_revision"
    assert asset.source_license == "Apache-2.0"
    assert "changed_sections" in asset.output_schema["required"]
    assert "blocked_sections" in asset.output_schema["required"]
```

- [ ] **Step 7: Run the prompt test to verify it fails**

Run: `pixi run pytest tests/prompts/test_registry.py::test_canon_proposal_revision_prompt_declares_json_contract -v`  
Expected: FAIL with `FileNotFoundError`.

- [ ] **Step 8: Add the prompt asset**

Create `src/mynovel/prompts/assets/canon_proposal_revision.yaml`:

```yaml
id: canon_proposal_revision
name: Canon Proposal AI Revision
version: "0.1.0"
purpose: Revise unlocked canon proposal sections from short author instructions.
source: original
source_license: Apache-2.0
adaptation_notes: Designed for MyNovel open-book proposal review with reversible section locks.
model_family_hint: OpenAI-compatible chat models with JSON response-format support.
input_schema:
  required:
    - trusted_state_proposal
    - target_section
    - instruction
    - section_locks
    - allowed_sections
    - locked_sections
output_schema:
  required:
    - target_section
    - changed_sections
    - blocked_sections
    - summary
    - risks
template: |
  Revise the trusted-state proposal using the author's instruction.
  You may replace only sections listed in allowed_sections. Sections listed in
  locked_sections are immutable constraints and must not appear in changed_sections.
  changed_sections must contain complete replacement arrays for every changed
  section, not patches. Return JSON only.
```

- [ ] **Step 9: Run task tests**

Run: `pixi run pytest tests/workflows/test_canon_proposal.py tests/prompts/test_registry.py -v`  
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add src/mynovel/domain/models.py src/mynovel/domain/repositories.py src/mynovel/db.py src/mynovel/prompts/assets/canon_proposal_revision.yaml tests/workflows/test_canon_proposal.py tests/prompts/test_registry.py
git commit -m "feat: add canon proposal revision persistence"
```

## Task 2: Core Canon Proposal Workflow

**Files:**
- Create: `src/mynovel/workflows/canon_proposal.py`
- Modify: `src/mynovel/workflows/open_book.py`
- Modify: `tests/workflows/test_canon_proposal.py`
- Modify: `tests/workflows/test_open_book.py`

- [ ] **Step 1: Write failing section registry and lock tests**

Append to `tests/workflows/test_canon_proposal.py`:

```python
from mynovel.domain.models import Book, BookStatus, Canon
from mynovel.domain.repositories import add_book, add_canon, get_book
from mynovel.workflows.canon_proposal import (
    CANON_PROPOSAL_KEY,
    section_locks_for_book,
    set_canon_proposal_section_lock,
)


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
```

- [ ] **Step 2: Run lock tests to verify they fail**

Run: `pixi run pytest tests/workflows/test_canon_proposal.py::test_section_locks_default_to_unlocked_for_editable_sections tests/workflows/test_canon_proposal.py::test_draft_book_can_toggle_section_lock -v`  
Expected: FAIL with missing `mynovel.workflows.canon_proposal`.

- [ ] **Step 3: Implement section registry and locks**

Create `src/mynovel/workflows/canon_proposal.py` with:

```python
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from sqlmodel import Session

from mynovel.domain.models import (
    Book,
    BookStatus,
    Canon,
    CanonProposalRevision,
    CanonProposalRevisionStatus,
    utc_now,
)
from mynovel.domain.repositories import (
    add_canon_proposal_revision,
    get_book,
    get_canon_proposal_revision,
    get_latest_canon,
    list_pending_canon_proposal_revisions_for_book,
)

CANON_PROPOSAL_KEY = "_canon_proposal"


@dataclass(frozen=True)
class CanonProposalSection:
    key: str
    anchor: str
    label: str
    editable: bool = True


SECTION_REGISTRY = {
    "world_rules": CanonProposalSection("world_rules", "world", "世界规则"),
    "characters": CanonProposalSection("characters", "characters", "人物"),
    "factions": CanonProposalSection("factions", "factions", "势力"),
    "locations": CanonProposalSection("locations", "locations", "地点"),
    "relationships": CanonProposalSection("relationships", "relationships", "关系"),
    "foreshadowing": CanonProposalSection("foreshadowing", "foreshadowing", "伏笔账本"),
    "chapter_summaries": CanonProposalSection("chapter_summaries", "chapter-summaries", "章节摘要"),
    "state_history": CanonProposalSection("state_history", "state-history", "变化历史", False),
}


def section_locks_for_book(book: Book) -> dict[str, bool]:
    proposal = book.constraints.get(CANON_PROPOSAL_KEY, {})
    raw_locks = proposal.get("section_locks", {}) if isinstance(proposal, dict) else {}
    return {
        key: bool(raw_locks.get(key, not section.editable))
        for key, section in SECTION_REGISTRY.items()
    }
```

Continue the implementation with `set_canon_proposal_section_lock`, `_editable_section`, `content_hash`, and `locks_hash`.

- [ ] **Step 4: Run lock tests**

Run: `pixi run pytest tests/workflows/test_canon_proposal.py::test_section_locks_default_to_unlocked_for_editable_sections tests/workflows/test_canon_proposal.py::test_draft_book_can_toggle_section_lock -v`  
Expected: PASS.

- [ ] **Step 5: Write failing AI preview creation test**

Append:

```python
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
```

- [ ] **Step 6: Run preview test to verify it fails**

Run: `pixi run pytest tests/workflows/test_canon_proposal.py::test_create_revision_preview_persists_ai_output_with_base_hashes -v`  
Expected: FAIL with missing `create_canon_proposal_revision`.

- [ ] **Step 7: Implement AI preview creation**

In `src/mynovel/workflows/canon_proposal.py`, add:

```python
class CanonProposalModelClient(Protocol):
    def complete(self, stage: str, messages: list[dict[str, str]], response_format: str) -> str:
        pass
```

Implement `create_canon_proposal_revision` using `load_prompt_by_id("canon_proposal_revision")`, `render_prompt_messages`, JSON parsing, `changed_sections` whitelist validation, array-only section validation, and repository persistence. Raise `ValueError` for missing book/canon, non-`DRAFT` book, locked target section, unknown sections, invalid JSON, or locked section changes.

- [ ] **Step 8: Run preview test**

Run: `pixi run pytest tests/workflows/test_canon_proposal.py::test_create_revision_preview_persists_ai_output_with_base_hashes -v`  
Expected: PASS.

- [ ] **Step 9: Write failing apply and stale tests**

Add imports near the top of `tests/workflows/test_canon_proposal.py`:

```python
import pytest

from mynovel.workflows.canon_proposal import (
    apply_canon_proposal_revision,
    content_hash,
    locks_hash,
)
```

Append focused tests:

```python
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
```

Use real objects and avoid mocks except the fake model client.

- [ ] **Step 10: Run apply/stale tests to verify they fail**

Run: `pixi run pytest tests/workflows/test_canon_proposal.py -v`  
Expected: FAIL with missing `apply_canon_proposal_revision` and stale helpers.

- [ ] **Step 11: Implement apply/discard/stale helpers**

Add:

```python
def apply_canon_proposal_revision(
    session: Session,
    book_id: int,
    revision_id: int,
) -> CanonProposalRevision:
    ...
```

Required behavior:
- book must still be `DRAFT`.
- revision must exist, belong to book, and be `PENDING`.
- current canon version/content hash and locks hash must match base hashes.
- `changed_sections` keys must be editable, currently unlocked, and known.
- `state_history` from AI is always rejected.
- replace entire changed section arrays.
- append system `state_history` entry with target section, changed sections, blocked sections, summary, risks, and timestamp.
- update `Book.constraints[CANON_PROPOSAL_KEY]["last_revision"]` with target section, instruction, changed sections, blocked sections, summary, risks, and timestamp.
- mark revision `APPLIED` with `applied_at`.
- commit atomically.

Also add `discard_canon_proposal_revision` and `mark_pending_canon_proposal_revisions_stale`.

- [ ] **Step 12: Run workflow tests**

Run: `pixi run pytest tests/workflows/test_canon_proposal.py -v`  
Expected: PASS.

- [ ] **Step 13: Write failing open-book lock cleanup tests**

Append to `tests/workflows/test_open_book.py`:

```python
def test_lock_canon_foundation_marks_pending_proposal_revisions_stale(tmp_path: Path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    blueprint = OpenBookBlueprint(
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={"title_options": ["长夜图书馆"], "genre": "玄幻", "audience": "男频网文读者"},
        raw_response="{}",
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(
            session,
            blueprint,
            selected_title="长夜图书馆",
            lock_foundation=False,
        )
        canon = get_latest_canon(session, book.id or 0)
        assert canon is not None
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
        book.constraints[CANON_PROPOSAL_KEY] = {
            "section_locks": {"characters": False},
            "last_revision": {"summary": "草稿摘要"},
        }
        canon.content["_canon_proposal"] = {"should": "not survive"}
        canon.content["unknown_internal"] = ["not trusted state"]
        session.add(book)
        session.add(canon)
        session.commit()

        locked = lock_canon_foundation(session, book.id)
        stale_revision = get_canon_proposal_revision(session, revision.id or 0)
        locked_canon = get_latest_canon(session, book.id or 0)

    assert locked.status.value == "canon_locked"
    assert CANON_PROPOSAL_KEY not in locked.constraints
    assert stale_revision is not None
    assert stale_revision.status == CanonProposalRevisionStatus.STALE
    assert locked_canon is not None
    assert "_canon_proposal" not in locked_canon.content
    assert "unknown_internal" not in locked_canon.content
    assert locked_canon.content["factions"] == []
    assert locked_canon.content["state_history"] == []


def test_create_draft_book_from_blueprint_initializes_factions_section(tmp_path: Path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    blueprint = OpenBookBlueprint(
        idea="失意档案员重建禁书馆",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={"title_options": ["长夜图书馆"], "genre": "玄幻", "audience": "男频网文读者"},
        raw_response="{}",
    )

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(
            session,
            blueprint,
            selected_title="长夜图书馆",
            lock_foundation=False,
        )
        canon = get_latest_canon(session, book.id or 0)

    assert canon is not None
    assert canon.content["factions"] == []
```

Add imports for `CanonProposalRevision`, `CanonProposalRevisionStatus`, `add_canon_proposal_revision`, `get_canon_proposal_revision`, and `CANON_PROPOSAL_KEY`, `content_hash`, `locks_hash`, `section_locks_for_book`.

- [ ] **Step 14: Run open-book tests to verify they fail**

Run: `pixi run pytest tests/workflows/test_open_book.py::test_lock_canon_foundation_marks_pending_proposal_revisions_stale tests/workflows/test_open_book.py::test_create_draft_book_from_blueprint_initializes_factions_section -v`  
Expected: FAIL before integration.

- [ ] **Step 15: Integrate with `lock_canon_foundation`**

Modify `src/mynovel/workflows/open_book.py`:
- Add `"factions": []` in `_initial_canon_content`.
- Before setting `book.status = BookStatus.CANON_LOCKED`, call a helper from `canon_proposal.py` that:
  - normalizes known canon sections,
  - removes `Book.constraints[CANON_PROPOSAL_KEY]`,
  - marks pending revisions stale.

- [ ] **Step 16: Run task tests**

Run: `pixi run pytest tests/workflows/test_canon_proposal.py tests/workflows/test_open_book.py -v`  
Expected: PASS.

- [ ] **Step 17: Commit**

```bash
git add src/mynovel/workflows/canon_proposal.py src/mynovel/workflows/open_book.py tests/workflows/test_canon_proposal.py tests/workflows/test_open_book.py
git commit -m "feat: add canon proposal AI revision workflow"
```

## Task 3: Dev Server Routes Without Growing `dev_server.py`

**Files:**
- Create: `src/mynovel/canon_proposal_server.py`
- Modify: `src/mynovel/dev_server.py`
- Modify: `tests/test_dev_server.py`

- [ ] **Step 0: Check `dev_server.py` line budget before editing**

Run: `wc -l src/mynovel/dev_server.py`  
Expected: about 985 lines. Because the file is already close to the 1000-line limit, do not add four separate route branches and a local helper. Use one dispatch function from `canon_proposal_server.py`, and if the file still crosses 1000 lines, extract an existing export/send helper from `dev_server.py` before committing.

- [ ] **Step 1: Write failing server handler tests**

Add tests to `tests/test_dev_server.py` that exercise pure handler functions first:

```python
from mynovel.canon_proposal_server import (
    handle_toggle_canon_proposal_section_lock,
    is_canon_proposal_post_path,
    load_pending_canon_proposal_revision_for_book,
)
from mynovel.domain.models import Canon, CanonProposalRevision, CanonProposalRevisionStatus


def test_toggle_section_lock_handler_redirects_to_section_anchor(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = Book(title="长夜图书馆", genre="奇幻", audience="连载读者")
        session.add(book)
        session.commit()
        session.refresh(book)
        session.add(Canon(book_id=book.id or 0, version=1, content={"world_rules": []}))
        session.commit()

    response = handle_toggle_canon_proposal_section_lock(
        {"book_id": str(book.id or 0), "section": "world_rules", "locked": "1"},
        db_path,
    )

    assert response.redirect_to == f"/book/{book.id}/state#world"


def test_state_page_revision_loader_returns_pending_revision_for_same_book(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = Book(title="长夜图书馆", genre="奇幻", audience="连载读者")
        session.add(book)
        session.commit()
        session.refresh(book)
        revision = CanonProposalRevision(
            book_id=book.id or 0,
            base_canon_version=1,
            base_content_hash="content",
            base_locks_hash="locks",
            target_section="characters",
            instruction="主角改成外冷内热",
            changed_sections={"characters": [{"name": "林烬"}]},
        )
        session.add(revision)
        session.commit()
        session.refresh(revision)

    revision = load_pending_canon_proposal_revision_for_book(
        db_path,
        book_id=book.id or 0,
        revision_id=revision.id or 0,
    )

    assert revision is not None
    assert revision.target_section == "characters"


def test_state_page_revision_loader_ignores_cross_book_or_non_pending_revision(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "test.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = Book(title="长夜图书馆", genre="奇幻", audience="连载读者")
        other_book = Book(title="别的书", genre="奇幻", audience="连载读者")
        session.add(book)
        session.add(other_book)
        session.commit()
        session.refresh(book)
        session.refresh(other_book)
        cross_book_revision = CanonProposalRevision(
            book_id=other_book.id or 0,
            base_canon_version=1,
            base_content_hash="content",
            base_locks_hash="locks",
            target_section="characters",
            instruction="主角改成外冷内热",
            changed_sections={"characters": [{"name": "林烬"}]},
        )
        applied_revision = CanonProposalRevision(
            book_id=book.id or 0,
            base_canon_version=1,
            base_content_hash="content",
            base_locks_hash="locks",
            target_section="characters",
            instruction="主角改成外冷内热",
            changed_sections={"characters": [{"name": "林烬"}]},
            status=CanonProposalRevisionStatus.APPLIED,
        )
        session.add(cross_book_revision)
        session.add(applied_revision)
        session.commit()
        session.refresh(cross_book_revision)
        session.refresh(applied_revision)

    cross_book = load_pending_canon_proposal_revision_for_book(
        db_path,
        book_id=book.id or 0,
        revision_id=cross_book_revision.id or 0,
    )
    non_pending = load_pending_canon_proposal_revision_for_book(
        db_path,
        book_id=book.id or 0,
        revision_id=applied_revision.id or 0,
    )

    assert cross_book is None
    assert non_pending is None


def test_canon_proposal_post_path_guard_only_matches_proposal_routes() -> None:
    assert is_canon_proposal_post_path("/canon-proposal-lock")
    assert is_canon_proposal_post_path("/canon-proposal-revise")
    assert not is_canon_proposal_post_path("/open-book")
    assert not is_canon_proposal_post_path("/books/import")
```

Also add tests for invalid section returning `HTTPStatus.BAD_REQUEST` and locked book rejecting changes.

- [ ] **Step 2: Run handler tests to verify they fail**

Run: `pixi run pytest tests/test_dev_server.py::test_toggle_section_lock_handler_redirects_to_section_anchor -v`  
Expected: FAIL with missing module.

- [ ] **Step 3: Implement `canon_proposal_server.py` response type and lock handler**

Create:

```python
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from collections.abc import Mapping


@dataclass(frozen=True)
class CanonProposalServerResponse:
    body: str = ""
    status: HTTPStatus = HTTPStatus.OK
    redirect_to: str | None = None
```

Implement `handle_toggle_canon_proposal_section_lock(form, db_path)` with `create_engine_for_path`, `Session`, and `set_canon_proposal_section_lock`.

- [ ] **Step 4: Run lock handler tests**

Run: `pixi run pytest tests/test_dev_server.py::test_toggle_section_lock_handler_redirects_to_section_anchor -v`  
Expected: PASS.

- [ ] **Step 5: Write failing revision/apply/discard handler tests**

Add tests for:
- `handle_create_canon_proposal_revision` creates pending revision and redirects to `/book/{id}/state?revision_id={revision.id}#characters`.
- invalid/missing provider config returns BAD_REQUEST.
- `handle_apply_canon_proposal_revision` applies pending revision and redirects to the target anchor.
- `handle_discard_canon_proposal_revision` marks revision discarded and redirects.
- `load_pending_canon_proposal_revision_for_book` returns `None` for unknown, cross-book, stale, discarded, or applied revisions.

Use a fake model client injection parameter on the handler to avoid network.

- [ ] **Step 6: Run new handler tests to verify they fail**

Run: `pixi run pytest tests/test_dev_server.py -k canon_proposal -v`  
Expected: FAIL for missing handlers.

- [ ] **Step 7: Implement create/apply/discard handlers**

Implement in `src/mynovel/canon_proposal_server.py`:
- `handle_create_canon_proposal_revision(form, db_path, model_client=None)`
- `handle_apply_canon_proposal_revision(form, db_path)`
- `handle_discard_canon_proposal_revision(form, db_path)`
- `load_pending_canon_proposal_revision_for_book(db_path, book_id, revision_id)`
- `dispatch_canon_proposal_post(path, form, db_path)`
- `is_canon_proposal_post_path(path)`
- `OpenAICanonProposalModelClient` wrapper using `OpenAICompatibleClient` and `ChatRequest`.

If `model_client` is `None`, build it from provider config in the server handler path. Keep network code outside tests through injection.

- [ ] **Step 8: Wire minimal routes in `dev_server.py`**

Add only three imports:

```python
from mynovel.canon_proposal_server import (
    dispatch_canon_proposal_post,
    is_canon_proposal_post_path,
    load_pending_canon_proposal_revision_for_book,
)
```

Add one small gated POST dispatch block near the top of `do_POST`. Do not call `_read_form()` unless the path is known to belong to the canon proposal feature, because `_read_form()` consumes `rfile`:

```python
if is_canon_proposal_post_path(parsed.path):
    proposal_response = dispatch_canon_proposal_post(parsed.path, self._read_form(), state.db_path)
    if proposal_response.redirect_to:
        self._redirect(proposal_response.redirect_to)
    else:
        self._send_html(proposal_response.body, proposal_response.status)
    return
```

`dispatch_canon_proposal_post` handles:
- `/canon-proposal-lock`
- `/canon-proposal-revise`
- `/canon-proposal-apply`
- `/canon-proposal-discard`

Add `is_canon_proposal_post_path(path)` in `canon_proposal_server.py` and test that non-proposal paths return `False`.

Update GET state rendering:
- Parse `revision_id` from `/book/{id}/state?revision_id=...`.
- Pass it into `_send_trusted_state_page`.
- Load with `load_pending_canon_proposal_revision_for_book`.
- Pass the result to `render_trusted_state_page(..., proposal_revision=revision)`.
- Unknown, cross-book, stale, discarded, or applied revisions should be ignored, not rendered.

- [ ] **Step 9: Run server tests and line count**

Run: `pixi run pytest tests/test_dev_server.py -v`  
Expected: PASS.

Run: `wc -l src/mynovel/dev_server.py`  
Expected: less than or equal to 1000. If above 1000, move more helper code from `dev_server.py` into `canon_proposal_server.py`.

- [ ] **Step 10: Commit**

```bash
git add src/mynovel/canon_proposal_server.py src/mynovel/dev_server.py tests/test_dev_server.py
git commit -m "feat: wire canon proposal revision routes"
```

## Task 4: Canon Proposal UI

**Files:**
- Create: `src/mynovel/canon_proposal_views.py`
- Modify: `src/mynovel/product_components.py`
- Modify: `src/mynovel/product_views.py`
- Modify: `tests/test_product_ui.py`

- [ ] **Step 1: Write failing UI tests for clickable sections and locks**

Add to `tests/test_product_ui.py`:

```python
def test_trusted_state_page_renders_clickable_canon_sections_with_locks() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="连载读者",
        status=BookStatus.DRAFT,
        constraints={
            "_canon_proposal": {
                "last_revision": {
                    "target_section": "characters",
                    "summary": "已调整人物和关系。",
                }
            }
        },
    )
    canon = Canon(
        id=1,
        book_id=1,
        version=1,
        content={
            "world_rules": [{"name": "雾墙规则", "detail": "幽谷边界危险"}],
            "characters": [{"name": "林烬", "trait": "外冷内热"}],
            "factions": [],
        },
    )

    page = render_trusted_state_page(book, canon, [])

    assert 'href="#world"' in page
    assert 'id="world"' in page
    assert 'action="/canon-proposal-lock"' in page
    assert 'name="section" value="world_rules"' in page
    assert "让 AI 修改这部分" in page
    assert "最近一次 AI 修订" in page
    assert "已调整人物和关系" in page
```

- [ ] **Step 2: Run UI test to verify it fails**

Run: `pixi run pytest tests/test_product_ui.py::test_trusted_state_page_renders_clickable_canon_sections_with_locks -v`  
Expected: FAIL because cards are static or forms are missing.

- [ ] **Step 3: Implement `canon_proposal_views.py` section rendering**

Create focused render helpers:

```python
def render_canon_proposal_surface(
    book: Book,
    canon: Canon | None,
    locked: bool,
    revision: CanonProposalRevision | None = None,
) -> str:
    ...
```

Include helpers for:
- summary cards as `<a class="canon-summary-card" href="#{anchor}">`.
- lock/unlock forms for draft books.
- full section detail list with Chinese labels.
- AI revision form for unlocked draft sections.
- locked-state hint for locked sections.
- latest revision summary from `Book.constraints["_canon_proposal"]["last_revision"]`.
- hide all revision forms when global locked.

Escape all user/AI content with `html.escape`.

- [ ] **Step 4: Modify `product_components.py` minimally**

Keep `render_canon_gate_main(canon, locked=False)` callable for older tests by delegating to new helper with a synthetic context, or update callers to pass `book`. Prefer updating `product_views.render_trusted_state_page` to call the new helper directly so `product_components.py` does not grow too much.

- [ ] **Step 5: Run clickable/locks UI test**

Run: `pixi run pytest tests/test_product_ui.py::test_trusted_state_page_renders_clickable_canon_sections_with_locks -v`  
Expected: PASS.

- [ ] **Step 6: Write failing preview UI test**

Add:

```python
def test_trusted_state_page_renders_ai_revision_preview_actions() -> None:
    book = Book(id=1, title="长夜图书馆", genre="奇幻", audience="连载读者", status=BookStatus.DRAFT)
    canon = Canon(id=1, book_id=1, version=1, content={"characters": []})
    revision = CanonProposalRevision(
        id=9,
        book_id=1,
        base_canon_version=1,
        base_content_hash="content",
        base_locks_hash="locks",
        target_section="characters",
        instruction="主角改成外冷内热",
        allowed_sections=["characters"],
        locked_sections=["world_rules"],
        changed_sections={"characters": [{"name": "林烬"}]},
        blocked_sections=[{"section": "world_rules", "reason": "已锁定"}],
        summary="已调整人物。",
        risks=["需要同步章节动机。"],
    )

    page = render_trusted_state_page(book, canon, [], proposal_revision=revision)

    assert "修订预览" in page
    assert 'action="/canon-proposal-apply"' in page
    assert 'name="revision_id" value="9"' in page
    assert "世界规则" in page
    assert "已锁定" in page
```

- [ ] **Step 7: Run preview UI test to verify it fails**

Run: `pixi run pytest tests/test_product_ui.py::test_trusted_state_page_renders_ai_revision_preview_actions -v`  
Expected: FAIL until preview rendering is added.

- [ ] **Step 8: Implement preview rendering**

In `canon_proposal_views.py`, render:
- changed section labels and replacement content.
- blocked section labels and reasons.
- risks.
- apply/discard forms.
- a regenerate form preserving target section and instruction.

Use registry labels in visible preview copy. Hidden form values may contain canonical section keys, so tests should not assert that raw keys are absent from the entire page.

- [ ] **Step 9: Thread optional revision through page rendering**

Modify `src/mynovel/product_views.py`:

```python
def render_trusted_state_page(
    book: Book,
    canon: Canon | None,
    chapters: list[Chapter],
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
    proposal_revision: CanonProposalRevision | None = None,
) -> str:
    ...
```

Ensure existing callers still work.

- [ ] **Step 10: Run UI tests and line counts**

Run: `pixi run pytest tests/test_product_ui.py -v`  
Expected: PASS.

Run: `wc -l src/mynovel/product_components.py src/mynovel/product_views.py src/mynovel/canon_proposal_views.py`  
Expected: each file is less than or equal to 1000 lines.

- [ ] **Step 11: Commit**

```bash
git add src/mynovel/canon_proposal_views.py src/mynovel/product_components.py src/mynovel/product_views.py tests/test_product_ui.py
git commit -m "feat: render AI-revisable canon proposal UI"
```

## Task 5: End-to-End Regression and Cleanup

**Files:**
- Modify as needed only in files touched by Tasks 1-4.
- Modify: `tests/workflows/test_canon_proposal.py`
- Modify: `src/mynovel/workflows/book_export.py`
- Modify: `src/mynovel/workflows/book_import.py`
- Modify: `tests/workflows/test_book_export.py`
- Modify: `tests/workflows/test_book_import.py`
- Modify: `tests/workflows/test_chapter_pipeline.py`
- Modify: `tests/test_dev_server.py`
- Modify: `tests/test_product_ui.py`

- [ ] **Step 1: Add final security regression tests**

Add or confirm these concrete regression tests.

In `tests/workflows/test_canon_proposal.py`:

```python
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
```

These may reuse helpers introduced in Task 2, but they must be real pytest code with persisted rows and assertions.

In `tests/workflows/test_book_export.py`:

```python
def test_export_book_json_does_not_include_canon_proposal_metadata(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        book.constraints["_canon_proposal"] = {
            "section_locks": {"characters": True},
            "last_revision": {"summary": "草稿修订"},
        }
        session.add(book)
        session.commit()
        canon = get_latest_canon(session, book.id or 0)
        assert canon is not None
        canon.content["_canon_proposal"] = {"should": "not export"}
        session.add(canon)
        session.add(
            CanonProposalRevision(
                book_id=book.id or 0,
                base_canon_version=canon.version,
                base_content_hash="content",
                base_locks_hash="locks",
                target_section="characters",
                instruction="主角改成外冷内热",
                changed_sections={"characters": [{"name": "DO_NOT_EXPORT_PREVIEW"}]},
                summary="DO_NOT_EXPORT_REVISION",
            )
        )
        session.commit()

        payload_text = export_book_json(book, canon, list_chapters_for_book(session, book.id or 0))
        payload = json.loads(payload_text)

    assert "_canon_proposal" not in payload_text
    assert "last_revision" not in payload_text
    assert "DO_NOT_EXPORT_PREVIEW" not in payload_text
    assert "DO_NOT_EXPORT_REVISION" not in payload_text
    assert payload["trusted_state"]["content"].get("characters") is not None
```

Add `CanonProposalRevision` to the model imports in this file.

In `tests/workflows/test_book_import.py`:

```python
def test_import_book_json_strips_canon_proposal_metadata(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "dev.sqlite")
    create_db_and_tables(engine)
    payload = {
        "book": {"title": "雾港书局", "genre": "奇幻", "audience": "连载读者"},
        "trusted_state": {
            "version": 1,
            "content": {
                "world_rules": [{"name": "石语魔法"}],
                "_canon_proposal": {"section_locks": {"world_rules": True}},
                "canon_proposal_revisions": [{"changed_sections": {"characters": []}}],
            },
        },
    }

    with Session(engine) as session:
        book = import_book_json(session, json.dumps(payload, ensure_ascii=False))
        canon = get_latest_canon(session, book.id or 0)

    assert "_canon_proposal" not in book.constraints
    assert canon is not None
    assert "_canon_proposal" not in canon.content
    assert "canon_proposal_revisions" not in canon.content
```

In `tests/workflows/test_chapter_pipeline.py`:

```python
def test_chapter_context_package_excludes_canon_proposal_metadata(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book_from_blueprint(
            session,
            _blueprint(),
            selected_title="长夜图书馆",
            lock_foundation=False,
        )
        book.constraints["_canon_proposal"] = {"last_revision": {"summary": "草稿"}}
        session.add(book)
        canon = get_latest_canon(session, book.id or 0)
        assert canon is not None
        canon.content["_canon_proposal"] = {"should": "not enter context"}
        session.add(canon)
        session.commit()
        lock_canon_foundation(session, book.id)
        chapter = list_chapters_for_book(session, book.id or 0)[0]

        reviewed = run_chapter_pipeline(session, chapter.id)

    context_text = str(reviewed.context_package)
    assert "_canon_proposal" not in context_text
    assert "last_revision" not in context_text
```

Also verify the Task 2 open-book tests cover global lock normalization and missing registry-section defaults.

- [ ] **Step 1.5: Implement export/import metadata sanitization if regression tests fail**

If the export/import regression tests fail, update:

- `src/mynovel/workflows/book_export.py`
- `src/mynovel/workflows/book_import.py`

Implementation requirements:

- Export must copy and sanitize `trusted_state.content` before serializing.
- Export must remove `_canon_proposal`, `canon_proposal_revisions`, and any other non-registry internal proposal keys.
- Export must not include `Book.constraints["_canon_proposal"]` or any `CanonProposalRevision` row data.
- Import must sanitize incoming `trusted_state.content` before saving `Canon.content`.
- Import must remove `_canon_proposal`, `canon_proposal_revisions`, and revision-preview-shaped internal keys.
- Import must not write imported proposal metadata into `Book.constraints`.
- Reuse the section registry or normalization helper from `src/mynovel/workflows/canon_proposal.py` so export/import do not maintain their own internal-key list.

- [ ] **Step 2: Run targeted regression suite**

Run:

```bash
pixi run pytest \
  tests/workflows/test_canon_proposal.py \
  tests/workflows/test_open_book.py \
  tests/workflows/test_book_export.py \
  tests/workflows/test_book_import.py \
  tests/workflows/test_chapter_pipeline.py \
  tests/test_dev_server.py \
  tests/test_product_ui.py \
  tests/prompts/test_registry.py \
  -v
```

Expected: PASS.

- [ ] **Step 3: Run full tests**

Run: `pixi run test`  
Expected: PASS.

- [ ] **Step 4: Run lint**

Run: `pixi run lint`  
Expected: PASS.

- [ ] **Step 5: Check file sizes**

Run:

```bash
wc -l src/mynovel/dev_server.py src/mynovel/product_views.py src/mynovel/product_components.py src/mynovel/canon_proposal_views.py src/mynovel/workflows/canon_proposal.py
```

Expected: no file exceeds 1000 lines.

- [ ] **Step 6: Manual smoke test with local dev server**

Run: `pixi run dev`  
Open the reported URL and verify:
- `/book/{id}/state` shows clickable section cards.
- a draft book shows lock/unlock controls.
- a locked section disables AI revision input.
- creating a revision shows preview before application.
- applying revision updates visible proposal sections.
- global lock hides free revision controls.

Stop the dev server before finishing.

- [ ] **Step 7: Commit final cleanup**

If Task 5 required changes:

```bash
git add <changed-files>
git commit -m "test: cover canon proposal revision safeguards"
```

If no changes were required, do not create an empty commit.

## Implementation Notes

- Use `pixi run ...` for every test and dev command.
- Keep all new code comments in English.
- Keep UI copy in Chinese, matching existing product surfaces.
- Do not stage unrelated dirty files already present in the worktree.
- Use git identity `Logic Tan <logictan89@gmail.com>`.
- Do not call the model in tests. Inject fake model clients.
- Avoid broad refactors outside files listed above.
- When applying a revision, commit the canon change and revision status in one transaction.
