from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.repositories import get_provider_config, get_provider_config_validation


def app_bootstrap_payload(db_path: Path) -> dict[str, Any]:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        configured = (
            get_provider_config(session) is not None
            and get_provider_config_validation(session) is not None
        )
    return {"providerConfigured": configured, "initialRoute": "/" if configured else "/setup", "message": None}
