# Electron Desktop Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and release MyNovel as a real Electron desktop application that opens a native app window and bundles the existing Python backend.

**Architecture:** Keep the Python backend and Vite frontend intact. Add an Electron main process that starts a bundled PyInstaller backend executable, waits for `/health`, opens a `BrowserWindow`, and stops the backend on quit. Replace the Windows release installer path with Electron Builder NSIS output while preserving release checksums and update metadata.

**Tech Stack:** Python 3.11, PyInstaller, pytest, Vite, TypeScript, Vitest, Electron, Electron Builder, GitHub Actions, pixi.
---

## File Structure
- Create `frontend/electron/backend.ts`, `frontend/electron/main.ts`, and `frontend/tests/electron-backend.test.ts`: backend orchestration helpers, Electron entrypoint, and Vitest coverage.
- Create `frontend/tsconfig.electron.json` and `frontend/electron-builder.yml`: Electron TypeScript build and packaging config.
- Modify `frontend/package.json`: add Electron scripts, Electron dependencies, and `main`.
- Modify `frontend/tsconfig.json` and `frontend/eslint.config.js`: include Electron source in typecheck and linting.
- Modify `src/mynovel/release_package.py`: add a `write-metadata` CLI subcommand for Electron Builder artifacts.
- Modify `tests/test_desktop_release.py`, `tests/test_github_actions.py`, and `tests/test_frontend_tooling.py`: update packaging, workflow, and frontend tooling assertions.
- Modify `.github/workflows/release.yml`: build `MyNovelBackend`, package with Electron Builder, publish `.exe` artifacts.

---

### Task 1: Add Metadata CLI For Electron Builder Artifacts

**Files:**
- Modify: `src/mynovel/release_package.py`
- Modify: `tests/test_desktop_release.py`

- [ ] **Step 1: Write the failing metadata command test**

Add `main` to the existing import from `mynovel.release_package` and add this test near the metadata tests in `tests/test_desktop_release.py`:

```python
def test_release_metadata_command_writes_existing_electron_artifact_metadata(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "MyNovel-windows-x64.exe"
    artifact.write_bytes(b"sample electron installer")

    main(
        [
            "write-metadata",
            "--dist",
            str(tmp_path),
            "--artifact",
            str(artifact),
            "--version",
            "v0.1.9",
            "--platform",
            "windows-x64",
        ]
    )

    update = json.loads((tmp_path / "update-windows-x64.json").read_text(encoding="utf-8"))
    checksum = (tmp_path / "checksums-windows-x64.sha256").read_text(encoding="utf-8")

    assert update["version"] == "0.1.9"
    assert update["platform"] == "windows-x64"
    assert update["url"] == "MyNovel-windows-x64.exe"
    assert update["size_bytes"] == len(b"sample electron installer")
    assert checksum.endswith("  MyNovel-windows-x64.exe\n")
```

Also add `import json` at the top of `tests/test_desktop_release.py`.

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
pixi run pytest tests/test_desktop_release.py::test_release_metadata_command_writes_existing_electron_artifact_metadata -q
```

Expected: FAIL because `write-metadata` is not a supported `release_package` subcommand yet.

- [ ] **Step 3: Implement the metadata command**

In `src/mynovel/release_package.py`, route the new subcommand before the existing package parser:

```python
def main(argv: list[str] | None = None) -> None:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args[:1] == ["sync-frontend-dist"]:
        _sync_frontend_dist_command(raw_args[1:])
        return
    if raw_args[:1] == ["write-metadata"]:
        _write_metadata_command(raw_args[1:])
        return

    parser = argparse.ArgumentParser(description="Create unsigned native MyNovel installer assets.")
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--version", default=os.environ.get("GITHUB_REF_NAME", "0.0.0"))
    parser.add_argument("--platform", default=_default_platform())
    args = parser.parse_args(raw_args)

    version = normalize_release_version(args.version)
    artifact = package_native_installer(args.dist, version, args.platform)
    metadata = _write_metadata(args.dist, artifact, version, args.platform)
    print(f"Packaged {artifact}")
    print(f"Wrote {metadata}")
