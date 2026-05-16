# Embedding Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real embedding-based chapter retrieval while removing rerank as a required product capability.

**Architecture:** Chat validation unlocks the app. Embedding validation becomes optional readiness for model-based retrieval. Accepted chapter and trusted-state entries store numeric vectors when possible; chapter generation retrieves bounded, source-labeled fragments into `chapter.context_package["retrieved_context"]`.

**Tech Stack:** Python 3.11, SQLModel, httpx OpenAI-compatible APIs, pytest, React + TypeScript + Vitest, pixi.

---

## File Map

- `src/mynovel/provider_config_validation.py`: validate required chat plus optional embedding; stop running rerank checks.
- `src/mynovel/api_serializers.py`: make bootstrap depend only on chat validation; add embedding readiness helper.
- `src/mynovel/api_provider_config.py`: save config when chat passes even if embedding fails; report embedding readiness.
- `src/mynovel/provider_config_status.py`: remove rerank and embedding from legacy completeness gate.
- `frontend/src/features/provider-config/ProviderConfigPage.tsx`: remove rerank UI; make embedding optional.
- `frontend/src/features/provider-config/providerConfigTypes.ts`: remove rerank draft fields; allow `embeddingValidated`.
- `src/mynovel/workflows/embedding.py`: new embedding service wrapper and response parser.
- `src/mynovel/workflows/retrieval.py`: numeric vector storage, cosine retrieval, lexical fallback.
- `src/mynovel/workflows/chapter_pipeline.py`: optional embedding indexing and retrieval in chapter runs.
- `src/mynovel/workflows/chapter_prompting.py`: render retrieved context below trusted state.
- Tests: `tests/test_provider_config_validation.py`, `tests/test_provider_config_api.py`, `tests/test_api_routes.py`, `tests/workflows/test_embedding.py`, `tests/workflows/test_retrieval_index.py`, `tests/workflows/test_chapter_pipeline.py`, `tests/workflows/test_chapter_pipeline_llm.py`, `frontend/tests/provider-config-page.test.tsx`.

---

### Task 1: Split Provider Readiness

**Files:**
- Modify: `src/mynovel/provider_config_validation.py`
- Modify: `src/mynovel/api_serializers.py`
- Modify: `src/mynovel/api_provider_config.py`
- Modify: `src/mynovel/provider_config_status.py`
- Test: `tests/test_provider_config_validation.py`
- Test: `tests/test_provider_config_api.py`
- Test: `tests/test_api_routes.py`

- [ ] **Step 1: Write failing provider validation tests**

Replace the top tests in `tests/test_provider_config_validation.py` with chat-required and embedding-optional expectations:

```python
def test_provider_validation_requires_chat_and_records_optional_embedding() -> None:
    config = _provider_config()
    checker = FakeChecker()

    report = asyncio.run(validate_provider_config(config, None, checker))

    assert report.passed is True
    assert checker.calls == ["llm", "embedding"]
    assert [result.kind for result in report.results] == ["llm", "embedding"]
    assert report.validation.llm_fingerprint == provider_model_fingerprint(config, "llm")
    assert report.validation.embedding_fingerprint == provider_model_fingerprint(
        config, "embedding"
    )
    assert report.validation.rerank_fingerprint is None


def test_provider_validation_allows_save_when_optional_embedding_fails() -> None:
    config = _provider_config()
    checker = FakeChecker(failures={"embedding", "rerank"})

    report = asyncio.run(validate_provider_config(config, None, checker))

    assert report.passed is True
    assert checker.calls == ["llm", "embedding"]
    assert _status_for(report, "llm") == "passed"
    assert _status_for(report, "embedding") == "failed"
    assert report.validation.llm_fingerprint == provider_model_fingerprint(config, "llm")
    assert report.validation.embedding_fingerprint is None


def test_provider_validation_blocks_when_chat_fails() -> None:
    config = _provider_config()
    checker = FakeChecker(failures={"llm"})

    report = asyncio.run(validate_provider_config(config, None, checker))

    assert report.passed is False
    assert checker.calls == ["llm", "embedding"]
    assert _status_for(report, "llm") == "failed"


def test_provider_validation_skips_unconfigured_embedding() -> None:
    config = _provider_config(embedding_model="")
    checker = FakeChecker()

    report = asyncio.run(validate_provider_config(config, None, checker))

    assert report.passed is True
    assert checker.calls == ["llm"]
    assert _status_for(report, "embedding") == "skipped"
    assert "未配置检索模型" in _message_for(report, "embedding")
```

