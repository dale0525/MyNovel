from pathlib import Path
import json
import tomllib

import yaml


def test_frontend_package_has_required_scripts() -> None:
    package = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    assert package["main"] == "dist-electron/main.js"
    assert package["scripts"]["dev"] == "vite --host 127.0.0.1"
    assert package["scripts"]["build"] == "tsc -b && vite build"
    assert package["scripts"]["typecheck"] == "tsc -b --pretty false"
    assert package["scripts"]["lint"] == "eslint ."
    assert package["scripts"]["test"] == "vitest run --environment jsdom tests"
    assert package["scripts"]["e2e"] == (
        "PLAYWRIGHT_BROWSERS_PATH=.tool/ms-playwright playwright test"
    )
    assert package["scripts"]["build:electron-main"] == "tsc -p tsconfig.electron.json"
    assert package["scripts"]["electron:build"] == (
        "npm run build:electron-main && electron-builder --config electron-builder.yml"
    )
    assert package["scripts"]["electron:dev"] == "npm run build:electron-main && electron ."
    assert package["devDependencies"]["electron"] == "^35.0.0"
    assert package["devDependencies"]["electron-builder"] == "^26.0.0"


def test_pixi_exposes_frontend_tasks() -> None:
    config = tomllib.loads(Path("pixi.toml").read_text(encoding="utf-8"))
    assert "nodejs" in config["dependencies"]
    assert config["dependencies"]["nodejs"] == ">=22.12,<23"
    assert config["tasks"]["dev"] == (
        "pixi run frontend-install && python -m mynovel.dev_stack --db .mynovel/dev.sqlite"
    )
    assert config["tasks"]["preview"] == (
        "pixi run frontend-install && npm --prefix frontend run build && "
        "python -m mynovel.release_package sync-frontend-dist --source frontend/dist "
        "--target src/mynovel/frontend/dist && mynovel-dev --db .mynovel/dev.sqlite"
    )
    assert config["tasks"]["frontend-install"] == (
        "npm --prefix frontend install --package-lock=false"
    )
    ci_only_task_names = {
        "test",
        "lint",
        "typecheck",
        "schema-check",
        "frontend-dev",
        "frontend-build",
        "frontend-typecheck",
        "frontend-lint",
        "frontend-test",
        "frontend-e2e",
        "desktop-build",
        "native-package",
    }
    assert ci_only_task_names.isdisjoint(config["tasks"])


def test_vite_dev_server_proxies_api_to_python_backend() -> None:
    vite_config = Path("frontend/vite.config.ts").read_text(encoding="utf-8")

    assert '"/api": "http://127.0.0.1:8765"' in vite_config
    assert "server:" in vite_config


def test_frontend_config_files_support_tooling() -> None:
    package = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    assert "typescript-eslint" in package["devDependencies"]
    assert "postcss" in package["devDependencies"]
    assert "autoprefixer" in package["devDependencies"]

    eslint_config = Path("frontend/eslint.config.js").read_text(encoding="utf-8")
    assert "typescript-eslint" in eslint_config
    assert "eslint-plugin-react-hooks" in eslint_config
    assert '"electron/**/*.ts"' in eslint_config

    postcss_config = Path("frontend/postcss.config.js").read_text(encoding="utf-8")
    assert "tailwindcss" in postcss_config
    assert "autoprefixer" in postcss_config

    tailwind_config = Path("frontend/tailwind.config.ts").read_text(encoding="utf-8")
    assert '"./index.html"' in tailwind_config
    assert '"./src/**/*.{ts,tsx}"' in tailwind_config
    assert "tailwindcss-animate" in tailwind_config

    components = json.loads(Path("frontend/components.json").read_text(encoding="utf-8"))
    assert components["tailwind"]["config"] == "tailwind.config.ts"

    globals_css = Path("frontend/src/styles/globals.css").read_text(encoding="utf-8")
    assert "@tailwind base;" in globals_css
    assert "@tailwind components;" in globals_css
    assert "@tailwind utilities;" in globals_css
    assert "--background:" in globals_css
    assert "--foreground:" in globals_css


def test_frontend_shadcn_utils_helper_exists() -> None:
    utils = Path("frontend/src/lib/utils.ts").read_text(encoding="utf-8")
    assert 'import { clsx, type ClassValue } from "clsx";' in utils
    assert 'import { twMerge } from "tailwind-merge";' in utils
    assert "export function cn(" in utils


def test_frontend_generated_artifacts_are_ignored() -> None:
    ignore_lines = set(Path(".gitignore").read_text(encoding="utf-8").splitlines())
    assert "frontend/node_modules/" in ignore_lines
    assert "frontend/.vite/" in ignore_lines
    assert "frontend/playwright-report/" in ignore_lines
    assert "frontend/test-results/" in ignore_lines
    assert "frontend/dist-electron/" in ignore_lines


def test_frontend_tsconfig_separates_browser_and_node_projects() -> None:
    root = json.loads(Path("frontend/tsconfig.json").read_text(encoding="utf-8"))
    app = json.loads(Path("frontend/tsconfig.app.json").read_text(encoding="utf-8"))
    node = json.loads(Path("frontend/tsconfig.node.json").read_text(encoding="utf-8"))
    electron = json.loads(
        Path("frontend/tsconfig.electron.json").read_text(encoding="utf-8")
    )

    assert root["files"] == []
    assert root["references"] == [
        {"path": "./tsconfig.app.json"},
        {"path": "./tsconfig.node.json"},
        {"path": "./tsconfig.electron.json"},
    ]
    assert app["include"] == ["src"]
    assert app["compilerOptions"].get("types") != ["node"]
    assert node["include"] == ["vite.config.ts", "tailwind.config.ts"]
    assert node["compilerOptions"]["types"] == ["node"]
    assert electron["extends"] == "./tsconfig.node.json"
    assert electron["compilerOptions"]["module"] == "NodeNext"
    assert electron["compilerOptions"]["moduleResolution"] == "NodeNext"
    assert electron["compilerOptions"]["outDir"] == "dist-electron"
    assert electron["compilerOptions"]["rootDir"] == "electron"
    assert electron["compilerOptions"]["noEmit"] is False
    assert (
        electron["compilerOptions"]["tsBuildInfoFile"]
        == "./node_modules/.tmp/tsconfig.electron.tsbuildinfo"
    )
    assert electron["compilerOptions"]["types"] == ["node", "electron"]
    assert electron["include"] == ["electron/**/*.ts"]
    electron_env = Path("frontend/electron/electron-env.d.ts")
    assert electron_env.read_text(encoding="utf-8") == "export {};\n"


def test_electron_main_process_and_builder_config_are_packaged_for_backend() -> None:
    main_process = Path("frontend/electron/main.ts").read_text(encoding="utf-8")
    builder = yaml.safe_load(
        Path("frontend/electron-builder.yml").read_text(encoding="utf-8")
    )

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
