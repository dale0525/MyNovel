# React Workbench Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every user-facing Python-rendered page with a React/Vite/shadcn SPA while keeping Python as the local API, SQLite, AI workflow, and static-file host.

**Architecture:** Python serves `/api/*`, `/health`, file downloads, and Vite static assets with SPA fallback. React owns routing, layout, setup gating, forms, async states, and all product pages. Existing workflow modules remain in Python; old HTML renderers are removed from browser entrypoints instead of being kept as fallback UI.

**Tech Stack:** Python 3.11, stdlib `http.server`, SQLModel, React, TypeScript, Vite, Tailwind CSS, shadcn/ui, lucide-react, Vitest, Playwright, pixi-managed Node.js.

---

## Scope Rules

Before every task, run:

```bash
git status --short
```

Expected: unrelated existing changes may be present. Stage only files listed in the current task. Do not revert user changes.

Hard constraints:

- `/` must always be a React route after the first frontend cutover task.
- If provider config is missing or not validated, the only visible app UI is setup.
- No old server-rendered page may remain reachable as user fallback.
- Keep touched Python files under 1000 lines.

## File Map

Backend:

- `src/mynovel/dev_server.py`: CLI, server startup, request handler composition.
- `src/mynovel/static_server.py`: static asset and SPA fallback resolution.
- `src/mynovel/frontend_assets.py`: package-safe frontend dist path.
- `src/mynovel/api_errors.py`: JSON response and error envelope.
- `src/mynovel/api_routes.py`: `/api/*` dispatch.
- `src/mynovel/api_serializers.py`: domain object to DTO mapping.
- `src/mynovel/api_provider_config.py`: provider config JSON save/validate.

Frontend:

- `frontend/package.json`, `vite.config.ts`, `tsconfig*.json`, `components.json`: tooling.
- `frontend/src/app/*`: route tree and bootstrap gate.
- `frontend/src/components/layout/*`: setup-only shell and app shell.
- `frontend/src/components/ui/*`: shadcn/ui component source.
- `frontend/src/features/*`: provider config, workbench, open book, books, canon, chapters, quality, updates.
- `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`: API client and DTO types.
- `frontend/src/styles/globals.css`: Tailwind and design tokens.

Tests:

- Python API/static tests under `tests/test_*_api.py` and `tests/test_static_server.py`.
- Frontend unit tests under `frontend/tests/`.
- Browser smoke tests under `frontend/e2e/`.

---

## Task 1: Frontend Tooling Skeleton

**Files:**
- Create: `frontend/package.json`, `frontend/index.html`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/components.json`, `frontend/src/main.tsx`, `frontend/src/app/App.tsx`, `frontend/src/styles/globals.css`
- Modify: `pixi.toml`
- Test: `tests/test_frontend_tooling.py`

- [ ] **Step 1: Write failing tooling tests**

Create `tests/test_frontend_tooling.py`:

```python
from pathlib import Path
import json
import tomllib


def test_frontend_package_has_required_scripts() -> None:
    package = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["dev"] == "vite --host 127.0.0.1"
    assert package["scripts"]["build"] == "tsc -b && vite build"
    assert package["scripts"]["typecheck"] == "tsc -b --pretty false"
    assert package["scripts"]["lint"] == "eslint ."


def test_pixi_exposes_frontend_tasks() -> None:
    config = tomllib.loads(Path("pixi.toml").read_text(encoding="utf-8"))
    assert "nodejs" in config["dependencies"]
    assert config["tasks"]["frontend-dev"] == "npm --prefix frontend run dev"
    assert config["tasks"]["frontend-build"] == "npm --prefix frontend run build"
    assert config["tasks"]["frontend-typecheck"] == "npm --prefix frontend run typecheck"
    assert config["tasks"]["frontend-lint"] == "npm --prefix frontend run lint"
