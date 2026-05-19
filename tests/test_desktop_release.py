import json
import runpy
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from mynovel.release_package import (
    _write_metadata,
    write_release_version_file,
    main,
    normalize_release_version,
    sync_frontend_dist,
)
from mynovel.version import release_version_from_file


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


def test_desktop_default_database_uses_user_writable_local_app_data(
    monkeypatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, int, Path]] = []

    def fake_run_server(host: str, port: int, db: Path) -> None:
        calls.append((host, port, db))

    monkeypatch.setattr("mynovel.dev_server.run_server", fake_run_server)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "desktop.py",
            "--no-open",
            "--host",
            "127.0.0.1",
            "--port",
            "9988",
            "--strict-port",
        ],
    )

    runpy.run_path("src/mynovel/desktop.py", run_name="__main__")

    assert calls == [
        (
            "127.0.0.1",
            9988,
            tmp_path / "LocalAppData" / "MyNovel" / "desktop.sqlite",
        )
    ]


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


def test_release_workflow_builds_electron_desktop_artifact_and_update_metadata() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"))
    commands = [
        step["run"] for job in workflow["jobs"].values() for step in job["steps"] if "run" in step
    ]
    workflow_text = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert any(
        command.startswith("pixi run pyinstaller --name MyNovelBackend") for command in commands
    )
    assert any("npm run electron:build" in command for command in commands)
    assert any("write-metadata" in command for command in commands)
    assert "update-" in workflow_text
    assert "sha256" in workflow_text
    assert "write-version" in workflow_text
    assert "--download-base-url" in workflow_text


def test_release_workflow_uploads_unsigned_native_installers_without_paid_signing() -> None:
    workflow_text = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert ".dmg" in workflow_text
    assert ".exe" in workflow_text
    assert ".msi" not in workflow_text
    assert "codesign" not in workflow_text
    assert "signtool" not in workflow_text
    assert "notarize" not in workflow_text
    assert "--global" not in workflow_text


def test_release_package_normalizes_github_tag_versions() -> None:
    assert normalize_release_version("v0.2.0") == "0.2.0"
    assert normalize_release_version("refs/tags/v1.0.0") == "1.0.0"


def test_release_metadata_command_writes_existing_electron_artifact_metadata(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "MyNovel-windows-x64.exe"
    artifact.write_bytes(b"sample electron installer")

    main(
        [
            "write-metadata",
            "--dist",
            str(tmp_path),
            "--artifact",
            str(artifact),
            "--version",
            "v0.1.9",
            "--platform",
            "windows-x64",
        ]
    )

    update = json.loads((tmp_path / "update-windows-x64.json").read_text(encoding="utf-8"))
    checksum = (tmp_path / "checksums-windows-x64.sha256").read_text(encoding="utf-8")

    assert update["version"] == "0.1.9"
    assert update["platform"] == "windows-x64"
    assert update["url"].endswith("/MyNovel-windows-x64.exe")
    assert update["url"].startswith("https://")
    assert update["size_bytes"] == len(b"sample electron installer")
    assert checksum.endswith("  MyNovel-windows-x64.exe\n")


def test_write_metadata_uses_absolute_release_asset_url(tmp_path: Path) -> None:
    artifact = tmp_path / "MyNovel-macos-arm64.dmg"
    artifact.write_bytes(b"installer")

    manifest_path = _write_metadata(
        tmp_path,
        artifact,
        "v0.2.0",
        "macos-arm64",
        download_base_url="https://github.com/dale0525/MyNovel/releases/download/v0.2.0",
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["version"] == "0.2.0"
    assert (
        manifest["url"]
        == "https://github.com/dale0525/MyNovel/releases/download/v0.2.0/MyNovel-macos-arm64.dmg"
    )


def test_write_release_version_file_normalizes_runtime_version(tmp_path: Path) -> None:
    version_path = tmp_path / "_release_version.txt"

    write_release_version_file(version_path, "v0.2.0")

    assert version_path.read_text(encoding="utf-8") == "0.2.0\n"
    assert release_version_from_file(version_path, fallback="0.1.0") == "0.2.0"


def test_release_metadata_checksum_uses_lf_on_windows_text_mode(
    monkeypatch, tmp_path: Path
) -> None:
    original_write_text = Path.write_text

    def windows_write_text(self: Path, data: str, *args, **kwargs) -> int:
        if kwargs.get("newline") is None:
            data = data.replace("\n", "\r\n")
        return original_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", windows_write_text)
    artifact = tmp_path / "MyNovel-windows-x64.exe"
    artifact.write_bytes(b"placeholder exe")

    _write_metadata(tmp_path, artifact, "0.1.9", "windows-x64")

    checksum = (tmp_path / "checksums-windows-x64.sha256").read_bytes()
    assert checksum.endswith(b"MyNovel-windows-x64.exe\n")
    assert b"\r" not in checksum


def test_release_package_removes_legacy_native_installer_packaging() -> None:
    source = Path("src/mynovel/release_package.py").read_text(encoding="utf-8")
    source_lower = source.lower()

    assert "wix" not in source_lower
    assert ".msi" not in source
    assert "package_native_installer" not in source
    assert "_package_windows_msi" not in source
    assert "_wix_source" not in source


def test_release_package_rejects_legacy_native_packaging_cli_args() -> None:
    with pytest.raises(SystemExit):
        main(["--version", "0.1.9", "--platform", "windows-x64"])
