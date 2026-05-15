from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def frontend_dist_path() -> Path:
    return Path(str(files("mynovel") / "frontend" / "dist"))