```

- [ ] **Step 2: Run failing tests**

```bash
pixi run pytest tests/test_frontend_tooling.py -v
```

Expected: FAIL because `frontend/package.json` is missing.

- [ ] **Step 3: Add Vite React files**

Create `frontend/package.json` with scripts:

```json
{
  "name": "mynovel-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc -b && vite build",
    "typecheck": "tsc -b --pretty false",
    "lint": "eslint .",
    "test": "vitest run --environment jsdom",
    "e2e": "playwright test"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^5.0.0",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "lucide-react": "^0.468.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router": "^7.0.0",
    "tailwind-merge": "^2.6.0",
    "tailwindcss-animate": "^1.0.7",
    "vite": "^7.0.0"
  },
  "devDependencies": {
    "@playwright/test": "^1.49.0",
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/react": "^16.1.0",
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "eslint": "^9.0.0",
    "eslint-plugin-react-hooks": "^5.0.0",
    "jsdom": "^25.0.0",
    "tailwindcss": "^3.4.17",
    "typescript": "^5.7.0",
    "vitest": "^2.1.0"
  }
}
```

Create `frontend/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  build: { outDir: "dist", emptyOutDir: true },
});
```

Create `frontend/src/main.tsx`:

```tsx
import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "@/app/App";
import "@/styles/globals.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 4: Add pixi tasks**

Add to `pixi.toml`:

```toml
nodejs = ">=22,<23"
frontend-dev = "npm --prefix frontend run dev"
frontend-build = "npm --prefix frontend run build"
frontend-typecheck = "npm --prefix frontend run typecheck"
frontend-lint = "npm --prefix frontend run lint"
frontend-test = "npm --prefix frontend run test"
frontend-e2e = "npm --prefix frontend run e2e"
```

- [ ] **Step 5: Verify and commit**

```bash
pixi run pytest tests/test_frontend_tooling.py -v
pixi run frontend-typecheck
pixi run frontend-build
git add frontend pixi.toml tests/test_frontend_tooling.py
git commit -m "feat: scaffold react frontend"
```

Expected: tests and build PASS.

---

## Task 2: Static SPA Hosting

**Files:**
- Create: `src/mynovel/frontend_assets.py`, `src/mynovel/static_server.py`, `tests/test_static_server.py`
- Modify: `src/mynovel/dev_server.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_static_server.py`:

```python
from http import HTTPStatus
from pathlib import Path
from mynovel.static_server import resolve_spa_response


def test_app_route_serves_index(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    response = resolve_spa_response("/books/1", dist)
    assert response.status == HTTPStatus.OK
    assert response.content_type == "text/html; charset=utf-8"


def test_asset_route_serves_asset(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    response = resolve_spa_response("/assets/app.js", dist)
    assert response.status == HTTPStatus.OK
    assert response.content_type == "text/javascript"


def test_path_traversal_is_not_served(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    assert resolve_spa_response("/assets/../secret.txt", dist).status == HTTPStatus.NOT_FOUND
```

- [ ] **Step 2: Run failing tests**

```bash
pixi run pytest tests/test_static_server.py -v
```

Expected: FAIL because `mynovel.static_server` is missing.

- [ ] **Step 3: Implement static server**

Create `src/mynovel/static_server.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from http import HTTPStatus
from mimetypes import guess_type
from pathlib import Path


@dataclass(frozen=True)
class StaticResponse:
    status: HTTPStatus
    content_type: str
    body: bytes


def resolve_spa_response(path: str, dist_dir: Path) -> StaticResponse:
    if path.startswith("/assets/"):
        asset = (dist_dir / path.removeprefix("/")).resolve()
        root = dist_dir.resolve()
        if root not in asset.parents or not asset.is_file():
            return StaticResponse(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"not found")
        return StaticResponse(HTTPStatus.OK, guess_type(asset.name)[0] or "application/octet-stream", asset.read_bytes())
    index = dist_dir / "index.html"
    if not index.is_file():
        return StaticResponse(HTTPStatus.SERVICE_UNAVAILABLE, "text/plain; charset=utf-8", b"React frontend is not built. Run `pixi run frontend-build`.")
    return StaticResponse(HTTPStatus.OK, "text/html; charset=utf-8", index.read_bytes())
```

Create `src/mynovel/frontend_assets.py`:

```python
from __future__ import annotations
from importlib.resources import files
from pathlib import Path


def frontend_dist_path() -> Path:
    return Path(str(files("mynovel") / "frontend" / "dist"))
```

- [ ] **Step 4: Wire GET fallback**

In `dev_server.py`, route GET in this order:

