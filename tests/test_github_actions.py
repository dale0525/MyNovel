from pathlib import Path

import yaml

FRONTEND_INSTALL_COMMAND = "pixi run npm install --package-lock=false"
FRONTEND_TEST_COMMAND = "pixi run npm run test"
FRONTEND_TYPECHECK_COMMAND = "pixi run npm run typecheck"
FRONTEND_BUILD_COMMAND = "pixi run npm run build"
SYNC_FRONTEND_DIST_COMMAND = (
    "pixi run python -m mynovel.release_package sync-frontend-dist "
    "--source frontend/dist --target src/mynovel/frontend/dist"
)


def test_ci_workflow_runs_project_verification_with_pixi() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))

    commands = _workflow_run_commands(workflow)

    assert "pixi run pytest" in commands
    assert "pixi run ruff check src tests" in commands
    assert "pixi run ruff format --check src tests" in commands
    assert "pixi run mypy src" in commands
    assert "pixi run python -m mynovel.schema_check" in commands
    assert FRONTEND_INSTALL_COMMAND in commands
    assert FRONTEND_TEST_COMMAND in commands
    assert FRONTEND_TYPECHECK_COMMAND in commands
    assert FRONTEND_BUILD_COMMAND in commands
    _assert_frontend_working_directory(workflow, FRONTEND_INSTALL_COMMAND)
    _assert_frontend_working_directory(workflow, FRONTEND_TEST_COMMAND)
    _assert_frontend_working_directory(workflow, FRONTEND_TYPECHECK_COMMAND)
    _assert_frontend_working_directory(workflow, FRONTEND_BUILD_COMMAND)
    assert all("--prefix frontend" not in command for command in commands)

    pixi = Path("pixi.toml").read_text(encoding="utf-8")
    assert 'mypy = "' in pixi
    assert 'typecheck = "mypy src"' not in pixi
    assert "compileall" not in pixi


def test_release_workflow_reserves_desktop_release_metadata_steps() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))

    commands = _workflow_run_commands(workflow)

    assert "pixi run pytest" in commands
    assert any(
        command.startswith("pixi run pyinstaller --name MyNovelBackend") for command in commands
    )
    assert any("npm run electron:build" in command for command in commands)
    assert any("write-metadata" in command for command in commands)
    assert workflow["on"]["push"]["branches"] == ["main"]
    assert "tags" not in workflow["on"]["push"]


def test_release_workflow_builds_packaged_frontend_before_python_tests() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))

    package_commands = [
        step["run"] for step in workflow["jobs"]["package"]["steps"] if "run" in step
    ]

    pytest_index = package_commands.index("pixi run pytest")
    assert package_commands.index(FRONTEND_INSTALL_COMMAND) < pytest_index
    assert package_commands.index(FRONTEND_BUILD_COMMAND) < pytest_index
    assert package_commands.index(SYNC_FRONTEND_DIST_COMMAND) < pytest_index
    _assert_frontend_working_directory(workflow, FRONTEND_INSTALL_COMMAND)
    _assert_frontend_working_directory(workflow, FRONTEND_BUILD_COMMAND)
    assert all("--prefix frontend" not in command for command in package_commands)


def test_ci_workflow_builds_packaged_frontend_before_python_tests() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))

    ci_commands = [step["run"] for step in workflow["jobs"]["test"]["steps"] if "run" in step]

    pytest_index = ci_commands.index("pixi run pytest")
    assert ci_commands.index(FRONTEND_INSTALL_COMMAND) < pytest_index
    assert ci_commands.index(FRONTEND_BUILD_COMMAND) < pytest_index
    assert ci_commands.index(SYNC_FRONTEND_DIST_COMMAND) < pytest_index
    _assert_frontend_working_directory(workflow, FRONTEND_INSTALL_COMMAND)
    _assert_frontend_working_directory(workflow, FRONTEND_BUILD_COMMAND)
    assert all("--prefix frontend" not in command for command in ci_commands)


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


def test_release_workflow_uses_electron_builder_instead_of_wix() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))
    commands = _workflow_run_commands(workflow)
    workflow_text = Path(".github/workflows/release.yml").read_text(encoding="utf-8").lower()

    assert any("npm run electron:build" in command for command in commands)
    assert "wix" not in workflow_text
    assert "MyNovel-windows-x64.exe" in Path(".github/workflows/release.yml").read_text(
        encoding="utf-8"
    )


def _workflow_run_commands(workflow: dict) -> list[str]:
    commands = []
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            command = step.get("run")
            if command:
                commands.append(command)
    return commands


def _assert_frontend_working_directory(workflow: dict, command: str) -> None:
    matching_steps = [
        step
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if step.get("run") == command
    ]

    assert matching_steps
    assert all(step.get("working-directory") == "frontend" for step in matching_steps)
