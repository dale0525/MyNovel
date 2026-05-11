from pathlib import Path

import yaml


def test_ci_workflow_runs_project_verification_with_pixi() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))

    commands = _workflow_run_commands(workflow)

    assert "pixi run pytest" in commands
    assert "pixi run ruff check src tests" in commands
    assert "pixi run ruff format --check src tests" in commands


def test_release_workflow_reserves_desktop_release_metadata_steps() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))

    commands = _workflow_run_commands(workflow)

    assert "pixi run pytest" in commands
    assert "生成更新元数据" in " ".join(commands)
    assert workflow["on"]["push"]["tags"] == ["v*"]


def _workflow_run_commands(workflow: dict) -> list[str]:
    commands = []
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            command = step.get("run")
            if command:
                commands.append(command)
    return commands
