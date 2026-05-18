from pathlib import Path

import yaml


def test_ci_workflow_runs_project_verification_with_pixi() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))

    commands = _workflow_run_commands(workflow)

    assert "pixi run pytest" in commands
    assert "pixi run ruff check src tests" in commands
    assert "pixi run ruff format --check src tests" in commands
    assert "pixi run mypy src" in commands
    assert "pixi run python -m mynovel.schema_check" in commands
    assert "pixi run npm --prefix frontend install --package-lock=false" in commands
    assert "pixi run npm --prefix frontend run test" in commands
    assert "pixi run npm --prefix frontend run typecheck" in commands
    assert "pixi run npm --prefix frontend run build" in commands

    pixi = Path("pixi.toml").read_text(encoding="utf-8")
    assert 'mypy = "' in pixi
    assert 'typecheck = "mypy src"' not in pixi
    assert "compileall" not in pixi


def test_release_workflow_reserves_desktop_release_metadata_steps() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))

    commands = _workflow_run_commands(workflow)

    assert "pixi run pytest" in commands
    assert any(command.startswith("pixi run pyinstaller") for command in commands)
    assert any(
        command.startswith("pixi run python -m mynovel.release_package --version")
        for command in commands
    )
    assert workflow["on"]["push"]["branches"] == ["main"]
    assert "tags" not in workflow["on"]["push"]


def test_release_workflow_builds_packaged_frontend_before_python_tests() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))

    package_commands = [
        step["run"] for step in workflow["jobs"]["package"]["steps"] if "run" in step
    ]

    pytest_index = package_commands.index("pixi run pytest")
    assert (
        package_commands.index("pixi run npm --prefix frontend install --package-lock=false")
        < pytest_index
    )
    assert package_commands.index("pixi run npm --prefix frontend run build") < pytest_index
    assert (
        package_commands.index(
            "pixi run python -m mynovel.release_package sync-frontend-dist --source frontend/dist --target src/mynovel/frontend/dist"
        )
        < pytest_index
    )


def test_release_workflow_publishes_main_push_with_generated_version() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))
    workflow_text = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert workflow["env"]["RELEASE_VERSION"] == "0.1.${{ github.run_number }}"
    assert workflow["env"]["RELEASE_TAG"] == "v0.1.${{ github.run_number }}"
    assert '--version "${{ env.RELEASE_VERSION }}"' in workflow_text
    assert "github.ref_name" not in workflow_text
    assert workflow["jobs"]["publish"]["steps"][-1]["with"]["tag_name"] == "${{ env.RELEASE_TAG }}"


def test_release_workflow_builds_macos_and_windows_without_linux() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))

    package_job = workflow["jobs"]["package"]
    matrix_entries = package_job["strategy"]["matrix"]["include"]
    platforms = {entry["os"] for entry in matrix_entries}

    assert platforms == {"macos-14", "macos-15-intel", "windows-latest"}
    assert all("linux" not in entry["os"] for entry in matrix_entries)


def test_release_workflow_pins_free_wix_toolset() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))
    commands = _workflow_run_commands(workflow)

    assert any(
        "dotnet tool install --tool-path .tools wix --version 5.0.2" in command
        for command in commands
    )


def _workflow_run_commands(workflow: dict) -> list[str]:
    commands = []
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            command = step.get("run")
            if command:
                commands.append(command)
    return commands