```python
if parsed.path == "/health":
    self._send_json(build_health_payload(state.db_path))
    return
if parsed.path.startswith("/api/"):
    self._send_api_response(dispatch_api_get(parsed.path, parsed.query, state.db_path))
    return
self._send_static_response(resolve_spa_response(parsed.path, frontend_dist_path()))
```

- [ ] **Step 5: Verify and commit**

```bash
pixi run pytest tests/test_static_server.py tests/test_dev_server.py::test_health_payload_reports_database_path -v
git add src/mynovel/frontend_assets.py src/mynovel/static_server.py src/mynovel/dev_server.py tests/test_static_server.py
git commit -m "feat: serve react spa assets"
```

Expected: PASS.

---

## Task 3: JSON API Foundation

**Files:**
- Create: `src/mynovel/api_errors.py`, `src/mynovel/api_routes.py`, `src/mynovel/api_serializers.py`, `tests/test_api_routes.py`
- Modify: `src/mynovel/dev_server.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_api_routes.py`:

```python
from http import HTTPStatus
from pathlib import Path
from mynovel.api_routes import dispatch_api_get


def test_unknown_api_route_returns_json_error(tmp_path: Path) -> None:
    response = dispatch_api_get("/api/missing", "", tmp_path / "dev.sqlite")
    assert response.status == HTTPStatus.NOT_FOUND
    assert response.body["error"]["code"] == "not_found"


def test_bootstrap_requires_setup_without_provider(tmp_path: Path) -> None:
    response = dispatch_api_get("/api/app/bootstrap", "", tmp_path / "dev.sqlite")
    assert response.body["providerConfigured"] is False
    assert response.body["initialRoute"] == "/setup"
```

- [ ] **Step 2: Implement API primitives**

Create `src/mynovel/api_errors.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any


@dataclass(frozen=True)
class ApiResponse:
    status: HTTPStatus
    body: dict[str, Any]


def api_error(status: HTTPStatus, code: str, message: str, details: dict[str, Any] | None = None) -> ApiResponse:
    return ApiResponse(status, {"error": {"code": code, "message": message, "details": details or {}}})
```

Create `src/mynovel/api_routes.py`:

```python
from __future__ import annotations
from http import HTTPStatus
from pathlib import Path
from mynovel.api_errors import ApiResponse, api_error
from mynovel.api_serializers import app_bootstrap_payload


def dispatch_api_get(path: str, query: str, db_path: Path) -> ApiResponse:
    if path == "/api/app/bootstrap":
        return ApiResponse(HTTPStatus.OK, app_bootstrap_payload(db_path))
    return api_error(HTTPStatus.NOT_FOUND, "not_found", "API route not found.")


def dispatch_api_post(path: str, body: dict, db_path: Path) -> ApiResponse:
    return api_error(HTTPStatus.NOT_FOUND, "not_found", "API route not found.")
```

Create `src/mynovel/api_serializers.py`:

```python
from __future__ import annotations
from pathlib import Path
from sqlmodel import Session
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.repositories import get_provider_config, get_provider_config_validation


def app_bootstrap_payload(db_path: Path) -> dict:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        configured = get_provider_config(session) is not None and get_provider_config_validation(session) is not None
    return {"providerConfigured": configured, "initialRoute": "/" if configured else "/setup", "message": None}
```

- [ ] **Step 3: Wire JSON IO in `dev_server.py`**

Add `_read_json()` and `_send_api_response()`:

```python
def _read_json(self) -> dict:
    length = int(self.headers.get("Content-Length", "0"))
    return {} if length == 0 else json.loads(self.rfile.read(length).decode("utf-8"))


def _send_api_response(self, response: ApiResponse) -> None:
    payload = json.dumps(response.body, ensure_ascii=False).encode("utf-8")
    self.send_response(response.status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(payload)))
    self.end_headers()
    self.wfile.write(payload)
```

- [ ] **Step 4: Verify and commit**

```bash
pixi run pytest tests/test_api_routes.py tests/test_static_server.py -v
git add src/mynovel/api_errors.py src/mynovel/api_routes.py src/mynovel/api_serializers.py src/mynovel/dev_server.py tests/test_api_routes.py
git commit -m "feat: add json api foundation"
```