- [ ] **Step 2: Verify the tests fail**

Run: `pixi run pytest tests/test_provider_config_validation.py -q`

Expected: FAIL because current validation still calls rerank and treats embedding failure as blocking.

- [ ] **Step 3: Implement chat-required validation**

In `src/mynovel/provider_config_validation.py`, change `ProviderValidationReport.passed`:

```python
@property
def passed(self) -> bool:
    return all(
        result.status != "failed" for result in self.results if result.kind == "llm"
    )
```

In `validate_provider_config()`, iterate only over `("llm", "embedding")`. Add the optional embedding skip before `_missing_required_message()`:

```python
if kind == "embedding" and not config.embedding_model.strip():
    validation.embedding_fingerprint = None
    results.append(
        ProviderCheckResult(
            kind,
            _model_label(kind),
            "skipped",
            "未配置检索模型，章节生产将使用本地检索。",
        )
    )
    continue
```

Keep `provider_model_fingerprint(config, "rerank")` working for backward compatibility, but stop invoking `_run_check()` with `"rerank"`.

- [ ] **Step 4: Update readiness helpers**

In `src/mynovel/api_serializers.py`, make `is_provider_config_validated()` check only `llm_fingerprint`. Add:

```python
def is_embedding_config_validated(
    config: ProviderConfig | None,
    validation: ProviderConfigValidation | None,
) -> bool:
    if config is None or validation is None or not config.embedding_model.strip():
        return False
    return validation.embedding_fingerprint == provider_model_fingerprint(config, "embedding")
```

In `src/mynovel/api_provider_config.py`, import this helper and return it from `get_provider_config_json()`:

```python
"embeddingValidated": is_embedding_config_validated(config, validation),
```

In `src/mynovel/provider_config_status.py`, reduce `is_provider_config_complete()` to LLM fields:

```python
return bool(
    provider_config
    and provider_config.llm_base_url.strip()
    and provider_config.llm_api_key
    and provider_config.llm_model.strip()
)
```

- [ ] **Step 5: Add API behavior tests**

Add to `tests/test_provider_config_api.py`:

```python
def test_save_provider_config_succeeds_when_embedding_fails(tmp_path) -> None:
    response = save_provider_config_json(
        tmp_path / "dev.sqlite",
        _payload(),
        FakeChecker(failures={"embedding"}),
    )

    assert response.status == HTTPStatus.OK
    assert response.body["saved"] is True
    statuses = _validation_statuses(response.body)
    assert statuses["llm"] == "passed"
    assert statuses["embedding"] == "failed"
    assert "rerank" not in statuses


def test_save_provider_config_ignores_missing_rerank_model(tmp_path) -> None:
    response = save_provider_config_json(
        tmp_path / "dev.sqlite",
        _payload(rerank_model=""),
        FakeChecker(failures={"rerank"}),
    )

    assert response.status == HTTPStatus.OK
    assert response.body["saved"] is True
    assert "rerank" not in _validation_statuses(response.body)
```

Update older test expectations that assert rerank calls or rerank failure blocking.

- [ ] **Step 6: Run provider tests**

Run: `pixi run pytest tests/test_provider_config_validation.py tests/test_provider_config_api.py tests/test_api_routes.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/mynovel/provider_config_validation.py src/mynovel/api_serializers.py src/mynovel/api_provider_config.py src/mynovel/provider_config_status.py tests/test_provider_config_validation.py tests/test_provider_config_api.py tests/test_api_routes.py
git commit -m "Allow chat-only provider readiness"
```

---

### Task 2: Update Provider Setup UI

**Files:**
- Modify: `frontend/src/features/provider-config/ProviderConfigPage.tsx`
- Modify: `frontend/src/features/provider-config/providerConfigTypes.ts`
- Test: `frontend/tests/provider-config-page.test.tsx`

- [ ] **Step 1: Write failing UI tests**

Add to `frontend/tests/provider-config-page.test.tsx`:

```tsx
test("provider setup requires chat and treats embedding as optional", () => {
  render(<ProviderConfigPage />);

  expect(screen.getByLabelText("Base url")).toBeRequired();
  expect(screen.getByLabelText("API key")).toBeRequired();
  expect(screen.getByLabelText("Model name")).toBeRequired();
  expect(screen.getByLabelText("Embedding model name")).not.toBeRequired();
  expect(screen.queryByLabelText("Rerank model name")).not.toBeInTheDocument();
});

test("dedicated embedding credentials are required only when embedding model is set", () => {
  render(<ProviderConfigPage />);

  fireEvent.click(screen.getByLabelText("Embedding 使用 LLM 的 base url 和 api key"));
  expect(screen.getByLabelText("Embedding base url")).not.toBeRequired();
  expect(screen.getByLabelText("Embedding API key")).not.toBeRequired();

  fireEvent.change(screen.getByLabelText("Embedding model name"), {
    target: { value: "text-embedding-test" },
  });
  expect(screen.getByLabelText("Embedding base url")).toBeRequired();
  expect(screen.getByLabelText("Embedding API key")).toBeRequired();
});
```

Remove or rewrite existing tests that expect visible rerank controls.

- [ ] **Step 2: Verify the UI tests fail**

Run: `pixi run frontend-test -- provider-config-page.test.tsx`

Expected: FAIL because rerank is still visible and embedding is required.

- [ ] **Step 3: Update TypeScript types**

In `frontend/src/features/provider-config/providerConfigTypes.ts`, remove rerank fields from `ProviderConfigDraft`:

```ts
export type ProviderConfigDraft = {
  llmBaseUrl: string;
  llmApiKey: string;
  llmModel: string;
  embeddingUseLlmCredentials: boolean;
  embeddingBaseUrl: string;
  embeddingApiKey: string;
  embeddingModel: string;
};
```

Add optional response status:

```ts
embeddingValidated?: boolean;
```

- [ ] **Step 4: Remove rerank UI and optionalize embedding**

In `ProviderConfigPage.tsx`, remove rerank keys from `emptyDraft`, delete the rerank section, and change the lead copy to:

```tsx
填入 OpenAI-compatible 对话模型信息；Embedding 可作为章节历史召回增强能力。
```

Remove `required` from `Embedding model name`. Add:

```tsx
const embeddingCredentialsRequired =
  !draft.embeddingUseLlmCredentials && draft.embeddingModel.trim().length > 0;
```

Use `required={embeddingCredentialsRequired}` for `Embedding base url` and `Embedding API key`.

- [ ] **Step 5: Update sanitization**

In `ProviderConfigPage.tsx`, redact only LLM and embedding keys:

```tsx
return Array.from(new Set([draft.llmApiKey, draft.embeddingApiKey]))
```

Replace `sanitizeProviderConfigDraft()` with:

```tsx
function sanitizeProviderConfigDraft(draft: ProviderConfigDraft): ProviderConfigDraft {
  if (!draft.embeddingUseLlmCredentials) {
    return draft;
  }
  return { ...draft, embeddingBaseUrl: "", embeddingApiKey: "" };
}
```

- [ ] **Step 6: Run and commit UI tests**

```bash
pixi run frontend-test -- provider-config-page.test.tsx
git add frontend/src/features/provider-config/ProviderConfigPage.tsx frontend/src/features/provider-config/providerConfigTypes.ts frontend/tests/provider-config-page.test.tsx
git commit -m "Make embedding optional in provider setup"
```

Expected: PASS before commit.

---

### Task 3: Add Embedding Service And Vector Retrieval

**Files:**
- Create: `src/mynovel/workflows/embedding.py`
- Modify: `src/mynovel/workflows/retrieval.py`
- Test: `tests/workflows/test_embedding.py`
- Test: `tests/workflows/test_retrieval_index.py`

- [ ] **Step 1: Write failing parser and retrieval tests**

Create `tests/workflows/test_embedding.py`:

```python
import pytest

from mynovel.workflows.embedding import parse_embedding_response


def test_parse_embedding_response_returns_first_vector() -> None:
    assert parse_embedding_response({"data": [{"embedding": [0.1, 0.2]}]}) == [0.1, 0.2]


def test_parse_embedding_response_rejects_missing_vector() -> None:
    with pytest.raises(ValueError, match="Embedding response has no usable vector"):
        parse_embedding_response({"data": []})
```