```

Add this helper below `_sync_frontend_dist_command`:

```python
def _write_metadata_command(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Write release metadata for an installer asset.")
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--platform", required=True)
    args = parser.parse_args(argv)

    version = normalize_release_version(args.version)
    metadata = _write_metadata(args.dist, args.artifact, version, args.platform)
    print(f"Wrote {metadata}")
```

- [ ] **Step 4: Run the focused tests**

Run:

```powershell
pixi run pytest tests/test_desktop_release.py::test_release_metadata_command_writes_existing_electron_artifact_metadata tests/test_desktop_release.py::test_release_metadata_checksum_uses_lf_on_windows_text_mode -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add src/mynovel/release_package.py tests/test_desktop_release.py; git commit -m "Add release metadata command for Electron artifacts"`

---

### Task 2: Add Electron Package Contract

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/tsconfig.electron.json`
- Modify: `frontend/tsconfig.json`
- Modify: `frontend/eslint.config.js`
- Modify: `tests/test_frontend_tooling.py`

- [ ] **Step 1: Write failing package/config assertions**

In `tests/test_frontend_tooling.py`, extend `test_frontend_package_has_required_scripts` with:

```python
    assert package["main"] == "dist-electron/main.js"
    assert package["scripts"]["build:electron-main"] == "tsc -p tsconfig.electron.json"
    assert package["scripts"]["electron:build"] == (
        "npm run build:electron-main && electron-builder --config electron-builder.yml"
    )
    assert package["scripts"]["electron:dev"] == "npm run build:electron-main && electron ."
    assert "electron" in package["devDependencies"]
    assert "electron-builder" in package["devDependencies"]
```

Extend `test_frontend_tsconfig_separates_browser_and_node_projects` with:

```python
    electron = json.loads(Path("frontend/tsconfig.electron.json").read_text(encoding="utf-8"))

    assert root["references"] == [
        {"path": "./tsconfig.app.json"},
        {"path": "./tsconfig.node.json"},
        {"path": "./tsconfig.electron.json"},
    ]
    assert electron["extends"] == "./tsconfig.node.json"
    assert electron["compilerOptions"]["outDir"] == "dist-electron"
    assert electron["compilerOptions"]["rootDir"] == "electron"
    assert electron["compilerOptions"]["noEmit"] is False
    assert electron["include"] == ["electron/**/*.ts"]
```

Update the earlier exact `root["references"]` assertion in the same test so it expects all three references.

Add this assertion to `test_frontend_config_files_support_tooling`:

```python
    assert '"electron/**/*.ts"' in eslint_config
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
pixi run pytest tests/test_frontend_tooling.py::test_frontend_package_has_required_scripts tests/test_frontend_tooling.py::test_frontend_tsconfig_separates_browser_and_node_projects tests/test_frontend_tooling.py::test_frontend_config_files_support_tooling -q
```

Expected: FAIL because Electron scripts, dependencies, and TypeScript config do not exist.

- [ ] **Step 3: Update frontend package scripts and dependencies**

Modify `frontend/package.json`:

```json
{
  "main": "dist-electron/main.js",
  "scripts": {
    "build:electron-main": "tsc -p tsconfig.electron.json",
    "electron:build": "npm run build:electron-main && electron-builder --config electron-builder.yml",
    "electron:dev": "npm run build:electron-main && electron ."
  },
  "devDependencies": {
    "electron": "^35.0.0",
    "electron-builder": "^26.0.0"
  }
}
```

Keep all existing scripts, dependencies, and devDependencies unchanged unless shown above.

- [ ] **Step 4: Add Electron TypeScript project**

Create `frontend/tsconfig.electron.json`:

```json
{
  "extends": "./tsconfig.node.json",
  "compilerOptions": {
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "noEmit": false,
    "outDir": "dist-electron",
    "rootDir": "electron",
    "types": ["node", "electron"]
  },
  "include": ["electron/**/*.ts"]
}
```

Modify `frontend/tsconfig.json`:

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" },
    { "path": "./tsconfig.electron.json" }
  ]
}
```

Modify the ESLint file glob in `frontend/eslint.config.js`:

```javascript
  {
    files: ["src/**/*.{ts,tsx}", "electron/**/*.ts", "*.config.ts"],
    languageOptions: {
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      "react-hooks": reactHooks,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
    },
  },