Expected: PASS.

---

## Task 4: Provider Config API

**Files:**
- Create: `src/mynovel/api_provider_config.py`, `tests/test_provider_config_api.py`
- Modify: `src/mynovel/api_routes.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_provider_config_api.py`:

```python
from http import HTTPStatus
from pathlib import Path
from sqlmodel import Session
from mynovel.api_provider_config import save_provider_config_json
from mynovel.db import create_engine_for_path
from mynovel.domain.models import ProviderConfig
from mynovel.domain.repositories import get_provider_config


class FakeChecker:
    def __init__(self, failures: set[str] | None = None) -> None:
        self.failures = failures or set()
        self.calls: list[str] = []
    async def check_chat(self, config: ProviderConfig) -> None:
        self.calls.append("llm")
        if "llm" in self.failures: raise RuntimeError("chat failed")
    async def check_embedding(self, config: ProviderConfig) -> None:
        self.calls.append("embedding")
        if "embedding" in self.failures: raise RuntimeError("embedding failed")
    async def check_rerank(self, config: ProviderConfig) -> None:
        self.calls.append("rerank")
        if "rerank" in self.failures: raise RuntimeError("rerank failed")


def test_failure_does_not_save_config(tmp_path: Path) -> None:
    response = save_provider_config_json(tmp_path / "dev.sqlite", _payload(), FakeChecker({"rerank"}))
    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["error"]["code"] == "provider_validation_failed"
    with Session(create_engine_for_path(tmp_path / "dev.sqlite")) as session:
        assert get_provider_config(session) is None


def test_second_save_only_retests_failure(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    save_provider_config_json(db_path, _payload(), FakeChecker({"rerank"}))
    checker = FakeChecker()
    assert save_provider_config_json(db_path, _payload(), checker).status == HTTPStatus.OK
    assert checker.calls == ["rerank"]


def _payload() -> dict:
    return {"llmBaseUrl": "https://api.test/v1", "llmApiKey": "sk", "llmModel": "gpt", "embeddingUseLlmCredentials": True, "embeddingModel": "embed", "rerankUseLlmCredentials": True, "rerankModel": "rerank"}
```

- [ ] **Step 2: Implement JSON provider config**

Create `src/mynovel/api_provider_config.py` with `provider_config_from_json()`, `provider_config_payload()`, `validation_report_payload()`, `get_provider_config_json()`, and `save_provider_config_json()`. Reuse `validate_provider_config()`, `save_provider_config_validation()`, and `save_provider_config()`. Failed validation returns status `400` with `error.code == "provider_validation_failed"` and the validation results; passed validation saves config and returns status `200`.

Route:

```python
if path == "/api/provider-config":
    return get_provider_config_json(db_path)
if path in {"/api/provider-config", "/api/provider-config/validate"}:
    return save_provider_config_json(db_path, body)
```

- [ ] **Step 3: Verify and commit**

```bash
pixi run pytest tests/test_provider_config_api.py tests/test_provider_config_validation.py tests/test_provider_config_server.py -v
git add src/mynovel/api_provider_config.py src/mynovel/api_routes.py tests/test_provider_config_api.py
git commit -m "feat: expose provider config api"
```

Expected: PASS.

---

## Task 5: Bootstrap Gate and Setup UI

**Files:**
- Create: `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`, `frontend/src/app/BootstrapGate.tsx`, `frontend/src/components/layout/SetupOnlyShell.tsx`, `frontend/src/features/provider-config/*`, `frontend/tests/provider-config-page.test.tsx`
- Modify: `frontend/src/app/App.tsx`

- [ ] **Step 1: Write failing frontend tests**

