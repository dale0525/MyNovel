from http import HTTPStatus
from pathlib import Path

from sqlmodel import Session

from mynovel.api_provider_config import save_provider_config_json
from mynovel.db import create_engine_for_path
from mynovel.domain.models import ProviderConfig
from mynovel.domain.repositories import get_provider_config, get_provider_config_validation


class FakeChecker:
    def __init__(self, failures: set[str] | None = None) -> None:
        self.failures = failures or set()
        self.calls: list[str] = []

    async def check_chat(self, config: ProviderConfig) -> None:
        self.calls.append("llm")
        if "llm" in self.failures:
            raise RuntimeError("chat failed")

    async def check_embedding(self, config: ProviderConfig) -> None:
        self.calls.append("embedding")
        if "embedding" in self.failures:
            raise RuntimeError("embedding failed")

    async def check_rerank(self, config: ProviderConfig) -> None:
        self.calls.append("rerank")
        if "rerank" in self.failures:
            raise RuntimeError("rerank failed")


def test_save_provider_config_json_returns_validation_error_without_saving_config(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    checker = FakeChecker(failures={"rerank"})

    response = save_provider_config_json(db_path, _payload(), checker)

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["error"] == {
        "code": "provider_validation_failed",
        "message": "模型连接测试未全部通过。",
        "details": {},
    }
    assert response.body["validation"]["passed"] is False
    assert _validation_statuses(response.body) == {
        "llm": "passed",
        "embedding": "passed",
        "rerank": "failed",
    }
    assert _validation_message(response.body, "rerank") == "rerank failed"
    assert checker.calls == ["llm", "embedding", "rerank"]

    with Session(create_engine_for_path(db_path)) as session:
        saved = get_provider_config(session)
        validation = get_provider_config_validation(session)

    assert saved is None
    assert validation is not None
    assert validation.llm_fingerprint is not None
    assert validation.embedding_fingerprint is not None
    assert validation.rerank_fingerprint is None


def test_save_provider_config_json_retests_only_failed_rerank_after_partial_validation(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    first_checker = FakeChecker(failures={"rerank"})
    second_checker = FakeChecker()

    first_response = save_provider_config_json(db_path, _payload(), first_checker)
    second_response = save_provider_config_json(db_path, _payload(), second_checker)

    assert first_response.status == HTTPStatus.BAD_REQUEST
    assert second_response.status == HTTPStatus.OK
    assert second_checker.calls == ["rerank"]
    assert second_response.body["validation"]["passed"] is True
    assert _validation_statuses(second_response.body) == {
        "llm": "skipped",
        "embedding": "skipped",
        "rerank": "passed",
    }
    provider_config = second_response.body["providerConfig"]
    assert provider_config["llmBaseUrl"] == "https://api.test/v1"
    assert "llmApiKey" not in provider_config
    assert "embeddingApiKey" not in provider_config
    assert "rerankApiKey" not in provider_config

    with Session(create_engine_for_path(db_path)) as session:
        saved = get_provider_config(session)

    assert saved is not None
    assert saved.llm_model == "gpt"
    assert saved.embedding_model == "embed"
    assert saved.rerank_model == "rerank"


def _payload() -> dict[str, object]:
    return {
        "llmBaseUrl": "https://api.test/v1",
        "llmApiKey": "sk",
        "llmModel": "gpt",
        "embeddingUseLlmCredentials": True,
        "embeddingModel": "embed",
        "rerankUseLlmCredentials": True,
        "rerankModel": "rerank",
    }


def _validation_statuses(body: dict[str, object]) -> dict[str, str]:
    validation = body["validation"]
    assert isinstance(validation, dict)
    results = validation["results"]
    assert isinstance(results, list)
    return {result["kind"]: result["status"] for result in results}


def _validation_message(body: dict[str, object], kind: str) -> str:
    validation = body["validation"]
    assert isinstance(validation, dict)
    results = validation["results"]
    assert isinstance(results, list)
    for result in results:
        if result["kind"] == kind:
            return result["message"]
    raise AssertionError(f"Missing validation result for {kind}.")