```

- [ ] **Step 5: Run the focused tests**

Run:

```powershell
pixi run pytest tests/test_frontend_tooling.py::test_frontend_package_has_required_scripts tests/test_frontend_tooling.py::test_frontend_tsconfig_separates_browser_and_node_projects tests/test_frontend_tooling.py::test_frontend_config_files_support_tooling -q
```

Expected: PASS.

- [ ] **Step 6: Install frontend dependencies through pixi**

Run:

```powershell
pixi run npm install --package-lock=false
```

Working directory: `frontend`.

Expected: npm installs Electron and Electron Builder under `frontend/node_modules/` without creating a committed package lock.

- [ ] **Step 7: Commit**

Run: `git add frontend/package.json frontend/tsconfig.electron.json frontend/tsconfig.json frontend/eslint.config.js tests/test_frontend_tooling.py; git commit -m "Add Electron frontend packaging contract"`

---

### Task 3: Implement Testable Backend Process Helpers

**Files:**
- Create: `frontend/tests/electron-backend.test.ts`
- Create: `frontend/electron/backend.ts`

- [ ] **Step 1: Write failing Vitest tests**

Create `frontend/tests/electron-backend.test.ts`:

```typescript
// @vitest-environment node
import path from "node:path";
import { describe, expect, test, vi } from "vitest";
import {
  backendExecutableName,
  createBackendArgs,
  createBackendUrl,
  resolveBackendExecutable,
  startBackend,
  stopBackend,
  waitForBackendHealth,
  type BackendProcess,
} from "../electron/backend";

