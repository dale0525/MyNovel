from __future__ import annotations

from pathlib import PurePath


def display_path(path: PurePath) -> str:
    return path.as_posix()