Create `frontend/tests/provider-config-page.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ProviderConfigPage } from "@/features/provider-config/ProviderConfigPage";

test("setup hides inherited credential fields by default", () => {
  render(<ProviderConfigPage />);
  expect(screen.getByLabelText("Embedding 使用 LLM 的 base url 和 api key")).toBeChecked();
  expect(screen.getByLabelText("Rerank 使用 LLM 的 base url 和 api key")).toBeChecked();
  expect(screen.queryByLabelText("Embedding base url")).not.toBeInTheDocument();
});

test("validation failure stays on setup", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ error: { code: "provider_validation_failed", message: "模型连接测试未全部通过。", details: {} }, validation: { passed: false, results: [{ kind: "rerank", label: "重排模型", status: "failed", message: "rerank failed" }] } }, { status: 400 })));
  render(<ProviderConfigPage />);
  fireEvent.change(screen.getByLabelText("Base url"), { target: { value: "https://api.test/v1" } });
  fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk" } });
  fireEvent.change(screen.getByLabelText("Model name"), { target: { value: "gpt" } });
  fireEvent.change(screen.getByLabelText("Embedding model name"), { target: { value: "embed" } });
  fireEvent.change(screen.getByLabelText("Rerank model name"), { target: { value: "rerank" } });
  fireEvent.click(screen.getByRole("button", { name: "测试并保存配置" }));
  await waitFor(() => expect(screen.getByText("rerank failed")).toBeInTheDocument());
});
```

- [ ] **Step 2: Implement API client and setup page**

Create `frontend/src/lib/api.ts`:

```ts
export class ApiError extends Error {
  constructor(message: string, public code: string, public details: Record<string, unknown>) {
    super(message);
  }
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, { method: "POST", headers: { Accept: "application/json", "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const payload = await response.json();
  if (!response.ok) throw new ApiError(payload.error?.message ?? "请求失败。", payload.error?.code ?? "request_failed", payload.error?.details ?? {});
  return payload as T;
}
```

Create `ProviderConfigPage.tsx` as a controlled form with fields `Base url`, `API key`, `Model name`, `Embedding model name`, `Rerank model name`, inherited credential switches, validation result list, loading state, and submit text `测试并保存配置`. On success navigate to `/`; on failure render messages and stay on setup.

- [ ] **Step 3: Verify and commit**

```bash
pixi run frontend-test -- provider-config-page
pixi run frontend-typecheck
git add frontend
git commit -m "feat: build provider setup page"
```

Expected: PASS.

---

## Task 6: Workbench API and App Shell

**Files:**
- Modify: `src/mynovel/api_serializers.py`, `src/mynovel/api_routes.py`
- Create: `tests/test_workbench_api.py`, `frontend/src/components/layout/AppShell.tsx`, `frontend/src/features/workbench/WorkbenchPage.tsx`

- [ ] **Step 1: Write failing API tests**

Create tests for `/api/app/bootstrap` with valid `ProviderConfigValidation` returning `initialRoute == "/"`, and `/api/books` returning recent books. Use `Book(title="长夜图书馆", genre="奇幻", audience="男频")`.

- [ ] **Step 2: Implement serializers**

Add:

```python
def book_payload(book: Book) -> dict:
    return {"id": book.id, "title": book.title, "genre": book.genre, "audience": book.audience, "status": book.status.value, "premise": book.premise}


def books_payload(db_path: Path) -> dict:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        books = list(session.exec(select(Book).order_by(Book.created_at.desc()).limit(20)))
    return {"books": [book_payload(book) for book in books]}
```

Route `GET /api/books`.

- [ ] **Step 3: Implement shell**

Create `AppShell.tsx` with nav links: 工作台, 开书, 项目, 章节, 可信设定, 质量, 设置. Create `WorkbenchPage.tsx` with loading, error, empty, and next-action states from `/api/books`.

- [ ] **Step 4: Verify and commit**

```bash
pixi run pytest tests/test_workbench_api.py tests/test_api_routes.py -v
pixi run frontend-typecheck
git add src/mynovel/api_serializers.py src/mynovel/api_routes.py tests/test_workbench_api.py frontend
git commit -m "feat: add react workbench shell"
```

Expected: PASS.

---

## Task 7: Open Book and Blueprint Flow

**Files:**
- Modify: `src/mynovel/api_routes.py`, `src/mynovel/api_serializers.py`
- Create: `tests/test_open_book_api.py`, `frontend/src/features/open-book/OpenBookPage.tsx`, `frontend/src/features/open-book/BlueprintPage.tsx`

- [ ] **Step 1: Write failing tests**

Test `POST /api/open-book` returns `provider_not_configured` without provider and `idea_required` for blank idea. Test `GET /api/blueprints/:id` returns status, content, parse error, and error message.

