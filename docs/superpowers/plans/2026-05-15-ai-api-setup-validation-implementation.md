# AI API Setup Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require chat, embedding, and rerank model configuration to pass OpenAI-compatible connection checks before saving AI API settings.

**Architecture:** Add a small validation module that fingerprints effective model connection fields, skips unchanged passing checks, and records passed fingerprints in a new local metadata table. Route POST `/provider-config` through a focused server helper so `dev_server.py` stays under the 1000-line refactor threshold. Update the setup renderer to show three required model sections and per-model validation status.

**Tech Stack:** Python 3.11, SQLModel, httpx, existing `OpenAICompatibleClient`, stdlib `http.server`, pytest.

---

## File Structure

- Create `src/mynovel/provider_config_validation.py` for fingerprints, check result types, checker protocol, and validation orchestration.
- Create `src/mynovel/provider_config_server.py` for POST `/provider-config` handling and response construction.
- Modify `src/mynovel/domain/models.py` to add `ProviderConfigValidation`.
- Modify `src/mynovel/domain/repositories.py` to load and save validation metadata.
- Modify `src/mynovel/model_setup_views.py` and `src/mynovel/product_views.py` to render the updated setup form and validation report.
- Modify `src/mynovel/dev_server.py` to delegate provider-config POST handling.
- Modify tests in `tests/domain/test_provider_config.py`, `tests/test_db.py`, `tests/test_product_regressions.py`, `tests/test_product_ui.py`, and add `tests/test_provider_config_validation.py` plus `tests/test_provider_config_server.py`.

## Task 1: Persist Validation Metadata

**Files:**
- Modify: `src/mynovel/domain/models.py`
- Modify: `src/mynovel/domain/repositories.py`
- Test: `tests/domain/test_provider_config.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing repository tests**

Add tests that create and update a single-row `ProviderConfigValidation` record:

```python
from mynovel.domain.models import ProviderConfigValidation
from mynovel.domain.repositories import get_provider_config_validation, save_provider_config_validation


def test_provider_config_validation_round_trips_through_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)

    with Session(engine) as session:
        saved = save_provider_config_validation(
            session,
            ProviderConfigValidation(
                llm_fingerprint="llm-pass",
                embedding_fingerprint="embedding-pass",
                rerank_fingerprint="rerank-pass",
            ),
        )
        loaded = get_provider_config_validation(session)

    assert saved.id == 1
    assert loaded is not None
    assert loaded.llm_fingerprint == "llm-pass"
    assert loaded.embedding_fingerprint == "embedding-pass"
    assert loaded.rerank_fingerprint == "rerank-pass"
```

- [ ] **Step 2: Verify RED**

Run: `pixi run pytest tests/domain/test_provider_config.py::test_provider_config_validation_round_trips_through_sqlite -q`

Expected: FAIL because `ProviderConfigValidation` and repository functions do not exist.

- [ ] **Step 3: Implement metadata model and repositories**

Add a `ProviderConfigValidation(SQLModel, table=True)` model with `id=1`, nullable fingerprint fields, and timestamps. Add `get_provider_config_validation(session)` and `save_provider_config_validation(session, validation)`.

- [ ] **Step 4: Verify GREEN**

Run: `pixi run pytest tests/domain/test_provider_config.py::test_provider_config_validation_round_trips_through_sqlite tests/test_db.py::test_create_db_and_tables -q`

Expected: PASS.

## Task 2: Validate And Cache Model Checks

**Files:**
- Create: `src/mynovel/provider_config_validation.py`
- Test: `tests/test_provider_config_validation.py`

- [ ] **Step 1: Write failing validation tests**

Cover three behaviors with a fake checker:

```python
class FakeChecker:
    def __init__(self, failures: set[str] | None = None) -> None:
        self.failures = failures or set()
        self.calls: list[str] = []

    async def check_chat(self, config: ProviderConfig) -> None:
        self.calls.append("llm")
        if "llm" in self.failures:
            raise RuntimeError("chat failed")

    async def check_embedding(self, config: ProviderConfig) -> None:
        self.calls.append("embedding")
        if "embedding" in self.failures:
            raise RuntimeError("embedding failed")

    async def check_rerank(self, config: ProviderConfig) -> None:
        self.calls.append("rerank")
        if "rerank" in self.failures:
            raise RuntimeError("rerank failed")
