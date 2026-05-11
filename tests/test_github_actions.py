from pathlib import Path

import yaml


def test_ci_workflow_runs_project_verification_with_pixi() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))

    commands = _workflow_run_commands(workflow)

    assert "pixi run pytest" in commands
    assert "pixi run ruff check src tests" in commands
    assert "pixi run ruff format --check src tests" in commands
    assert "pixi run typecheck" in commands
    assert "pixi run schema-check" in commands

    pixi = Path("pixi.toml").read_text(encoding="utf-8")
    assert 'mypy = "' in pixi
    assert 'typecheck = "mypy src"' in pixi
    assert "compileall" not in pixi


def test_release_workflow_reserves_desktop_release_metadata_steps() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))

    commands = _workflow_run_commands(workflow)

    assert "pixi run pytest" in commands
    assert any(command.startswith("pixi run native-package") for command in commands)
    assert workflow["on"]["push"]["tags"] == ["v*"]


def test_release_workflow_builds_macos_and_windows_without_linux() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))

    package_job = workflow["jobs"]["package"]
    matrix_entries = package_job["strategy"]["matrix"]["include"]
    platforms = {entry["os"] for entry in matrix_entries}

    assert platforms == {"macos-14", "macos-13", "windows-latest"}
    assert all("linux" not in entry["os"] for entry in matrix_entries)


def _workflow_run_commands(workflow: dict) -> list[str]:
    commands = []
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            command = step.get("run")
            if command:
                commands.append(command)
    return commands
