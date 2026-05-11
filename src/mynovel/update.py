from __future__ import annotations

from dataclasses import dataclass

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


def _size_label(size_bytes: int | None) -> str:
    if not size_bytes:
        return ""
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
