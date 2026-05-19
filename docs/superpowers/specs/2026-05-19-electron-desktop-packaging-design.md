# Electron Desktop Packaging Design

## Goal

Package MyNovel as a real Electron desktop application. Installing and launching the Windows release should open a native application window, not the user's default web browser.

## Current State

The current release workflow builds the frontend with Vite, syncs the static assets into the Python package, creates a PyInstaller executable from `src/mynovel/desktop.py`, and wraps it with the existing native installer flow. The desktop entrypoint starts the local Python server and calls `webbrowser.open(...)`, so the installed application behaves like a browser launcher instead of an Electron app.

## Decision

Use an Electron shell with a bundled PyInstaller backend executable.

Electron owns the desktop window, startup flow, and application lifecycle. The Python backend remains the source of the existing API, static frontend hosting, database access, and domain behavior. This keeps the migration focused on packaging and process orchestration instead of rewriting backend logic.

Rejected alternatives:

- Launch `python -m mynovel.desktop` from Electron using a packaged or system Python runtime. This is easier during development but fragile for end users because the release would depend on a Python runtime layout.
- Rewrite the backend in Node/Electron. This would create a larger migration with unnecessary risk for the packaging problem.

## Architecture

The packaged app contains two executables:

- `MyNovel.exe`: the Electron application shown to users.
- `MyNovelBackend.exe`: a bundled backend process built from the existing Python server entrypoint.

The frontend continues to be built by Vite. Release builds still sync `frontend/dist` into `src/mynovel/frontend/dist`, and the Python backend serves the single-page app and API from the same localhost origin. This avoids changing frontend API paths or adding a new production proxy layer.

Electron's main process finds the bundled backend executable from the packaged resources directory in production. In development it can use a configurable backend command or an existing local backend process, but the production path is the supported release path.

## Startup And Shutdown

On application start, Electron should:

1. Select an available localhost port, starting from the current default server port.
2. Spawn `MyNovelBackend.exe` with arguments equivalent to `--host 127.0.0.1 --port <port> --strict-port --no-open`.
3. Poll `http://127.0.0.1:<port>/health` until the backend is ready or a startup timeout expires.
4. Create a `BrowserWindow` and load `http://127.0.0.1:<port>`.
5. Show a clear local error view if the backend exits early or readiness times out.
6. Stop the backend child process when Electron quits.

The backend must not open a system browser when launched by Electron. The existing `--no-open` mode is the boundary for this behavior.

## Release Flow

The GitHub Actions release job should move Windows desktop packaging to Electron:

1. Install pixi and frontend dependencies.
2. Build the Vite frontend.
3. Sync `frontend/dist` into the Python package.
4. Run the existing Python and frontend quality checks.
5. Build the backend executable with PyInstaller, using a backend-specific name such as `MyNovelBackend`.
6. Run `electron-builder` to create the Windows installer for the Electron app named `MyNovel`.
7. Include the backend executable through Electron Builder resources.
8. Upload the installer, checksum, and update metadata to the GitHub Release.

The Windows installer should be produced by Electron Builder rather than the current WiX-based app installer path. The initial Windows target should be NSIS, producing an installer such as `MyNovel-windows-x64.exe`, because this matches the Electron ecosystem and supports the expected shortcuts and launch behavior.

The macOS release path should use Electron Builder DMG output with the corresponding platform backend executable bundled as a resource.

## Testing

Update release and packaging tests to assert the Electron packaging contract:

- The release workflow uses `electron-builder` for desktop packaging.
- The backend executable has a distinct name from the Electron application executable.
- The Windows Electron package no longer depends on the WiX desktop installer path.
- The backend launch mode includes `--no-open` and `--strict-port`.

Keep backend entrypoint tests focused on the existing Python behavior:

- `--no-open` prevents browser launch.
- `--strict-port` respects the selected port.
- `/health` remains available after startup.
- The synced frontend assets can still be served by the packaged backend.

Add lightweight Electron main-process tests or static assertions for the release-critical behavior:

- Backend executable path resolution.
- Backend child process spawning.
- Health polling before opening the window.
- `BrowserWindow` creation with the local backend URL.
- Backend cleanup on application quit.

Full GUI automation is out of scope for the first migration. The release artifact should still be manually verified after GitHub Actions builds it by installing the Windows package, launching the app, confirming a native Electron window opens, and confirming no external browser tab is opened.

## Out Of Scope

- Rewriting Python backend behavior in Node.
- Adding automatic updates.
- Adding tray behavior or background launch behavior.
- Changing the database location or schema.
- Reworking frontend routing or API paths.
