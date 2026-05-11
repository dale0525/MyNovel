import tomllib
from pathlib import Path

import yaml


def test_desktop_entrypoint_and_build_task_are_configured() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    pixi = tomllib.loads(Path("pixi.toml").read_text(encoding="utf-8"))

    assert project["project"]["scripts"]["mynovel-desktop"] == "mynovel.desktop:main"
    assert "pyinstaller" in pixi["pypi-dependencies"]
    assert "src/mynovel/desktop.py" in pixi["tasks"]["desktop-build"]


def test_release_workflow_builds_desktop_artifact_and_update_metadata() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))
    commands = [
        step["run"] for job in workflow["jobs"].values() for step in job["steps"] if "run" in step
    ]

    assert "pixi run desktop-build" in commands
    assert any("update-" in command and "sha256" in command for command in commands)