```

Tests:

- first validation calls all three check methods and records passed fingerprints;
- second validation with one previous passing fingerprint skips only that model;
- changing the effective model name for a previously passed model forces that model to run again.

- [ ] **Step 2: Verify RED**

Run: `pixi run pytest tests/test_provider_config_validation.py -q`

Expected: FAIL because the validation module does not exist.

- [ ] **Step 3: Implement validation orchestration**

Implement:

- `ProviderModelKind = Literal["llm", "embedding", "rerank"]`
- `ProviderCheckStatus = Literal["passed", "failed", "skipped"]`
- `ProviderCheckResult(kind, label, status, message)`
- `ProviderValidationReport(results)` with `passed` property
- `provider_model_fingerprint(config, kind)`
- `validate_provider_config(config, previous_validation, checker)`

Use SHA-256 over kind, effective base URL, effective API key, and model name. Before HTTP checks, fail missing required effective fields with a Chinese error message.

- [ ] **Step 4: Verify GREEN**

Run: `pixi run pytest tests/test_provider_config_validation.py -q`

Expected: PASS.

## Task 3: Wire Save Handling

**Files:**
- Create: `src/mynovel/provider_config_server.py`
- Modify: `src/mynovel/dev_server.py`
- Test: `tests/test_provider_config_server.py`

- [ ] **Step 1: Write failing server handling tests**

Add tests for:

- a failed model check returns HTTP 400, does not save `ProviderConfig`, and still saves passed validation fingerprints;
- a second identical submit skips passed checks and reruns only the failed model;
- all passed checks save provider config and return a redirect.

- [ ] **Step 2: Verify RED**

Run: `pixi run pytest tests/test_provider_config_server.py -q`

Expected: FAIL because `provider_config_server.py` does not exist.

- [ ] **Step 3: Implement server helper**

Create `ProviderConfigPostResponse(status, body="", redirect_to=None)`. Implement `handle_provider_config_post(db_path, form, checker=None)`:

1. Parse form with `provider_config_from_form`.
2. Load previous validation metadata.
3. Run `asyncio.run(validate_provider_config(...))`.
4. Save updated validation metadata from passed checks.
5. If report failed, render `render_model_setup_page(db_path, submitted_config, message, validation_report=report)` with HTTP 400.
6. If report passed, save provider config and redirect to `/?message=...`.

Update `dev_server.py` POST `/provider-config` to call this helper and send either redirect or HTML.

- [ ] **Step 4: Verify GREEN**

Run: `pixi run pytest tests/test_provider_config_server.py -q`

Expected: PASS.

## Task 4: Refactor Setup UI

**Files:**
- Modify: `src/mynovel/model_setup_views.py`
- Modify: `src/mynovel/product_views.py`
- Modify: `src/mynovel/home_views.py`
- Modify: `src/mynovel/ui_shell.py`
- Test: `tests/test_product_ui.py`
- Test: `tests/test_product_regressions.py`
- Test: `tests/test_dynamic_ui_regressions.py`

- [ ] **Step 1: Write failing UI tests**

Update or add assertions that:

- `/provider-config` contains fields for `llm_base_url`, `llm_api_key`, `llm_model`, `embedding_model`, and `rerank_model`;
- `llm_api_key` and `rerank_model` are required;
- embedding and rerank reuse checkboxes are checked by default;
- validation report rows render "通过", "失败", and "沿用上次通过结果";
- old copy "重排模型（可选）" is absent.

- [ ] **Step 2: Verify RED**

Run: `pixi run pytest tests/test_product_ui.py::test_model_setup_page_uses_dedicated_configuration_dashboard tests/test_product_regressions.py::test_model_setup_advanced_options_allow_dedicated_embedding_and_rerank_config tests/test_dynamic_ui_regressions.py::test_model_setup_does_not_label_required_embedding_model_as_optional -q`

Expected: FAIL on rerank required status and validation report UI.

- [ ] **Step 3: Implement setup renderer**

Update `render_model_setup_page(..., validation_report=None)` and `render_model_setup_content(..., validation_report=None)`. Replace the advanced-only retrieval section with visible model sections. Keep hidden checkbox values so unchecked reuse posts `0`. Render dedicated fields as required only when reuse is unchecked. Add a right-rail connection checklist from `validation_report`.

Update the hidden first-launch provider form to stop carrying a second full form; keep first launch pointed at `/provider-config` as the setup source of truth.

- [ ] **Step 4: Verify GREEN**

Run: `pixi run pytest tests/test_product_ui.py tests/test_product_regressions.py tests/test_dynamic_ui_regressions.py -q`

Expected: PASS.

## Task 5: Final Verification

**Files:**
- All modified source and tests.

- [ ] **Step 1: Run focused tests**

Run: `pixi run pytest tests/test_provider_config_validation.py tests/test_provider_config_server.py tests/domain/test_provider_config.py tests/test_db.py tests/test_product_ui.py tests/test_product_regressions.py tests/test_dynamic_ui_regressions.py -q`

Expected: PASS.

- [ ] **Step 2: Run lint**

Run: `pixi run ruff check src tests`

Expected: PASS.

- [ ] **Step 3: Check file sizes**

Run: `wc -l src/mynovel/dev_server.py src/mynovel/model_setup_views.py src/mynovel/provider_config_server.py src/mynovel/provider_config_validation.py`

Expected: no file exceeds 1000 lines.
