from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import ProviderConfig
from mynovel.domain.repositories import get_provider_config, save_provider_config


def test_provider_config_round_trips_through_sqlite(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        saved = save_provider_config(
            session,
            ProviderConfig(
                llm_base_url="https://api.example.test/v1",
                llm_api_key="sk-test",
                llm_model="gpt-test",
                embedding_base_url="https://api.example.test/v1",
                embedding_model="text-embedding-test",
                rerank_base_url="https://rerank.example.test/v1",
                rerank_model="rerank-test",
            ),
        )
        loaded = get_provider_config(session)

    assert saved.id == 1
    assert loaded is not None
    assert loaded.llm_model == "gpt-test"
    assert loaded.embedding_model == "text-embedding-test"
    assert loaded.rerank_model == "rerank-test"