Add to `tests/workflows/test_retrieval_index.py`:

```python
def test_model_retrieval_ranks_by_cosine_similarity(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        index_text(session, book.id, "note", "symbol", "符号发热", embedding_vector=[1.0, 0.0], embedding_model="embedding-test")
        index_text(session, book.id, "note", "market", "普通草药", embedding_vector=[0.0, 1.0], embedding_model="embedding-test")

        results = retrieve_book_context(
            session,
            book.id,
            "符号",
            query_embedding=[0.9, 0.1],
            embedding_model="embedding-test",
            top_k=2,
        )

    assert [result.source_id for result in results] == ["symbol", "market"]
    assert results[0].score > results[1].score


def test_model_retrieval_ignores_different_embedding_model(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        index_text(session, book.id, "note", "old", "旧模型", embedding_vector=[1.0, 0.0], embedding_model="old")
        results = retrieve_book_context(
            session,
            book.id,
            "旧模型",
            query_embedding=[1.0, 0.0],
            embedding_model="new",
        )

    assert results == []
```

Update the import to include `retrieve_book_context`.

- [ ] **Step 2: Verify the tests fail**

Run: `pixi run pytest tests/workflows/test_embedding.py tests/workflows/test_retrieval_index.py -q`

Expected: FAIL because embedding service and model retrieval do not exist.

- [ ] **Step 3: Create embedding service**

Create `src/mynovel/workflows/embedding.py`:

```python
from __future__ import annotations

import asyncio
from typing import Protocol

from mynovel.api_serializers import is_embedding_config_validated
from mynovel.domain.models import ProviderConfig, ProviderConfigValidation
from mynovel.llm.openai_compatible import EmbeddingRequest, OpenAICompatibleClient


class TextEmbeddingClient(Protocol):
    model: str
    def embed_text(self, text: str) -> list[float]: ...


class OpenAITextEmbeddingClient:
    def __init__(self, client: OpenAICompatibleClient, model: str) -> None:
        self.client = client
        self.model = model

    def embed_text(self, text: str) -> list[float]:
        response = asyncio.run(self.client.embeddings(EmbeddingRequest(model=self.model, input=text)))
        return parse_embedding_response(response)


def parse_embedding_response(response: dict) -> list[float]:
    data = response.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise ValueError("Embedding response has no usable vector.")
    vector = data[0].get("embedding")
    if not isinstance(vector, list) or not vector:
        raise ValueError("Embedding response has no usable vector.")
    try:
        return [float(value) for value in vector]
    except (TypeError, ValueError) as error:
        raise ValueError("Embedding response has no usable vector.") from error


def embedding_client_from_provider_config(
    config: ProviderConfig | None,
    validation: ProviderConfigValidation | None,
) -> TextEmbeddingClient | None:
    if not is_embedding_config_validated(config, validation):
        return None
    assert config is not None
    return OpenAITextEmbeddingClient(
        OpenAICompatibleClient(config.resolved_embedding_base_url(), config.resolved_embedding_api_key() or ""),
        config.embedding_model,
    )
```

- [ ] **Step 4: Implement retrieval primitives**

In `src/mynovel/workflows/retrieval.py`, add `RetrievedContext`, constants, and optional vector fields on `index_text()`:

```python
@dataclass(frozen=True)
class RetrievedContext:
    source_type: str
    source_id: str
    score: float
    text: str
    metadata: dict[str, Any]
```

When `embedding_vector` and `embedding_model` are provided, store `embedding` as a list of floats and metadata `embedding_kind`, `embedding_model`, `embedding_dimensions`. Otherwise keep the current token-count dict and set `embedding_kind` to `"lexical"`.

Add `retrieve_book_context()` with this behavior:

```python
def retrieve_book_context(..., query_embedding: list[float] | None = None, embedding_model: str | None = None, top_k: int = 10, character_budget: int = 10_000) -> list[RetrievedContext]:
    if query_embedding is not None and embedding_model:
        score same-model numeric vectors by cosine similarity
    else:
        call search_book_context() and wrap the entries
    truncate selected text to the remaining character budget
```

Implement helpers `_model_vector()`, `_cosine_similarity()`, and `_bounded_context()` in the same file.

