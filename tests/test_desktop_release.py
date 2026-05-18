import runpy
import sys
import tomllib
from pathlib import Path

import yaml

from mynovel.release_package import _write_metadata, normalize_release_version, sync_frontend_dist


def test_desktop_entrypoint_and_build_task_are_configured() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    pixi = tomllib.loads(Path("pixi.toml").read_text(encoding="utf-8"))

    assert project["project"]["scripts"]["mynovel-desktop"] == "mynovel.desktop:main"
    assert "pyinstaller" in pixi["pypi-dependencies"]
    assert "desktop-build" not in pixi["tasks"]
    assert "native-package" not in pixi["tasks"]


def test_desktop_script_invokes_main_when_executed_by_pyinstaller(
    monkeypatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, int, Path]] = []

    def fake_run_server(host: str, port: int, db: Path) -> None:
        calls.append((host, port, db))

    monkeypatch.setattr("mynovel.dev_server.run_server", fake_run_server)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "desktop.py",
            "--no-open",
            "--host",
            "127.0.0.1",
            "--port",
            "9987",
            "--strict-port",
            "--db",
            str(tmp_path / "desktop.sqlite"),
        ],
    )

    runpy.run_path("src/mynovel/desktop.py", run_name="__main__")

    assert calls == [("127.0.0.1", 9987, tmp_path / "desktop.sqlite")]


def test_preview_task_copies_assets_into_python_package() -> None:
    pixi = tomllib.loads(Path("pixi.toml").read_text(encoding="utf-8"))

    assert "src/mynovel/frontend/dist" in pixi["tasks"]["preview"]
    assert "mynovel-dev --db .mynovel/dev.sqlite" in pixi["tasks"]["preview"]


def test_sync_frontend_dist_replaces_package_assets(tmp_path: Path) -> None:
    source = tmp_path / "frontend" / "dist"
    target = tmp_path / "src" / "mynovel" / "frontend" / "dist"
    (source / "assets").mkdir(parents=True)
    (source / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    (source / "assets" / "old.js").write_text("console.log('new')", encoding="utf-8")
    target.mkdir(parents=True)
    (target / "stale.txt").write_text("stale", encoding="utf-8")

    copied = sync_frontend_dist(source, target)

    assert copied == target
    assert (target / "index.html").read_text(encoding="utf-8") == "<div id='root'></div>"
    assert (target / "assets" / "old.js").exists()
    assert not (target / "stale.txt").exists()


def test_release_workflow_builds_desktop_artifact_and_update_metadata() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))
    commands = [
        step["run"] for job in workflow["jobs"].values() for step in job["steps"] if "run" in step
    ]

    assert any(command.startswith("pixi run pyinstaller") for command in commands)
    assert any(
        command.startswith("pixi run python -m mynovel.release_package --version")
        for command in commands
    )
    workflow_text = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "update-" in workflow_text
    assert "sha256" in workflow_text


def test_release_workflow_uploads_unsigned_native_installers_without_paid_signing() -> None:
    workflow_text = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert ".dmg" in workflow_text
    assert ".msi" in workflow_text
    assert "codesign" not in workflow_text
    assert "signtool" not in workflow_text
    assert "notarize" not in workflow_text
    assert "--global" not in workflow_text


def test_release_package_normalizes_github_tag_versions() -> None:
    assert normalize_release_version("v0.2.0") == "0.2.0"
    assert normalize_release_version("refs/tags/v1.0.0") == "1.0.0"


def test_release_metadata_checksum_uses_lf_on_windows_text_mode(
    monkeypatch, tmp_path: Path
) -> None:
    original_write_text = Path.write_text

    def windows_write_text(self: Path, data: str, *args, **kwargs) -> int:
        if kwargs.get("newline") is None:
            data = data.replace("\n", "\r\n")
        return original_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", windows_write_text)
    artifact = tmp_path / "MyNovel-windows-x64.msi"
    artifact.write_bytes(b"placeholder msi")

    _write_metadata(tmp_path, artifact, "0.1.9", "windows-x64")

    checksum = (tmp_path / "checksums-windows-x64.sha256").read_bytes()
    assert checksum.endswith(b"MyNovel-windows-x64.msi\n")
    assert b"\r" not in checksum
