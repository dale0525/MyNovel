from pathlib import Path
import json
import tomllib


def test_frontend_package_has_required_scripts() -> None:
    package = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["dev"] == "vite --host 127.0.0.1"
    assert package["scripts"]["build"] == "tsc -b && vite build"
    assert package["scripts"]["typecheck"] == "tsc -b --pretty false"
    assert package["scripts"]["lint"] == "eslint ."
    assert package["scripts"]["test"] == "vitest run --environment jsdom"
    assert package["scripts"]["e2e"] == "playwright test"


def test_pixi_exposes_frontend_tasks() -> None:
    config = tomllib.loads(Path("pixi.toml").read_text(encoding="utf-8"))
    assert "nodejs" in config["dependencies"]
    assert config["dependencies"]["nodejs"] == ">=22.12,<23"
    assert config["tasks"]["frontend-install"] == (
        "npm --prefix frontend install --package-lock=false"
    )
    assert config["tasks"]["frontend-dev"] == (
        "pixi run frontend-install && npm --prefix frontend run dev"
    )
    assert config["tasks"]["frontend-build"] == (
        "pixi run frontend-install && npm --prefix frontend run build"
    )
    assert config["tasks"]["frontend-typecheck"] == (
        "pixi run frontend-install && npm --prefix frontend run typecheck"
    )
    assert config["tasks"]["frontend-lint"] == (
        "pixi run frontend-install && npm --prefix frontend run lint"
    )
    assert config["tasks"]["frontend-test"] == (
        "pixi run frontend-install && npm --prefix frontend run test"
    )
    assert config["tasks"]["frontend-e2e"] == (
        "pixi run frontend-install && npm --prefix frontend run e2e"
    )


def test_frontend_config_files_support_tooling() -> None:
    package = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    assert "typescript-eslint" in package["devDependencies"]
    assert "postcss" in package["devDependencies"]
    assert "autoprefixer" in package["devDependencies"]

    eslint_config = Path("frontend/eslint.config.js").read_text(encoding="utf-8")
    assert "typescript-eslint" in eslint_config
    assert "eslint-plugin-react-hooks" in eslint_config

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


def test_frontend_tsconfig_separates_browser_and_node_projects() -> None:
    root = json.loads(Path("frontend/tsconfig.json").read_text(encoding="utf-8"))
    app = json.loads(Path("frontend/tsconfig.app.json").read_text(encoding="utf-8"))
    node = json.loads(Path("frontend/tsconfig.node.json").read_text(encoding="utf-8"))

    assert root["files"] == []
    assert root["references"] == [
        {"path": "./tsconfig.app.json"},
        {"path": "./tsconfig.node.json"},
    ]
    assert app["include"] == ["src"]
    assert app["compilerOptions"].get("types") != ["node"]
    assert node["include"] == ["vite.config.ts", "tailwind.config.ts"]
    assert node["compilerOptions"]["types"] == ["node"]
