# MyNovel Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the M0-M1 foundation for MyNovel: pixi project scaffold, SQLite-backed core domain, OpenAI-compatible client shell, prompt registry, CLI, CI skeleton, and the first open-book canon workflow.

**Architecture:** Use a Python core package as the single source of business logic, with SQLite as the authoritative local store. Keep CLI/API/UI concerns outside the domain layer so the later review desk and desktop shell can reuse the same production pipeline.

**Tech Stack:** Python, pixi, SQLite, SQLModel or SQLAlchemy + Pydantic, Typer, pytest, ruff, OpenAI-compatible HTTP API, GitHub Actions.

---

## Scope

This plan covers M0 and the first usable slice of M1 only:

- project scaffold
- license and repository hygiene
- domain schema for Book/Canon/RunTrace
- SQLite persistence
- OpenAI-compatible configuration and client interface
- prompt registry skeleton
- CLI commands for setup and opening a book
- CI skeleton

It does not implement chapter drafting, audit/revise, review desk UI, vector search, desktop packaging, or application updates. Those should be separate plans.

## Target File Structure

- Create: `pyproject.toml`  
  Python package metadata and tool configuration.
- Create: `pixi.toml`  
  Local development environments and commands.
- Create: `src/mynovel/__init__.py`  
  Package version export.
- Create: `src/mynovel/config.py`  
  App configuration loading and validation.
- Create: `src/mynovel/db.py`  
  SQLite engine/session creation and migration bootstrap.
- Create: `src/mynovel/domain/models.py`  
  Domain models and enums for Book, Canon, RunTrace, PromptAsset.
- Create: `src/mynovel/domain/repositories.py`  
  Persistence operations for books, canon, traces, and prompts.
- Create: `src/mynovel/llm/openai_compatible.py`  
  Minimal OpenAI-compatible client wrapper.
- Create: `src/mynovel/prompts/registry.py`  
  Prompt registry loader and license/source metadata validation.
- Create: `src/mynovel/prompts/assets/open_book.yaml`  
  First prompt asset for open-book planning.
- Create: `src/mynovel/workflows/open_book.py`  
  Open-book workflow orchestration.
- Create: `src/mynovel/cli.py`  
  Typer CLI entrypoint.
- Create: `tests/` files mirroring the package.
- Create: `.github/workflows/ci.yml`  
  CI checks for lint and tests.
- Modify: `docs/superpowers/specs/2026-05-10-product-plan-design.md` only if implementation reveals a design gap.

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `pixi.toml`
- Create: `src/mynovel/__init__.py`
- Create: `tests/test_package.py`

- [ ] **Step 1: Write the package import test**

Create `tests/test_package.py`:

```python
import mynovel


def test_package_has_version() -> None:
    assert isinstance(mynovel.__version__, str)
    assert mynovel.__version__
```

- [ ] **Step 2: Add project metadata**

Create `pyproject.toml` with:

```toml
[project]
name = "mynovel"
version = "0.1.0"
description = "Local AI-led web novel production pipeline with human review gates."
requires-python = ">=3.11"
dependencies = [
  "httpx>=0.27",
  "pydantic>=2.7",
  "sqlmodel>=0.0.22",
  "typer>=0.12",
  "pyyaml>=6.0",
]

[project.scripts]
mynovel = "mynovel.cli:app"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

- [ ] **Step 3: Add pixi environment**

Create `pixi.toml` with:

```toml
[project]
name = "mynovel"
channels = ["conda-forge"]
platforms = ["osx-arm64", "osx-64", "linux-64", "win-64"]

[dependencies]
python = ">=3.11,<3.13"
pip = ">=24"

[pypi-dependencies]
mynovel = { path = ".", editable = true }
pytest = ">=8.0"
ruff = ">=0.5"

[tasks]
test = "pytest"
lint = "ruff check src tests"
format = "ruff format src tests"
cli = "mynovel --help"
```

- [ ] **Step 4: Add package version**

Create `src/mynovel/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 5: Run tests**

Run: `pixi run test`  
Expected: package import test passes.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml pixi.toml src/mynovel/__init__.py tests/test_package.py
git commit -m "🏗️ build(project): scaffold Python package with pixi"
```

## Task 2: Domain Models and SQLite Bootstrap

**Files:**
- Create: `src/mynovel/domain/models.py`
- Create: `src/mynovel/db.py`
- Create: `tests/domain/test_models.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write model tests**

Create `tests/domain/test_models.py`:

```python
from mynovel.domain.models import Book, BookStatus


def test_book_defaults_to_draft() -> None:
    book = Book(title="Untitled", genre="xianxia", audience="web novel readers")

    assert book.status == BookStatus.DRAFT
```

- [ ] **Step 2: Write DB bootstrap test**

Create `tests/test_db.py`:

```python
from pathlib import Path

from mynovel.db import create_db_and_tables, create_engine_for_path


def test_create_db_and_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    engine = create_engine_for_path(db_path)

    create_db_and_tables(engine)

    assert db_path.exists()
```

