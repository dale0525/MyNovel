import tomllib
from pathlib import Path

import mynovel


def test_package_has_version() -> None:
    assert isinstance(mynovel.__version__, str)
    assert mynovel.__version__


def test_frontend_dist_included_as_package_data() -> None:
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_data = config["tool"]["setuptools"]["package-data"]["mynovel"]
    assert "frontend/dist/index.html" in package_data
    assert "frontend/dist/assets/*" in package_data
