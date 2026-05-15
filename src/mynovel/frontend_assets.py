from __future__ import annotations

from pathlib import Path


def frontend_dist_path() -> Path:
    return frontend_dist_path_from_module(Path(__file__))


def frontend_dist_path_from_module(module_file: Path) -> Path:
    module_path = module_file.resolve()
    package_dist = module_path.parent / "frontend" / "dist"
    if package_dist.exists():
        return package_dist
    return module_path.parents[2] / "frontend" / "dist"