describe("Electron backend helpers", () => {
  test("uses platform-specific backend executable names", () => {
    expect(backendExecutableName("win32")).toBe("MyNovelBackend.exe");
    expect(backendExecutableName("darwin")).toBe("MyNovelBackend");
    expect(backendExecutableName("linux")).toBe("MyNovelBackend");
  });

  test("resolves backend executable from Electron resources", () => {
    expect(resolveBackendExecutable("C:\\Program Files\\MyNovel\\resources", "win32")).toBe(
      path.join("C:\\Program Files\\MyNovel\\resources", "backend", "MyNovelBackend.exe"),
    );
  });

  test("creates backend args that prevent browser launch and force the selected port", () => {
    expect(createBackendArgs({ host: "127.0.0.1", port: 8765 })).toEqual([
      "--host",
      "127.0.0.1",
      "--port",
      "8765",
      "--strict-port",
      "--no-open",
    ]);
  });

  test("starts backend with hidden child process options", () => {
    const child = {
      killed: false,
      kill: vi.fn(() => true),
      once: vi.fn(),
    } as unknown as BackendProcess;
    const spawnBackend = vi.fn(() => child);

    const started = startBackend({
      executable: "MyNovelBackend.exe",
      host: "127.0.0.1",
      port: 8765,
      spawnBackend,
    });

    expect(started).toBe(child);
    expect(spawnBackend).toHaveBeenCalledWith(
      "MyNovelBackend.exe",
      ["--host", "127.0.0.1", "--port", "8765", "--strict-port", "--no-open"],
      { stdio: "ignore", windowsHide: true },
    );
  });

  test("waits until backend health endpoint responds ok", async () => {
    let attempts = 0;
    const fetchImpl = vi.fn(async () => {
      attempts += 1;
      return { ok: attempts === 2 };
    });

    await waitForBackendHealth(createBackendUrl("127.0.0.1", 8765, "/health"), {
      fetchImpl,
      intervalMs: 1,
      timeoutMs: 100,
    });

    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  test("stops a running backend process", () => {
    const child = {
      killed: false,
      kill: vi.fn(() => true),
      once: vi.fn(),
    } as unknown as BackendProcess;

    stopBackend(child);

    expect(child.kill).toHaveBeenCalledWith();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
pixi run npm run test -- electron-backend.test.ts
```

Working directory: `frontend`.

Expected: FAIL because `frontend/electron/backend.ts` does not exist.

- [ ] **Step 3: Implement backend helpers**

Create `frontend/electron/backend.ts`:

```typescript
import { spawn, type ChildProcess, type SpawnOptions } from "node:child_process";
import net from "node:net";
import path from "node:path";

export const DEFAULT_BACKEND_HOST = "127.0.0.1";
export const DEFAULT_BACKEND_PORT = 8765;

export type BackendProcess = Pick<ChildProcess, "kill" | "killed" | "once">;
export type SpawnBackend = (
  executable: string,
  args: string[],
  options: SpawnOptions,
) => BackendProcess;

export function backendExecutableName(platform: NodeJS.Platform = process.platform): string {
  return platform === "win32" ? "MyNovelBackend.exe" : "MyNovelBackend";
}

export function resolveBackendExecutable(
  resourcesPath: string,
  platform: NodeJS.Platform = process.platform,
): string {
  return path.join(resourcesPath, "backend", backendExecutableName(platform));
}

export function createBackendArgs(options: { host: string; port: number }): string[] {
  return ["--host", options.host, "--port", String(options.port), "--strict-port", "--no-open"];
}

export function createBackendUrl(host: string, port: number, pathname = "/"): string {
  return new URL(pathname, `http://${host}:${port}`).toString();
}

export async function findAvailablePort(
  host = DEFAULT_BACKEND_HOST,
  startPort = DEFAULT_BACKEND_PORT,
  attempts = 20,
): Promise<number> {
  for (let offset = 0; offset < attempts; offset += 1) {
    const port = startPort + offset;
    if (await canListen(host, port)) {
      return port;
    }
  }
  throw new Error(`No available port found from ${startPort}.`);
}

export function startBackend(options: {
  executable: string;
  host: string;
  port: number;
  spawnBackend?: SpawnBackend;
}): BackendProcess {
  const spawnBackend = options.spawnBackend !== undefined ? options.spawnBackend : spawn;
  return spawnBackend(options.executable, createBackendArgs(options), {
    stdio: "ignore",
    windowsHide: true,
  });
}

export async function waitForBackendHealth(
  healthUrl: string,
  options: { fetchImpl?: typeof fetch; intervalMs?: number; timeoutMs?: number } = {},
): Promise<void> {
  const fetchImpl = options.fetchImpl !== undefined ? options.fetchImpl : fetch;
  const intervalMs = options.intervalMs !== undefined ? options.intervalMs : 250;
  const timeoutMs = options.timeoutMs !== undefined ? options.timeoutMs : 15_000;
  const deadline = Date.now() + timeoutMs;

  while (Date.now() <= deadline) {
    try {
      const response = await fetchImpl(healthUrl);
      if (response.ok) {
        return;
      }
    } catch {
      // Backend is still starting.
    }
    await delay(intervalMs);
  }

  throw new Error(`Backend did not become healthy at ${healthUrl}.`);
}

export function stopBackend(backend: BackendProcess | null): void {
  if (backend && !backend.killed) {
    backend.kill();
  }
}

function canListen(host: string, port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => server.close(() => resolve(true)));
    server.listen(port, host);
  });
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}
```

- [ ] **Step 4: Run the focused Vitest file**

Run:

```powershell
pixi run npm run test -- electron-backend.test.ts
```

Working directory: `frontend`.

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add frontend/electron/backend.ts frontend/tests/electron-backend.test.ts; git commit -m "Add Electron backend process helpers"`

---

### Task 4: Add Electron Main Process And Builder Config

**Files:**
- Create: `frontend/electron/main.ts`
- Create: `frontend/electron-builder.yml`
- Modify: `tests/test_frontend_tooling.py`

- [ ] **Step 1: Write failing static assertions**

Add this test to `tests/test_frontend_tooling.py`:

```python
def test_electron_main_process_and_builder_config_are_packaged_for_backend() -> None:
    main_process = Path("frontend/electron/main.ts").read_text(encoding="utf-8")
    builder = yaml.safe_load(Path("frontend/electron-builder.yml").read_text(encoding="utf-8"))

    for token in (
        'from "electron"',
        "BrowserWindow",
        "startBackend",
        "waitForBackendHealth",
        "resolveBackendExecutable",
        "stopBackend",
        "nodeIntegration: false",
        "contextIsolation: true",
    ):
        assert token in main_process

    assert builder["appId"] == "com.mynovel.app"
    assert builder["productName"] == "MyNovel"
    assert builder["artifactName"] == "MyNovel-${env.MYNOVEL_ASSET_SUFFIX}.${ext}"
    assert builder["directories"]["output"] == "../dist"
    assert {"from": "../dist/backend", "to": "backend", "filter": ["MyNovelBackend*"]} in builder[
        "extraResources"
    ]
    assert builder["win"]["target"] == [{"target": "nsis", "arch": ["x64"]}]
    assert builder["nsis"]["createDesktopShortcut"] is True
    assert builder["nsis"]["createStartMenuShortcut"] is True
    assert builder["nsis"]["runAfterFinish"] is True
```

Add `import yaml` at the top of `tests/test_frontend_tooling.py`.

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
pixi run pytest tests/test_frontend_tooling.py::test_electron_main_process_and_builder_config_are_packaged_for_backend -q
```

Expected: FAIL because the Electron main process and builder config do not exist.

- [ ] **Step 3: Create Electron main process**

Create `frontend/electron/main.ts`:

```typescript
import { app, BrowserWindow } from "electron";
import {
  DEFAULT_BACKEND_HOST,
  DEFAULT_BACKEND_PORT,
  createBackendUrl,
  findAvailablePort,
  resolveBackendExecutable,
  startBackend,
  stopBackend,
  waitForBackendHealth,
  type BackendProcess,
} from "./backend.js";

let backendProcess: BackendProcess | null = null;
let mainWindow: BrowserWindow | null = null;

async function createMainWindow(): Promise<void> {
  const host = DEFAULT_BACKEND_HOST;
  const port = await findAvailablePort(host, DEFAULT_BACKEND_PORT);
  const executable =
    process.env.MYNOVEL_BACKEND_EXECUTABLE !== undefined
      ? process.env.MYNOVEL_BACKEND_EXECUTABLE
      : resolveBackendExecutable(process.resourcesPath, process.platform);

  backendProcess = startBackend({ executable, host, port });
  try {
    await waitForBackendHealth(createBackendUrl(host, port, "/health"));
  } catch (error) {
    await createStartupErrorWindow(error);
    return;
  }

  const window = new BrowserWindow({
    width: 1280,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow = window;
  window.once("ready-to-show", () => {
    mainWindow?.show();
  });
  window.on("closed", () => {
    if (mainWindow === window) {
      mainWindow = null;
    }
  });
  await window.loadURL(createBackendUrl(host, port));
}

async function createStartupErrorWindow(error: unknown): Promise<void> {
  stopBackend(backendProcess);
  backendProcess = null;
  const message = error instanceof Error ? error.message : String(error);
  const window = new BrowserWindow({
    width: 760,
    height: 420,
    resizable: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow = window;
  await window.loadURL(
    `data:text/plain;charset=utf-8,${encodeURIComponent(`MyNovel could not start\n\n${message}`)}`,
  );
}

app.whenReady().then(() => {
  void createMainWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  stopBackend(backendProcess);
  backendProcess = null;
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    void createMainWindow();
  }
});
```

- [ ] **Step 4: Create Electron Builder config**

Create `frontend/electron-builder.yml`:

```yaml
appId: com.mynovel.app
productName: MyNovel
artifactName: MyNovel-${env.MYNOVEL_ASSET_SUFFIX}.${ext}
asar: true
npmRebuild: false
directories:
  output: ../dist
files: ["dist/**/*", "dist-electron/**/*", "package.json"]
extraResources:
  - from: ../dist/backend
    to: backend
    filter: ["MyNovelBackend*"]
win:
  target:
    - { target: nsis, arch: ["x64"] }
nsis:
  oneClick: false
  perMachine: false
  allowToChangeInstallationDirectory: false
  createDesktopShortcut: true
  createStartMenuShortcut: true
  runAfterFinish: true
mac:
  target: [{ target: dmg }]
  category: public.app-category.productivity
```

- [ ] **Step 5: Run focused tests and typecheck**

Run:

```powershell
pixi run pytest tests/test_frontend_tooling.py::test_electron_main_process_and_builder_config_are_packaged_for_backend -q
pixi run npm run typecheck
pixi run npm run lint
```

Working directory for npm commands: `frontend`.

Expected: PASS.

- [ ] **Step 6: Commit**

Run: `git add frontend/electron/main.ts frontend/electron-builder.yml tests/test_frontend_tooling.py; git commit -m "Add Electron main process and builder config"`

---

### Task 5: Move Release Workflow To Electron Builder

**Files:**
- Modify: `.github/workflows/release.yml`
- Modify: `tests/test_desktop_release.py`
- Modify: `tests/test_github_actions.py`

- [ ] **Step 1: Update failing workflow assertions**

In `tests/test_desktop_release.py`, change `test_release_workflow_builds_desktop_artifact_and_update_metadata` to:

```python
def test_release_workflow_builds_electron_desktop_artifact_and_update_metadata() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))
    commands = [
        step["run"] for job in workflow["jobs"].values() for step in job["steps"] if "run" in step
    ]
    workflow_text = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert any(command.startswith("pixi run pyinstaller --name MyNovelBackend") for command in commands)
    assert any("npm run electron:build" in command for command in commands)
    assert any("write-metadata" in command for command in commands)
    assert "update-" in workflow_text
    assert "sha256" in workflow_text
```

Change `test_release_workflow_uploads_unsigned_native_installers_without_paid_signing` to assert `.exe` instead of `.msi`:

```python
def test_release_workflow_uploads_unsigned_native_installers_without_paid_signing() -> None:
    workflow_text = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert ".dmg" in workflow_text
    assert ".exe" in workflow_text
    assert ".msi" not in workflow_text
    assert "codesign" not in workflow_text
    assert "signtool" not in workflow_text
    assert "notarize" not in workflow_text
    assert "--global" not in workflow_text
```

Remove the old WiX-specific tests from `tests/test_desktop_release.py`:

- `test_windows_installer_creates_shortcuts_and_launches_after_interactive_install`
- `test_windows_msi_build_uses_x64_architecture_and_wix_util_extension`

In `tests/test_github_actions.py`, update `test_release_workflow_reserves_desktop_release_metadata_steps`:

```python
def test_release_workflow_reserves_desktop_release_metadata_steps() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))

    commands = _workflow_run_commands(workflow)

    assert "pixi run pytest" in commands
    assert any(command.startswith("pixi run pyinstaller --name MyNovelBackend") for command in commands)
    assert any("npm run electron:build" in command for command in commands)
    assert any("write-metadata" in command for command in commands)
    assert workflow["on"]["push"]["branches"] == ["main"]
    assert "tags" not in workflow["on"]["push"]
```

Replace `test_release_workflow_pins_free_wix_toolset` with:

```python
def test_release_workflow_uses_electron_builder_instead_of_wix() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))
    commands = _workflow_run_commands(workflow)
    workflow_text = Path(".github/workflows/release.yml").read_text(encoding="utf-8").lower()

    assert any("npm run electron:build" in command for command in commands)
    assert "wix" not in workflow_text
    assert "MyNovel-windows-x64.exe" in Path(".github/workflows/release.yml").read_text(
        encoding="utf-8"
    )
