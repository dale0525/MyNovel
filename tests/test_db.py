from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import BlueprintStatus, OpenBookBlueprint, ProviderConfig
from mynovel.domain.repositories import add_open_book_blueprint, save_provider_config


def test_create_db_and_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    engine = create_engine_for_path(db_path)

    create_db_and_tables(engine)

    assert db_path.exists()


def test_create_db_and_tables_migrates_provider_config_reuse_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    engine = create_engine_for_path(db_path)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE providerconfig (
              id INTEGER NOT NULL PRIMARY KEY,
              llm_base_url VARCHAR NOT NULL,
              llm_api_key VARCHAR,
              llm_model VARCHAR NOT NULL,
              embedding_base_url VARCHAR NOT NULL,
              embedding_api_key VARCHAR,
              embedding_model VARCHAR NOT NULL,
              rerank_base_url VARCHAR,
              rerank_api_key VARCHAR,
              rerank_model VARCHAR,
              created_at DATETIME NOT NULL,
              updated_at DATETIME NOT NULL
            )
            """
        )

    create_db_and_tables(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("providerconfig")}
    assert "embedding_use_llm_credentials" in columns
    assert "rerank_use_llm_credentials" in columns

    with Session(engine) as session:
        saved = save_provider_config(
            session,
            ProviderConfig(
                llm_base_url="https://api.example.test/v1",
                llm_model="gpt-test",
                embedding_use_llm_credentials=True,
                embedding_base_url="",
                embedding_model="text-embedding-test",
            ),
        )

    assert saved.resolved_embedding_base_url() == "https://api.example.test/v1"


def test_create_db_and_tables_migrates_open_book_blueprint_status_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    engine = create_engine_for_path(db_path)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE openbookblueprint (
              id INTEGER NOT NULL PRIMARY KEY,
              idea VARCHAR NOT NULL,
              version INTEGER NOT NULL,
              instruction VARCHAR,
              content JSON,
              raw_response VARCHAR NOT NULL,
              parse_error VARCHAR,
              created_at DATETIME NOT NULL
            )
            """
        )

    create_db_and_tables(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("openbookblueprint")}
    assert "parent_id" in columns
    assert "status" in columns
    assert "error_message" in columns
    assert "started_at" in columns
    assert "finished_at" in columns

    with Session(engine) as session:
        saved = add_open_book_blueprint(
            session,
            OpenBookBlueprint(
                idea="失意档案员重建禁书馆",
                version=1,
                status=BlueprintStatus.PENDING,
                content={},
                raw_response="",
            ),
        )

    assert saved.status == BlueprintStatus.PENDING
