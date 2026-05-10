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


def test_provider_config_can_reuse_llm_endpoint_for_embedding_and_rerank() -> None:
    config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_api_key="sk-llm",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_api_key=None,
        embedding_model="text-embedding-test",
        rerank_use_llm_credentials=True,
        rerank_base_url=None,
        rerank_api_key=None,
        rerank_model="rerank-test",
    )

    assert config.resolved_embedding_base_url() == "https://api.example.test/v1"
    assert config.resolved_embedding_api_key() == "sk-llm"
    assert config.resolved_rerank_base_url() == "https://api.example.test/v1"
    assert config.resolved_rerank_api_key() == "sk-llm"