- [ ] **Step 3: Implement models**

Create `src/mynovel/domain/models.py`:

```python
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BookStatus(StrEnum):
    DRAFT = "draft"
    CANON_LOCKED = "canon_locked"
    PRODUCING = "producing"
    PAUSED = "paused"


class Book(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    genre: str
    audience: str
    status: BookStatus = BookStatus.DRAFT
    premise: str | None = None
    constraints: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Canon(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(index=True, foreign_key="book.id")
    version: int = 1
    content: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class RunTrace(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int | None = Field(default=None, index=True, foreign_key="book.id")
    stage: str
    prompt_id: str | None = None
    prompt_version: str | None = None
    model: str | None = None
    cost: dict = Field(default_factory=dict, sa_column=Column(JSON))
    metadata: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
```

- [ ] **Step 4: Implement DB helpers**

Create `src/mynovel/db.py`:

```python
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine


def create_engine_for_path(path: Path) -> Engine:
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


def create_db_and_tables(engine: Engine) -> None:
    from mynovel.domain import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
```

- [ ] **Step 5: Run tests**

Run: `pixi run test tests/domain/test_models.py tests/test_db.py -v`  
Expected: both tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/mynovel/domain/models.py src/mynovel/db.py tests/domain/test_models.py tests/test_db.py
git commit -m "🗃️ feat(domain): add SQLite-backed core models"
```

## Task 3: Prompt Registry With Source Metadata

**Files:**
- Create: `src/mynovel/prompts/registry.py`
- Create: `src/mynovel/prompts/assets/open_book.yaml`
- Create: `tests/prompts/test_registry.py`

- [ ] **Step 1: Write registry tests**

Create `tests/prompts/test_registry.py`:

```python
from pathlib import Path

from mynovel.prompts.registry import load_prompt_asset


def test_prompt_asset_requires_source_metadata(tmp_path: Path) -> None:
    path = tmp_path / "prompt.yaml"
    path.write_text(
        """
id: open_book
name: Open Book
version: "0.1.0"
purpose: Create initial book canon
source: original
source_license: Apache-2.0
template: "Write a book plan for {{ idea }}"
""".strip(),
        encoding="utf-8",
    )

    asset = load_prompt_asset(path)

    assert asset.id == "open_book"
    assert asset.source_license == "Apache-2.0"
```

- [ ] **Step 2: Implement registry**

Create `src/mynovel/prompts/registry.py`:

```python
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class PromptAsset(BaseModel):
    id: str
    name: str
    version: str
    purpose: str
    source: str
    source_license: str
    template: str
    adaptation_notes: str | None = None
    model_family_hint: str | None = None
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
    evaluation_notes: str | None = None


def load_prompt_asset(path: Path) -> PromptAsset:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return PromptAsset.model_validate(data)
```

- [ ] **Step 3: Add first prompt asset**

Create `src/mynovel/prompts/assets/open_book.yaml`:

```yaml
id: open_book
name: Open Book Canon Planner
version: "0.1.0"
purpose: Generate initial web novel direction and canon from one idea.
source: original
source_license: Apache-2.0
adaptation_notes: Designed for MyNovel schema-first open-book workflow.
template: |
  You are planning a serialized web novel production line.
  Given the user's idea, produce a concise book direction, target reader,
  protagonist, core conflict, world rules, writing constraints, and the
  first 10 chapter promises.
```

- [ ] **Step 4: Run tests**

Run: `pixi run test tests/prompts/test_registry.py -v`  
Expected: prompt registry test passes.

- [ ] **Step 5: Commit**

```bash
git add src/mynovel/prompts/registry.py src/mynovel/prompts/assets/open_book.yaml tests/prompts/test_registry.py
git commit -m "🧾 feat(prompts): add source-aware prompt registry"
```

## Task 4: OpenAI-Compatible Client Shell

**Files:**
- Create: `src/mynovel/config.py`
- Create: `src/mynovel/llm/openai_compatible.py`
- Create: `tests/llm/test_openai_compatible.py`

- [ ] **Step 1: Write client payload test**

Create `tests/llm/test_openai_compatible.py`:

```python
from mynovel.llm.openai_compatible import ChatRequest


def test_chat_request_payload() -> None:
    request = ChatRequest(model="test-model", messages=[{"role": "user", "content": "hi"}])

    assert request.to_payload()["model"] == "test-model"
```

- [ ] **Step 2: Implement config**

Create `src/mynovel/config.py`:

```python
from pathlib import Path

from pydantic import BaseModel


class AppConfig(BaseModel):
    data_dir: Path
    llm_base_url: str
    llm_api_key: str
    llm_model: str
```

- [ ] **Step 3: Implement client shell**

Create `src/mynovel/llm/openai_compatible.py`:

```python
from typing import Any

import httpx
from pydantic import BaseModel