- [ ] **Step 2: Implement API**

Reuse `_book_idea_from_form()`, `create_blueprint_job()`, `_start_blueprint_job()`, `create_revision_blueprint_job()`, and `accept_blueprint_for_foundation_review()`. Successful open book returns:

```python
ApiResponse(HTTPStatus.ACCEPTED, {"blueprintId": blueprint_id, "redirectTo": f"/blueprints/{blueprint_id}"})
```

- [ ] **Step 3: Implement pages**

`OpenBookPage.tsx` submits idea presets to `/api/open-book`. `BlueprintPage.tsx` polls pending/running jobs, renders failed retry, succeeded title selection, revision notes, and accept action.

- [ ] **Step 4: Verify and commit**

```bash
pixi run pytest tests/test_open_book_api.py tests/test_dev_server.py::test_book_idea_from_form_keeps_idea_required_and_uses_visible_presets -v
pixi run frontend-typecheck
git add src/mynovel/api_routes.py src/mynovel/api_serializers.py tests/test_open_book_api.py frontend/src/features/open-book
git commit -m "feat: migrate open book flow"
```

Expected: PASS.

---

## Task 8: Book Workspace and Trusted State

**Files:**
- Modify: `src/mynovel/api_routes.py`, `src/mynovel/api_serializers.py`
- Create: `tests/test_book_state_api.py`, `frontend/src/features/books/BookWorkspacePage.tsx`, `frontend/src/features/canon/TrustedStatePage.tsx`

- [ ] **Step 1: Write failing tests**

Test `GET /api/books/:id` returns book, chapters, latest canon, run traces, and volume plans. Test `GET /api/books/:id/state` returns canon content and pending canon proposal revision if query includes `revisionId`.

- [ ] **Step 2: Implement serializers and routes**

Add `chapter_payload()`, `canon_payload()`, `run_trace_payload()`, `volume_plan_payload()`, `book_detail_payload()`, and `trusted_state_payload()`. Route `GET /api/books/:id`, `GET /api/books/:id/state`, `POST /api/books/:id/state/lock`, and canon proposal actions under `/api/books/:id/canon-proposals/*`.

- [ ] **Step 3: Implement pages**

`BookWorkspacePage.tsx` shows current task, chapter queue, trusted state summary, and recent AI progress. `TrustedStatePage.tsx` shows canon sections, locked state, revision proposal changes, blocked sections, apply, discard, and revise actions.

- [ ] **Step 4: Verify and commit**

```bash
pixi run pytest tests/test_book_state_api.py tests/workflows/test_canon_proposal.py -v
pixi run frontend-typecheck
git add src/mynovel/api_routes.py src/mynovel/api_serializers.py tests/test_book_state_api.py frontend/src/features/books frontend/src/features/canon
git commit -m "feat: migrate book workspace api"
```

Expected: PASS.

---

## Task 9: Chapter Run and Review Flow

**Files:**
- Modify: `src/mynovel/api_routes.py`, `src/mynovel/api_serializers.py`
- Create: `tests/test_chapter_api.py`, `frontend/src/features/chapters/ChapterPage.tsx`, `frontend/src/features/chapters/ChapterStageBoard.tsx`, `frontend/src/features/chapters/ChapterReviewActions.tsx`

- [ ] **Step 1: Write failing tests**

Test `GET /api/chapters/:id` returns chapter, book, sibling chapters, canon, traces, and `stageSlots`. Test unknown or invalid action returns `chapter_action_failed`.

- [ ] **Step 2: Implement API**

Route:

```text
GET /api/chapters/:chapterId
POST /api/chapters/:chapterId/run
POST /api/books/:bookId/chapters/run-batch
POST /api/chapters/:chapterId/request-revision
POST /api/chapters/:chapterId/repair
POST /api/chapters/:chapterId/edit
POST /api/chapters/:chapterId/approve
GET /api/chapters/:chapterId/export.txt
```

Reuse existing chapter workflow functions. Add `chapter_stage_slots()` returning plan, context, draft, delta, and audit readiness.

- [ ] **Step 3: Implement pages**

`ChapterPage.tsx` polls every 3000ms while status is `running`, shows result report before text, then manual edit, repair, approve, and export actions. Use empty states for missing state delta and audit report rather than fake data.

