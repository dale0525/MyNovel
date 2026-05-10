from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine


def create_engine_for_path(path: Path) -> Engine:
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


def create_db_and_tables(engine: Engine) -> None:
    from mynovel.domain import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    migrate_sqlite_schema(engine)


def migrate_sqlite_schema(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "providerconfig" in table_names:
        _migrate_provider_config(engine, inspector)
    if "openbookblueprint" in table_names:
        _migrate_open_book_blueprint(engine, inspector)


def _migrate_provider_config(engine: Engine, inspector) -> None:
    columns = {column["name"] for column in inspector.get_columns("providerconfig")}
    with engine.begin() as connection:
        if "embedding_use_llm_credentials" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE providerconfig "
                "ADD COLUMN embedding_use_llm_credentials BOOLEAN NOT NULL DEFAULT 1"
            )
        if "rerank_use_llm_credentials" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE providerconfig "
                "ADD COLUMN rerank_use_llm_credentials BOOLEAN NOT NULL DEFAULT 1"
            )


def _migrate_open_book_blueprint(engine: Engine, inspector) -> None:
    columns = {column["name"] for column in inspector.get_columns("openbookblueprint")}
    with engine.begin() as connection:
        if "parent_id" not in columns:
            connection.exec_driver_sql("ALTER TABLE openbookblueprint ADD COLUMN parent_id INTEGER")
        if "status" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE openbookblueprint "
                "ADD COLUMN status VARCHAR NOT NULL DEFAULT 'SUCCEEDED'"
            )
        connection.exec_driver_sql(
            """
            UPDATE openbookblueprint
            SET status = UPPER(status)
            WHERE status IN ('pending', 'running', 'succeeded', 'failed')
            """
        )
        if "error_message" not in columns:
            connection.exec_driver_sql("ALTER TABLE openbookblueprint ADD COLUMN error_message VARCHAR")
        if "started_at" not in columns:
            connection.exec_driver_sql("ALTER TABLE openbookblueprint ADD COLUMN started_at DATETIME")
        if "finished_at" not in columns:
            connection.exec_driver_sql("ALTER TABLE openbookblueprint ADD COLUMN finished_at DATETIME")
