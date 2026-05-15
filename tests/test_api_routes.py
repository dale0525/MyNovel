from http import HTTPStatus
from pathlib import Path

import pytest
from sqlmodel import Session

from mynovel.api_routes import dispatch_api_get, read_api_json_body
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import ProviderConfig, ProviderConfigValidation
from mynovel.domain.repositories import save_provider_config, save_provider_config_validation
from mynovel.provider_config_validation import provider_model_fingerprint


def test_unknown_api_route_returns_json_error(tmp_path: Path) -> None:
    response = dispatch_api_get("/api/missing", "", tmp_path / "dev.sqlite")
    assert response.status == HTTPStatus.NOT_FOUND
    assert response.body["error"]["code"] == "not_found"


def test_bootstrap_requires_setup_without_provider(tmp_path: Path) -> None:
    response = dispatch_api_get("/api/app/bootstrap", "", tmp_path / "dev.sqlite")
    assert response.status == HTTPStatus.OK
    assert response.body["providerConfigured"] is False
    assert response.body["initialRoute"] == "/setup"


def test_bootstrap_requires_setup_with_empty_provider_validation(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    config = _provider_config()
    _save_provider_state(db_path, config, ProviderConfigValidation())

    response = dispatch_api_get("/api/app/bootstrap", "", db_path)

    assert response.status == HTTPStatus.OK
    assert response.body["providerConfigured"] is False
    assert response.body["initialRoute"] == "/setup"


def test_bootstrap_opens_home_with_matching_provider_fingerprints(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    config = _provider_config()
    _save_provider_state(
        db_path,
        config,
        ProviderConfigValidation(
            llm_fingerprint=provider_model_fingerprint(config, "llm"),
            embedding_fingerprint=provider_model_fingerprint(config, "embedding"),
            rerank_fingerprint=provider_model_fingerprint(config, "rerank"),
        ),
    )

    response = dispatch_api_get("/api/app/bootstrap", "", db_path)

    assert response.status == HTTPStatus.OK
    assert response.body["providerConfigured"] is True
    assert response.body["initialRoute"] == "/"


@pytest.mark.parametrize(
    ("content_length", "body"),
    [
        ("1", b"{"),
        ("1", b"\xff"),
        ("not-an-int", b"{}"),
        ("", b"{}"),
        ("10", b"{}"),
    ],
)
def test_read_api_json_body_returns_invalid_json_error(
    content_length: str,
    body: bytes,
) -> None:
    parsed_body, error = read_api_json_body(content_length, lambda length: body[:length])

    assert parsed_body == {}
    assert error is not None
    assert error.status == HTTPStatus.BAD_REQUEST
    assert error.body["error"]["code"] == "invalid_json"
    assert error.body["error"]["details"] == {}


def _provider_config() -> ProviderConfig:
    return ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_api_key="sk-test",
        llm_model="gpt-test",
        embedding_base_url="https://api.example.test/v1",
        embedding_model="text-embedding-test",
        rerank_base_url="https://rerank.example.test/v1",
        rerank_model="rerank-test",
    )


def _save_provider_state(
    db_path: Path,
    config: ProviderConfig,
    validation: ProviderConfigValidation,
) -> None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        save_provider_config(session, config)
        save_provider_config_validation(session, validation)