- [ ] **Step 4: Verify and commit**

```bash
pixi run pytest tests/test_chapter_api.py tests/test_dev_server.py::test_queue_chapter_run_marks_chapter_running_without_blocking -v
pixi run frontend-typecheck
git add src/mynovel/api_routes.py src/mynovel/api_serializers.py tests/test_chapter_api.py frontend/src/features/chapters
git commit -m "feat: migrate chapter workflow ui"
```

Expected: PASS.

---

## Task 10: Quality, Import, Updates, and Downloads

**Files:**
- Modify: `src/mynovel/api_routes.py`, `src/mynovel/api_serializers.py`
- Create: `tests/test_secondary_api.py`, `frontend/src/features/quality/QualityPage.tsx`, `frontend/src/features/books/ImportBookPage.tsx`, `frontend/src/features/updates/UpdatesPage.tsx`

- [ ] **Step 1: Write failing tests**

Test invalid import returns `import_failed`. Test unknown quality snapshot book returns `quality_action_failed`. Test update check returns JSON instead of HTML.

- [ ] **Step 2: Implement API**

Route import, quality style assets, deconstruction, snapshots, updates, book exports, and chapter export through `/api/*`. Use existing `import_book_json()`, `create_style_asset()`, `deconstruct_reference_text()`, `generate_quality_snapshot()`, `handle_check_update()`, `handle_stage_update()`, `export_book_markdown()`, `export_book_json()`, and `export_chapter_text()`.

- [ ] **Step 3: Implement pages**

Create React pages for quality center, import, and updates with loading, error, empty, and success states. File downloads use normal anchor URLs to API download endpoints.

- [ ] **Step 4: Verify and commit**

```bash
pixi run pytest tests/test_secondary_api.py tests/test_update_check.py tests/test_quality_ui.py -v
pixi run frontend-typecheck
git add src/mynovel/api_routes.py src/mynovel/api_serializers.py tests/test_secondary_api.py frontend/src/features/quality frontend/src/features/books/ImportBookPage.tsx frontend/src/features/updates
git commit -m "feat: migrate secondary product flows"
```

Expected: PASS after HTML-only assertions are migrated to API or frontend tests.

---

## Task 11: Remove Old User HTML Entry Points

**Files:**
- Modify: `src/mynovel/dev_server.py`
- Delete or convert: `src/mynovel/home_views.py`, `src/mynovel/model_setup_views.py`, `src/mynovel/product_views.py`, `src/mynovel/open_book_views.py`, `src/mynovel/chapter_review_views.py`, `src/mynovel/workspace_views.py`, `src/mynovel/quality_views.py`, `src/mynovel/update_views.py`
- Update: tests importing `render_*`

- [ ] **Step 1: Write failing no-old-page tests**

Create `tests/test_no_old_user_pages.py`:

```python
from pathlib import Path


def test_dev_server_does_not_import_html_renderers() -> None:
    source = Path("src/mynovel/dev_server.py").read_text(encoding="utf-8")
    assert "render_home" not in source
    assert "render_model_setup_page" not in source
    assert "render_book_workspace" not in source
    assert "render_chapter_review" not in source


def test_no_send_html_user_route_remains() -> None:
    source = Path("src/mynovel/dev_server.py").read_text(encoding="utf-8")
    assert "_send_html(" not in source
```

- [ ] **Step 2: Remove old dispatch**

In `dev_server.py`, keep `/health`, `/api/*`, static assets, SPA fallback, and API file responses. Remove direct GET branches for `/books/new`, `/provider-config`, `/book/*`, `/chapter/*`, `/blueprint/*`, `/updates`. Remove old POST form branches outside `/api/*`.

- [ ] **Step 3: Migrate old tests**

Convert old render string assertions into API serialization assertions or frontend tests. Remove `tests/test_product_ui_workspace.py` when equivalent API/frontend coverage exists. Keep workflow tests that call pure business functions.

- [ ] **Step 4: Verify and commit**

```bash
wc -l src/mynovel/dev_server.py
pixi run pytest tests/test_no_old_user_pages.py tests/test_dev_server.py tests/test_api_routes.py -v
git add src/mynovel tests
git commit -m "refactor: remove old server rendered pages"
```

