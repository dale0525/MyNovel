from __future__ import annotations

from sqlmodel import SQLModel

from mynovel.domain import models  # noqa: F401
from mynovel.prompts.registry import ASSET_DIR, load_prompt_asset


def main() -> None:
    _check_tables()
    _check_prompt_assets()


def _check_tables() -> None:
    required_tables = {
        "book",
        "canon",
        "chapter",
        "runtrace",
        "providerconfig",
        "openbookblueprint",
    }
    existing_tables = set(SQLModel.metadata.tables)
    missing = sorted(required_tables - existing_tables)
    if missing:
        raise SystemExit(f"Missing schema tables: {', '.join(missing)}")


def _check_prompt_assets() -> None:
    for path in sorted(ASSET_DIR.glob("*.yaml")):
        asset = load_prompt_asset(path)
        if not asset.source or not asset.source_license:
            raise SystemExit(f"Prompt asset missing source metadata: {path}")


if __name__ == "__main__":
    main()