```

- [ ] **Step 2: Run workflow tests to verify they fail**

Run:

```powershell
pixi run pytest tests/test_desktop_release.py::test_release_workflow_builds_electron_desktop_artifact_and_update_metadata tests/test_desktop_release.py::test_release_workflow_uploads_unsigned_native_installers_without_paid_signing tests/test_github_actions.py::test_release_workflow_reserves_desktop_release_metadata_steps tests/test_github_actions.py::test_release_workflow_uses_electron_builder_instead_of_wix -q
```

Expected: FAIL because the release workflow still builds `MyNovel` with PyInstaller and WiX.

- [ ] **Step 3: Update release workflow**

In `.github/workflows/release.yml`, change the Windows matrix installer glob to `.exe`:

```yaml
          - os: windows-latest
            asset_suffix: windows-x64
            installer_glob: MyNovel-windows-x64.exe
```

Replace the PyInstaller/WiX/package steps with:

```yaml
      - run: pixi run pyinstaller --name MyNovelBackend --onefile --collect-all mynovel --workpath build/pyinstaller --specpath build src/mynovel/desktop.py
      - name: Prepare Electron backend resource
        run: |
          import shutil
          import sys
          from pathlib import Path

          dist = Path("dist")
          backend_dir = dist / "backend"
          backend_dir.mkdir(parents=True, exist_ok=True)
          executable_name = "MyNovelBackend.exe" if sys.platform == "win32" else "MyNovelBackend"
          shutil.copy2(dist / executable_name, backend_dir / executable_name)
        shell: python
      - name: Build Electron installer
        run: pixi run npm run electron:build
        working-directory: frontend
        env:
          CSC_IDENTITY_AUTO_DISCOVERY: "false"
          MYNOVEL_ASSET_SUFFIX: ${{ matrix.asset_suffix }}
      - name: Write update metadata
        run: pixi run python -m mynovel.release_package write-metadata --dist dist --artifact "dist/${{ matrix.installer_glob }}" --version "${{ env.RELEASE_VERSION }}" --platform "${{ matrix.asset_suffix }}"
