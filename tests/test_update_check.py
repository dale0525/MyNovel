from hashlib import sha256
import sqlite3

import httpx
from mynovel.update import (
    UpdateManifest,
    backup_sqlite_database,
    check_for_update,
    prepare_update_install,
    stage_update_install,
    verify_update_artifact,
)


def test_update_manifest_reports_newer_stable_release() -> None:
    manifest = UpdateManifest(
        channel="stable",
        version="0.2.0",
        url="https://example.test/MyNovel.dmg",
        sha256="abc123",
        notes="修复章节恢复。",
        published_at="2026-05-11T00:00:00Z",
        size_bytes=123456,
    )

    result = check_for_update("0.1.0", manifest)

    assert result.available is True
    assert result.version == "0.2.0"
    assert result.notes == "修复章节恢复。"
    assert result.size_label == "120.6 KB"


def test_update_manifest_ignores_current_or_skipped_version() -> None:
    manifest = UpdateManifest(
        channel="stable",
        version="0.2.0",
        url="https://example.test/MyNovel.dmg",
        sha256="abc123",
        notes="修复章节恢复。",
    )

    assert check_for_update("0.2.0", manifest).available is False
    assert check_for_update("0.1.0", manifest, skipped_version="0.2.0").available is False


def test_verified_update_artifact_can_be_staged_with_database_backup(tmp_path) -> None:
    artifact = tmp_path / "MyNovel.dmg"
    artifact.write_bytes(b"installer payload")
    db_path = tmp_path / "mynovel.sqlite"
    _create_sqlite_database(db_path, "sqlite data")
    manifest = UpdateManifest(
        channel="stable",
        version="0.2.0",
        url="https://example.test/MyNovel.dmg",
        sha256=sha256(artifact.read_bytes()).hexdigest(),
        notes="修复章节恢复。",
    )

    verified = verify_update_artifact(artifact, manifest)
    backup = backup_sqlite_database(db_path, tmp_path / "backups")
    plan = stage_update_install(
        manifest,
        verified.path,
        db_backup_path=backup.path,
        staging_dir=tmp_path / "staged",
    )

    assert verified.sha256 == manifest.sha256
    assert backup.path.exists()
    assert _read_sqlite_value(backup.path) == "sqlite data"
    assert plan.plan_path.exists()
    assert plan.payload["version"] == "0.2.0"
    assert plan.payload["requires_user_confirmation"] is True
    assert plan.payload["db_backup_path"] == str(backup.path)


def test_prepare_update_install_downloads_verifies_and_backs_up_database(tmp_path) -> None:
    payload = b"installer payload"
    db_path = tmp_path / "mynovel.sqlite"
    _create_sqlite_database(db_path, "current data")
    manifest = UpdateManifest(
        channel="stable",
        version="0.2.0",
        url="https://example.test/MyNovel.dmg",
        sha256=sha256(payload).hexdigest(),
        notes="修复章节恢复。",
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=payload))

    with httpx.Client(transport=transport) as client:
        plan = prepare_update_install(
            manifest,
            db_path,
            workspace_dir=tmp_path / "updates",
            client=client,
        )

    staged_artifact = plan.payload["artifact_path"]
    assert isinstance(staged_artifact, str)
    assert (tmp_path / "updates" / "downloads" / "0.2.0" / "MyNovel.dmg").exists()
    assert plan.plan_path.exists()
    assert plan.payload["requires_user_confirmation"] is True
    assert _read_sqlite_value(tmp_path / "updates" / "backups" / "mynovel.backup.sqlite") == (
        "current data"
    )


def _create_sqlite_database(path, value: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("create table content(value text not null)")
        connection.execute("insert into content(value) values (?)", (value,))


def _read_sqlite_value(path) -> str:
    with sqlite3.connect(path) as connection:
        row = connection.execute("select value from content").fetchone()
    assert row is not None
    return row[0]
