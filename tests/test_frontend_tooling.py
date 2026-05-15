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