```

Update the release upload file list:

```yaml
          files: |
            dist/update-*.json
            dist/checksums-*.sha256
            dist/*.dmg
            dist/*.exe
```

Remove the `Install free WiX toolset` step and the old `Build unsigned native installer` step.

- [ ] **Step 4: Run workflow tests**

Run:

```powershell
pixi run pytest tests/test_desktop_release.py tests/test_github_actions.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add .github/workflows/release.yml tests/test_desktop_release.py tests/test_github_actions.py; git commit -m "Build release installers with Electron Builder"`

---

### Task 6: Local Verification

**Files:**
- No planned source edits unless verification exposes a bug.

- [ ] **Step 1: Run frontend verification**

Run from `frontend`:

```powershell
pixi run npm run test
pixi run npm run typecheck
pixi run npm run lint
pixi run npm run build
```

Expected: all commands PASS.

- [ ] **Step 2: Run Python verification**

Run from repo root:

```powershell
pixi run pytest
pixi run ruff check src tests
pixi run ruff format --check src tests
pixi run mypy src
pixi run python -m mynovel.schema_check
```

Expected: all commands PASS.

- [ ] **Step 3: Run a local Windows Electron package smoke build**

Run from repo root except the final npm command, which runs from `frontend`:

```powershell
pixi run npm --prefix frontend install --package-lock=false
pixi run npm --prefix frontend run build
pixi run python -m mynovel.release_package sync-frontend-dist --source frontend/dist --target src/mynovel/frontend/dist
pixi run pyinstaller --name MyNovelBackend --onefile --collect-all mynovel --workpath build/pyinstaller --specpath build src/mynovel/desktop.py
New-Item -ItemType Directory -Force -Path dist/backend
Copy-Item -LiteralPath dist/MyNovelBackend.exe -Destination dist/backend/MyNovelBackend.exe -Force
$env:CSC_IDENTITY_AUTO_DISCOVERY = "false"
$env:MYNOVEL_ASSET_SUFFIX = "windows-x64"
Push-Location frontend; pixi run npm run electron:build; Pop-Location
Test-Path dist/MyNovel-windows-x64.exe
```

Expected: the final `Test-Path` returns `True`.

---

### Task 7: Push, Trigger GitHub Actions, Download, Install, And Run

**Files:**
- No source edits unless release verification exposes a bug.

- [ ] **Step 1: Push and watch workflows**

```powershell
git status --short --branch
git log --oneline -5
git push origin main
gh run list --branch main --limit 5
gh run watch <release-run-id>
gh run watch <ci-run-id>
```

Expected: push succeeds; CI and Release finish successfully.

- [ ] **Step 2: Download the Windows release artifact**

```powershell
$tag = "v0.1.<github-run-number>"
$downloadDir = ".tool/release-smoke/$tag"
New-Item -ItemType Directory -Force -Path $downloadDir
gh release download $tag --pattern "MyNovel-windows-x64.exe" --pattern "update-windows-x64.json" --pattern "checksums-windows-x64.sha256" --dir $downloadDir --clobber
Get-ChildItem -LiteralPath $downloadDir
```

Expected: installer, update metadata, and checksum are downloaded.

- [ ] **Step 3: Install, launch, and check shortcuts**

```powershell
$installer = Resolve-Path ".tool/release-smoke/$tag/MyNovel-windows-x64.exe"
Start-Process -FilePath $installer -ArgumentList "/S" -Wait
$installedExe = Join-Path $env:LOCALAPPDATA "Programs\\MyNovel\\MyNovel.exe"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "MyNovel.lnk"
$startMenuShortcut = Join-Path $env:APPDATA "Microsoft\\Windows\\Start Menu\\Programs\\MyNovel.lnk"
Test-Path $installedExe
Test-Path $desktopShortcut
Test-Path $startMenuShortcut
Start-Process -FilePath $installedExe
Start-Sleep -Seconds 8
Get-Process MyNovel -ErrorAction SilentlyContinue
```

Expected: app exe and shortcuts exist, `MyNovel` is running, a native Electron window opens, and no default-browser tab opens.

- [ ] **Step 4: Report release verification result**

Report commit range, CI run, Release run, release tag, downloaded installer path, install result, launch result, shortcut result, and browser-launch result.