class ChatRequest(BaseModel):
    model: str
    messages: list[dict[str, str]]
    temperature: float | None = None
    extra: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model, "messages": self.messages}
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.extra:
            payload.update(self.extra)
        return payload


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def chat(self, request: ChatRequest) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=request.to_payload(),
            )
            response.raise_for_status()
            return response.json()
```

- [ ] **Step 4: Run tests**

Run: `pixi run test tests/llm/test_openai_compatible.py -v`  
Expected: client payload test passes without network access.

- [ ] **Step 5: Commit**

```bash
git add src/mynovel/config.py src/mynovel/llm/openai_compatible.py tests/llm/test_openai_compatible.py
git commit -m "🔌 feat(llm): add OpenAI-compatible client shell"
```

## Task 5: Open-Book Workflow and CLI

**Files:**
- Create: `src/mynovel/domain/repositories.py`
- Create: `src/mynovel/workflows/open_book.py`
- Create: `src/mynovel/cli.py`
- Create: `tests/workflows/test_open_book.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write repository workflow test**

Create `tests/workflows/test_open_book.py`:

```python
from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.workflows.open_book import create_draft_book


def test_create_draft_book(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        book = create_draft_book(session, idea="废土修仙", genre="xianxia", audience="web readers")

    assert book.id is not None
    assert book.title == "Untitled"
```

- [ ] **Step 2: Implement repositories**

Create `src/mynovel/domain/repositories.py`:

```python
from sqlmodel import Session

from mynovel.domain.models import Book


def add_book(session: Session, book: Book) -> Book:
    session.add(book)
    session.commit()
    session.refresh(book)
    return book
```

- [ ] **Step 3: Implement open-book workflow shell**

Create `src/mynovel/workflows/open_book.py`:

```python
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
```

- [ ] **Step 4: Implement CLI**

Create `src/mynovel/cli.py`:

```python
from pathlib import Path

import typer
from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.workflows.open_book import create_draft_book

app = typer.Typer(no_args_is_help=True)


@app.command()
def init(db: Path = typer.Option(Path("mynovel.sqlite"), help="SQLite database path.")) -> None:
    engine = create_engine_for_path(db)
    create_db_and_tables(engine)
    typer.echo(f"Initialized {db}")


@app.command("open-book")
def open_book(
    idea: str = typer.Argument(...),
    genre: str = typer.Option("web-novel"),
    audience: str = typer.Option("web novel readers"),
    db: Path = typer.Option(Path("mynovel.sqlite")),
) -> None:
    engine = create_engine_for_path(db)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = create_draft_book(session, idea=idea, genre=genre, audience=audience)
    typer.echo(f"Created draft book #{book.id}: {book.premise}")
```

- [ ] **Step 5: Run workflow tests**

Run: `pixi run test tests/workflows/test_open_book.py -v`  
Expected: workflow test passes.

- [ ] **Step 6: Smoke-test CLI**

Run: `pixi run mynovel init --db /tmp/mynovel-test.sqlite`  
Expected: outputs `Initialized /tmp/mynovel-test.sqlite`.

- [ ] **Step 7: Commit**

```bash
git add src/mynovel/domain/repositories.py src/mynovel/workflows/open_book.py src/mynovel/cli.py tests/workflows/test_open_book.py tests/test_cli.py
git commit -m "🚀 feat(cli): add open-book workflow shell"
```

## Task 6: CI Skeleton

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Add CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: prefix-dev/setup-pixi@v0.8.8
      - run: pixi run lint
      - run: pixi run test
```

- [ ] **Step 2: Run local verification**

Run: `pixi run lint`  
Expected: no lint errors.

Run: `pixi run test`  
Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "👷 ci: add pixi test workflow"
```

## Task 7: Documentation Checkpoint

**Files:**
- Modify: `docs/superpowers/specs/2026-05-10-product-plan-design.md`
- Create: `README.md`

- [ ] **Step 1: Add README skeleton**

Create `README.md`:

````markdown
# MyNovel

Local AI-led web novel production pipeline with human review gates.

## Status

Planning and early foundation work.

## Product Direction

MyNovel is not a text editor. It is a personal local AI web-novel production line:
AI plans, drafts, audits, revises, and maintains state; the author reviews and approves.

## Development

```bash
pixi run test
pixi run lint
```

## License

Apache-2.0.
````

- [ ] **Step 2: Update design doc if any implementation detail changed**

Only edit the spec if implementation changes a product decision. Do not churn wording.

- [ ] **Step 3: Run verification**

Run: `pixi run test && pixi run lint`  
Expected: all tests and lint pass.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/superpowers/specs/2026-05-10-product-plan-design.md
git commit -m "📝 docs(project): add foundation README"
```

## Handoff Notes

- This plan intentionally stops before real LLM generation. The first client is a shell to keep tests deterministic and avoid network calls.
- The next plan should implement M2: `plan -> context -> draft -> extract -> audit -> revise -> accept` for one chapter using fake LLM fixtures first.
- Do not add vector search until canon persistence and RunTrace are stable.
- Do not add UI until CLI workflow and SQLite state are demonstrably stable.
