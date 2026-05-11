from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from shutil import copy2
import sqlite3
from urllib.parse import unquote, urlparse

from packaging.version import Version
from pydantic import BaseModel
import httpx


class UpdateManifest(BaseModel):
    channel: str = "stable"
    version: str
    url: str
    sha256: str
    notes: str = ""
    published_at: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True)
class UpdateCheckResult:
    available: bool
    version: str | None = None
    url: str | None = None
    sha256: str | None = None
    notes: str = ""
    published_at: str | None = None
    size_label: str = ""


@dataclass(frozen=True)
class VerifiedUpdateArtifact:
    path: Path
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class DatabaseBackup:
    path: Path


@dataclass(frozen=True)
class StagedUpdateInstall:
    plan_path: Path
    payload: dict[str, object]


def check_for_update(
    current_version: str,
    manifest: UpdateManifest,
    skipped_version: str | None = None,
) -> UpdateCheckResult:
    if manifest.channel != "stable":
        return UpdateCheckResult(available=False)
    if skipped_version and manifest.version == skipped_version:
        return UpdateCheckResult(available=False)
    if Version(manifest.version) <= Version(current_version):
        return UpdateCheckResult(available=False)
    return UpdateCheckResult(
        available=True,
        version=manifest.version,
        url=manifest.url,
        sha256=manifest.sha256,
        notes=manifest.notes,
        published_at=manifest.published_at,
        size_label=_size_label(manifest.size_bytes),
    )


def fetch_update_manifest(manifest_url: str) -> UpdateManifest:
    response = httpx.get(manifest_url, timeout=30.0)
    response.raise_for_status()
    return UpdateManifest.model_validate(response.json())


def download_update_artifact(
    manifest: UpdateManifest,
    download_dir: Path,
    client: httpx.Client | None = None,
) -> VerifiedUpdateArtifact:
    download_dir.mkdir(parents=True, exist_ok=True)
    target = download_dir / _artifact_filename(manifest.url, manifest.version)
    if client is None:
        response = httpx.get(manifest.url, timeout=120.0)
    else:
        response = client.get(manifest.url, timeout=120.0)
    response.raise_for_status()
    target.write_bytes(response.content)
    return verify_update_artifact(target, manifest)


def verify_update_artifact(path: Path, manifest: UpdateManifest) -> VerifiedUpdateArtifact:
    digest = sha256(path.read_bytes()).hexdigest()
    if digest.lower() != manifest.sha256.lower():
        raise ValueError("Downloaded update checksum does not match the manifest.")
    return VerifiedUpdateArtifact(path=path, sha256=digest, size_bytes=path.stat().st_size)


def backup_sqlite_database(db_path: Path, backup_dir: Path) -> DatabaseBackup:
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = _unique_backup_path(db_path, backup_dir)
    with sqlite3.connect(db_path) as source, sqlite3.connect(backup_path) as target:
        source.backup(target)
    return DatabaseBackup(path=backup_path)


def stage_update_install(
    manifest: UpdateManifest,
    artifact_path: Path,
    db_backup_path: Path,
    staging_dir: Path,
) -> StagedUpdateInstall:
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged_artifact = staging_dir / artifact_path.name
    copy2(artifact_path, staged_artifact)
    payload = {
        "version": manifest.version,
        "artifact_path": str(staged_artifact),
        "sha256": manifest.sha256,
        "db_backup_path": str(db_backup_path),
        "notes": manifest.notes,
        "requires_user_confirmation": True,
        "install_mode": "manual-confirmation",
    }
    plan_path = staging_dir / "install-plan.json"
    plan_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return StagedUpdateInstall(plan_path=plan_path, payload=payload)


def prepare_update_install(
    manifest: UpdateManifest,
    db_path: Path,
    workspace_dir: Path,
    client: httpx.Client | None = None,
) -> StagedUpdateInstall:
    version_dir = manifest.version.replace("/", "-")
    verified = download_update_artifact(manifest, workspace_dir / "downloads" / version_dir, client)
    backup = backup_sqlite_database(db_path, workspace_dir / "backups")
    return stage_update_install(
        manifest,
        verified.path,
        db_backup_path=backup.path,
        staging_dir=workspace_dir / "staged" / version_dir,
    )


def _artifact_filename(url: str, version: str) -> str:
    name = Path(unquote(urlparse(url).path)).name
    return name or f"MyNovel-{version}"


def _unique_backup_path(db_path: Path, backup_dir: Path) -> Path:
    first = backup_dir / f"{db_path.stem}.backup{db_path.suffix}"
    if not first.exists():
        return first
    for index in range(2, 1000):
        candidate = backup_dir / f"{db_path.stem}.backup-{index}{db_path.suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Unable to reserve a database backup path in {backup_dir}")


def _size_label(size_bytes: int | None) -> str:
    if not size_bytes:
        return ""
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
