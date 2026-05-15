from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import ProviderConfig, ProviderConfigValidation
from mynovel.domain.repositories import (
    get_provider_config,
    get_provider_config_validation,
    save_provider_config,
    save_provider_config_validation,
)
from mynovel.provider_config_status import is_provider_config_complete


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


def test_provider_config_is_complete_only_with_all_required_models() -> None:
    missing_rerank = ProviderConfig(
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
        rerank_model="",
    )
    complete = ProviderConfig(
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

    assert is_provider_config_complete(None) is False
    assert is_provider_config_complete(missing_rerank) is False
    assert is_provider_config_complete(complete) is True


def test_provider_config_validation_round_trips_through_sqlite(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "mynovel.sqlite")
    create_db_and_tables(engine)

    with Session(engine) as session:
        saved = save_provider_config_validation(
            session,
            ProviderConfigValidation(
                llm_fingerprint="llm-pass",
                embedding_fingerprint="embedding-pass",
                rerank_fingerprint="rerank-pass",
            ),
        )
        loaded = get_provider_config_validation(session)

    assert saved.id == 1
    assert loaded is not None
    assert loaded.llm_fingerprint == "llm-pass"
    assert loaded.embedding_fingerprint == "embedding-pass"
    assert loaded.rerank_fingerprint == "rerank-pass"