- [ ] **Step 5: Run and commit retrieval tests**

```bash
pixi run pytest tests/workflows/test_embedding.py tests/workflows/test_retrieval_index.py -q
git add src/mynovel/workflows/embedding.py src/mynovel/workflows/retrieval.py tests/workflows/test_embedding.py tests/workflows/test_retrieval_index.py
git commit -m "Add embedding retrieval primitives"
```

Expected: PASS before commit.

---

### Task 4: Index Approved Chapters With Embeddings

**Files:**
- Modify: `src/mynovel/workflows/chapter_pipeline.py`
- Test: `tests/workflows/test_retrieval_index.py`
- Test: `tests/workflows/test_chapter_pipeline.py`

- [ ] **Step 1: Write failing approval-index tests**

Add to `tests/workflows/test_retrieval_index.py`:

```python
class FakeEmbeddingClient:
    model = "embedding-test"
    def __init__(self, failures: bool = False) -> None:
        self.failures = failures
        self.inputs: list[str] = []
    def embed_text(self, text: str) -> list[float]:
        self.inputs.append(text)
        if self.failures:
            raise RuntimeError("embedding unavailable")
        return [float(len(text)), 1.0]


def test_accepted_chapter_index_uses_embedding_client(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    embedder = FakeEmbeddingClient()
    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = run_chapter_pipeline(session, _first_chapter_id(session, book.id))
        chapter.state_delta = {"chapter": 1, "changes": []}
        session.add(chapter)
        session.commit()
        approve_chapter(session, chapter.id, embedding_client=embedder)
        entries = list_vector_entries_for_book(session, book.id)

    assert len(embedder.inputs) == 2
    assert all(entry.metadata_["embedding_kind"] == "model" for entry in entries)
    assert all(isinstance(entry.embedding, list) for entry in entries)


def test_accepted_chapter_index_falls_back_when_embedding_fails(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        chapter = run_chapter_pipeline(session, _first_chapter_id(session, book.id))
        chapter.state_delta = {"chapter": 1, "changes": []}
        session.add(chapter)
        session.commit()
        accepted = approve_chapter(session, chapter.id, embedding_client=FakeEmbeddingClient(failures=True))
        entries = list_vector_entries_for_book(session, book.id)

    assert accepted.status.value == "accepted"
    assert all(entry.metadata_["embedding_kind"] == "lexical" for entry in entries)
    assert all("embedding unavailable" in entry.metadata_["embedding_error"] for entry in entries)
```

- [ ] **Step 2: Verify the tests fail**

Run: `pixi run pytest tests/workflows/test_retrieval_index.py::test_accepted_chapter_index_uses_embedding_client tests/workflows/test_retrieval_index.py::test_accepted_chapter_index_falls_back_when_embedding_fails -q`

Expected: FAIL because `approve_chapter()` has no `embedding_client` keyword.

- [ ] **Step 3: Update chapter approval indexing**

In `chapter_pipeline.py`, import `TextEmbeddingClient`, `embedding_client_from_provider_config`, `get_provider_config`, and `get_provider_config_validation`.

Change `approve_chapter()`:

```python
def approve_chapter(..., *, embedding_client: TextEmbeddingClient | None = None) -> Chapter:
    embedding_client = embedding_client or _embedding_client_from_session(session)
```

Add:

```python
def _embedding_client_from_session(session: Session) -> TextEmbeddingClient | None:
    return embedding_client_from_provider_config(
        get_provider_config(session),
        get_provider_config_validation(session),
    )


def _embedding_for_index(client: TextEmbeddingClient | None, text: str) -> tuple[list[float] | None, str | None, str | None]:
    if client is None:
        return None, None, None
    try:
        return client.embed_text(text), client.model, None
    except Exception as error:  # noqa: BLE001
        return None, None, str(error) or type(error).__name__
```

Pass `embedding_vector`, `embedding_model`, and `embedding_error` into both `index_text()` calls inside `_index_accepted_chapter()`.

- [ ] **Step 4: Run and commit approval indexing tests**

```bash
pixi run pytest tests/workflows/test_retrieval_index.py tests/workflows/test_chapter_pipeline.py -q
git add src/mynovel/workflows/chapter_pipeline.py tests/workflows/test_retrieval_index.py tests/workflows/test_chapter_pipeline.py
git commit -m "Index accepted chapters with embeddings"
```

