from __future__ import annotations

from importlib.resources import files
from pathlib import Path

BASE_VERSION = "0.1.0"
RELEASE_VERSION_RESOURCE = "_release_version.txt"


def release_version(fallback: str = BASE_VERSION) -> str:
    try:
        resource = files("mynovel").joinpath(RELEASE_VERSION_RESOURCE)
        text = resource.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return fallback
    return _normalized_version_text(text, fallback)


def release_version_from_file(path: Path, fallback: str = BASE_VERSION) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return fallback
    return _normalized_version_text(text, fallback)


def _normalized_version_text(text: str, fallback: str) -> str:
    normalized = text.strip()
    return normalized or fallback
