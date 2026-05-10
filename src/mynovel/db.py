from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine


def create_engine_for_path(path: Path) -> Engine:
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


def create_db_and_tables(engine: Engine) -> None:
    from mynovel.domain import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