Expected: PASS before commit.

---

### Task 5: Retrieve Context For Chapter Prompts

**Files:**
- Modify: `src/mynovel/workflows/chapter_pipeline.py`
- Modify: `src/mynovel/workflows/chapter_prompting.py`
- Test: `tests/workflows/test_chapter_pipeline.py`
- Test: `tests/workflows/test_chapter_pipeline_llm.py`

- [ ] **Step 1: Write failing context and prompt tests**

Add to `tests/workflows/test_chapter_pipeline.py`:

```python
class _FixedEmbeddingClient:
    model = "embedding-test"
    def embed_text(self, text: str) -> list[float]:
        return [1.0, 0.0] if "莉拉" in text or "符号" in text else [0.5, 0.5]


def test_chapter_pipeline_adds_retrieved_context_from_embedding(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    embedder = _FixedEmbeddingClient()
    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        first = list_chapters_for_book(session, book.id)[0]
        reviewed = run_chapter_pipeline(session, first.id, embedding_client=embedder)
        approve_chapter(session, reviewed.id, embedding_client=embedder)
        second = list_chapters_for_book(session, book.id)[1]
        next_reviewed = run_chapter_pipeline(session, second.id, embedding_client=embedder)

    retrieved = next_reviewed.context_package["retrieved_context"]
    assert retrieved
    assert {"source_type", "source_id", "score", "text"} <= set(retrieved[0])
```

Add to `tests/workflows/test_chapter_pipeline_llm.py`:

```python
def test_run_chapter_pipeline_prompt_includes_retrieved_context(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)
    model = FakeChapterModel()
    embedder = _PromptEmbeddingClient()
    with Session(engine) as session:
        book = create_draft_book_from_blueprint(session, _blueprint(), selected_title="长夜图书馆")
        first = book_chapter(session, book.id, 1)
        reviewed = run_chapter_pipeline(session, first.id, embedding_client=embedder)
        approve_chapter(session, reviewed.id, embedding_client=embedder)
        second = book_chapter(session, book.id, 2)
        run_chapter_pipeline(session, second.id, model_client=model, model_name="章节模型", embedding_client=embedder)

    prompt = "\n".join(message["content"] for message in model.messages_by_stage["draft"])
    assert "历史召回片段" in prompt
    assert "可信设定优先于历史召回片段" in prompt


class _PromptEmbeddingClient:
    model = "embedding-test"
    def embed_text(self, text: str) -> list[float]:
        return [1.0, 0.0] if "莉拉" in text else [0.5, 0.5]
```

- [ ] **Step 2: Verify the tests fail**

Run: `pixi run pytest tests/workflows/test_chapter_pipeline.py::test_chapter_pipeline_adds_retrieved_context_from_embedding tests/workflows/test_chapter_pipeline_llm.py::test_run_chapter_pipeline_prompt_includes_retrieved_context -q`

Expected: FAIL because `run_chapter_pipeline()` does not accept `embedding_client` and prompts do not render retrieved context.

- [ ] **Step 3: Build retrieved context in chapter pipeline**

In `chapter_pipeline.py`, update `run_chapter_pipeline()` to accept keyword-only `embedding_client`. Pass `session` and the client into `_run_simulated_pipeline()` and `_run_model_pipeline()`.

Add:

```python
def _retrieved_context_for_chapter(session: Session, chapter: Chapter, canon: Canon, client: TextEmbeddingClient | None) -> list[dict[str, Any]]:
    query = _chapter_retrieval_query(chapter, canon)
    query_embedding = None
    embedding_model = None
    if client is not None:
        try:
            query_embedding = client.embed_text(query)
            embedding_model = client.model
        except Exception:  # noqa: BLE001
            query_embedding = None
    return [_retrieved_context_payload(item) for item in retrieve_book_context(session, chapter.book_id, query, query_embedding=query_embedding, embedding_model=embedding_model)]
```

Add `_chapter_retrieval_query()` using chapter title, `chapter.plan["goal"]`, `must_write`, recent `chapter_summaries`, `characters`, and `foreshadowing`. Add `_retrieved_context_payload()` with `source_type`, `source_id`, rounded `score`, `text`, and `metadata`.