Expected: `dev_server.py` is below 1000 lines and tests PASS.

---

## Task 12: Packaging and Desktop Build

**Files:**
- Modify: `pyproject.toml`, `pixi.toml`, `src/mynovel/release_package.py`, `tests/test_package.py`, `tests/test_desktop_release.py`

- [ ] **Step 1: Write failing package test**

Add:

```python
def test_frontend_dist_included_as_package_data() -> None:
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_data = config["tool"]["setuptools"]["package-data"]["mynovel"]
    assert "frontend/dist/index.html" in package_data
    assert "frontend/dist/assets/*" in package_data
```

- [ ] **Step 2: Package frontend dist**

Add package data:

```toml
mynovel = ["prompts/assets/*.yaml", "frontend/dist/index.html", "frontend/dist/assets/*"]
```

Make `frontend-build` copy `frontend/dist` to `src/mynovel/frontend/dist`. Keep `desktop-build` dependent on `frontend-build` and `--collect-all mynovel`.

- [ ] **Step 3: Verify and commit**

```bash
pixi run frontend-build
pixi run pytest tests/test_package.py tests/test_desktop_release.py -v
git add pyproject.toml pixi.toml src/mynovel/release_package.py tests/test_package.py tests/test_desktop_release.py
git commit -m "build: package react frontend"
```

Expected: PASS and `src/mynovel/frontend/dist/index.html` exists.

---

## Task 13: Browser Smoke Tests

**Files:**
- Create: `frontend/e2e/setup-gate.spec.ts`, `frontend/e2e/workbench.spec.ts`
- Modify: `frontend/package.json`, `pixi.toml`

- [ ] **Step 1: Write setup smoke**

Create `frontend/e2e/setup-gate.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("unconfigured app shows only model setup", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "连接你的 AI 模型" })).toBeVisible();
  await expect(page.getByText("工作台")).toHaveCount(0);
  await expect(page.getByText("项目")).toHaveCount(0);
});
```

- [ ] **Step 2: Write configured smoke**

Create `frontend/e2e/workbench.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("configured app opens workbench shell", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("工作台")).toBeVisible();
  await expect(page.getByText("开书")).toBeVisible();
  await expect(page.getByText("设置")).toBeVisible();
});
```

- [ ] **Step 3: Verify and commit**

```bash
pixi run frontend-e2e
git add frontend/e2e frontend/package.json pixi.toml
git commit -m "test: add frontend smoke tests"
```

Expected: PASS with configured and unconfigured DB fixtures.

---

## Task 14: Final Verification

**Files:**
- No planned file changes.

- [ ] **Step 1: Run all verification**

```bash
pixi run test
pixi run lint
pixi run typecheck
pixi run frontend-test
pixi run frontend-typecheck
pixi run frontend-lint
pixi run frontend-build
pixi run frontend-e2e
```

Expected: all commands exit 0.

- [ ] **Step 2: Confirm old HTML route removal**

```bash
rg -n "render_home|render_model_setup_page|render_book_workspace|render_chapter_review|_send_html\\(" src/mynovel tests
```

Expected: no matches for user route rendering.

- [ ] **Step 3: Confirm file sizes**

```bash
wc -l src/mynovel/dev_server.py src/mynovel/api_routes.py src/mynovel/api_serializers.py
```

Expected: every listed file is below 1000 lines.

- [ ] **Step 4: Confirm clean migration state**

```bash
git status --short
```

Expected: no output. If output exists, stop and inspect it with `git diff --name-only`; do not create a final cleanup commit until the changed files are identified and assigned to a concrete migration task.

---

## Self-Review

- Spec coverage: React/Vite/shadcn, setup-only startup, three-model validation, JSON API, SPA fallback, workbench, open book, trusted state, chapters, quality, import, updates, packaging, old-page removal, and verification are covered.
- Old UI constraint: Task 11 removes old server-rendered user entrypoints; no task keeps old pages as fallback.
- Provider validation: Task 4 reuses existing fingerprint-based retest behavior.
- File-size constraint: The plan file is under 1000 lines, and implementation tasks check Python file sizes.
- Testing: Each implementation area starts with a failing test and includes verification before commit.