Change `_build_context_package()` to accept `retrieved_context` and include:

```python
"retrieved_context": retrieved_context or [],
```

- [ ] **Step 4: Render retrieved context in prompts**

In `chapter_prompting.py`, append retrieved context in `_context_package_text()` after trusted state and volume plan:

```python
retrieved_context = _retrieved_context_text(context_package.get("retrieved_context"))
if retrieved_context:
    sections.append(retrieved_context)
```

Add:

```python
def _retrieved_context_text(value: object) -> str:
    if not isinstance(value, list) or not value:
        return ""
    lines = ["历史召回片段：", "可信设定优先于历史召回片段；当两者冲突时，忽略召回片段。"]
    for index, item in enumerate(value[:10], start=1):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        source_type = str(item.get("source_type") or "unknown").strip()
        score = item.get("score")
        label = f"{index}. {source_type}"
        if isinstance(score, int | float):
            label += f" score={score:.3f}"
        lines.extend([label, text[:1200]])
    return "\n".join(lines) if len(lines) > 2 else ""
```

- [ ] **Step 5: Run and commit chapter context tests**

```bash
pixi run pytest tests/workflows/test_chapter_pipeline.py tests/workflows/test_chapter_pipeline_llm.py -q
git add src/mynovel/workflows/chapter_pipeline.py src/mynovel/workflows/chapter_prompting.py tests/workflows/test_chapter_pipeline.py tests/workflows/test_chapter_pipeline_llm.py
git commit -m "Add retrieved context to chapter prompts"
```

Expected: PASS before commit.

---

### Task 6: Final Verification

**Files:**
- Verify all feature files listed in the File Map.

- [ ] **Step 1: Run backend tests**

Run: `pixi run pytest -q`

Expected: PASS.

- [ ] **Step 2: Run backend lint and typecheck**

Run:

```bash
pixi run lint
pixi run typecheck
```

Expected: PASS for both commands.

- [ ] **Step 3: Run frontend tests and typecheck**

Run:

```bash
pixi run frontend-test
pixi run frontend-typecheck
```

Expected: PASS for both commands.

- [ ] **Step 4: Inspect git status**

Run: `git status --short --branch`

Expected: the implementation commits are present; unrelated pre-existing user changes may remain in `src/mynovel/workflows/chapter_repair.py`, `src/mynovel/workflows/chapter_repair_terms.py`, and `tests/test_product_ui_workspace.py`.

- [ ] **Step 5: Commit verification fixes if any were needed**

If verification required fixes, add the exact feature files touched by those fixes:

```bash
git add src/mynovel/provider_config_validation.py src/mynovel/api_serializers.py src/mynovel/api_provider_config.py src/mynovel/provider_config_status.py frontend/src/features/provider-config/ProviderConfigPage.tsx frontend/src/features/provider-config/providerConfigTypes.ts src/mynovel/workflows/embedding.py src/mynovel/workflows/retrieval.py src/mynovel/workflows/chapter_pipeline.py src/mynovel/workflows/chapter_prompting.py tests/test_provider_config_validation.py tests/test_provider_config_api.py tests/test_api_routes.py tests/workflows/test_embedding.py tests/workflows/test_retrieval_index.py tests/workflows/test_chapter_pipeline.py tests/workflows/test_chapter_pipeline_llm.py frontend/tests/provider-config-page.test.tsx
git commit -m "Stabilize embedding retrieval integration"
```

If no fixes were required, do not create a commit.

---

## Self-Review

- Spec coverage: Task 1 covers chat-only readiness and optional embedding status. Task 2 covers setup UI and rerank removal. Task 3 covers embedding parsing, vector storage, cosine retrieval, model mismatch, and bounded results. Task 4 covers approved-chapter indexing and runtime fallback. Task 5 covers chapter context package and prompt priority. Task 6 covers project verification.
- Placeholder scan: The plan uses concrete file paths, test names, code snippets, and commands. The only flexible step is final verification cleanup, and it lists the exact feature files to stage.
- Type consistency: `TextEmbeddingClient.model`, `embed_text()`, `RetrievedContext`, `retrieve_book_context()`, `embedding_client` keyword parameters, and `retrieved_context` payload keys are introduced before later tasks use them.
