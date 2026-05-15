import json
from http import HTTPStatus
from pathlib import Path

from sqlmodel import Session

from mynovel.api_provider_config import (
    get_provider_config_json,
    provider_config_from_json,
    save_provider_config_json,
)
from mynovel.api_routes import dispatch_api_get, dispatch_api_post
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
    assert response.body["saved"] is False
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
    assert second_response.body["saved"] is True
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


def test_validate_endpoint_tests_and_saves_config_on_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    checker = FakeChecker()
    monkeypatch.setattr(
        "mynovel.api_provider_config.OpenAICompatibleProviderConfigChecker",
        lambda: checker,
    )

    response = dispatch_api_post("/api/provider-config/validate", _payload(), db_path)

    assert response.status == HTTPStatus.OK
    assert response.body["saved"] is True
    assert checker.calls == ["llm", "embedding", "rerank"]
    with Session(create_engine_for_path(db_path)) as session:
        saved = get_provider_config(session)

    assert saved is not None
    assert saved.llm_model == "gpt"


def test_failed_json_edit_keeps_existing_valid_provider_config_active(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    original_payload = _payload(llm_model="gpt-a", rerank_model="rerank-a")
    changed_payload = _payload(llm_model="gpt-b", rerank_model="rerank-b")
    changed_checker = FakeChecker(failures={"rerank"})

    saved_response = save_provider_config_json(db_path, original_payload, FakeChecker())
    failed_response = save_provider_config_json(db_path, changed_payload, changed_checker)

    assert saved_response.status == HTTPStatus.OK
    assert saved_response.body["saved"] is True
    assert failed_response.status == HTTPStatus.BAD_REQUEST
    assert failed_response.body["error"]["code"] == "provider_validation_failed"
    assert failed_response.body["saved"] is False
    assert changed_checker.calls == ["llm", "rerank"]

    with Session(create_engine_for_path(db_path)) as session:
        saved = get_provider_config(session)

    assert saved is not None
    assert saved.llm_model == "gpt-a"
    assert saved.rerank_model == "rerank-a"

    bootstrap = dispatch_api_get("/api/app/bootstrap", "", db_path)
    assert bootstrap.body["providerConfigured"] is True
    assert bootstrap.body["initialRoute"] == "/"


def test_provider_config_payload_exposes_key_presence_without_key_values(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    payload = _payload(
        llm_api_key="llm-secret",
        embedding_use_llm_credentials=False,
        embedding_base_url="https://embedding.test/v1",
        embedding_api_key="embedding-secret",
        rerank_use_llm_credentials=True,
        rerank_api_key="rerank-secret",
    )

    save_response = save_provider_config_json(db_path, payload, FakeChecker())
    get_response = get_provider_config_json(db_path)

    assert save_response.status == HTTPStatus.OK
    assert save_response.body["saved"] is True
    _assert_provider_config_key_state(
        save_response.body["providerConfig"],
        has_llm=True,
        has_embedding=True,
        has_rerank=True,
    )
    _assert_provider_config_key_state(
        get_response.body["providerConfig"],
        has_llm=True,
        has_embedding=True,
        has_rerank=True,
    )
    _assert_no_secret_payload(save_response.body, "llm-secret")
    _assert_no_secret_payload(save_response.body, "embedding-secret")
    _assert_no_secret_payload(save_response.body, "rerank-secret")
    _assert_no_secret_payload(get_response.body, "llm-secret")
    _assert_no_secret_payload(get_response.body, "embedding-secret")
    _assert_no_secret_payload(get_response.body, "rerank-secret")


def test_validation_error_redacts_submitted_keys_from_messages(tmp_path: Path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    secret = "sk-secret-redacted"
    checker = SecretLeakingChecker(secret)

    response = save_provider_config_json(db_path, _payload(llm_api_key=secret), checker)

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["saved"] is False
    _assert_no_secret_payload(response.body, secret)
    assert "[redacted]" in _validation_message(response.body, "rerank")


def test_validation_error_redacts_raw_submitted_embedding_key_when_inherited(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    secret = "submitted-embedding-secret"
    checker = ModelSecretLeakingChecker("embedding", secret)

    response = save_provider_config_json(
        db_path,
        _payload(
            embedding_use_llm_credentials=True,
            embedding_api_key=secret,
        ),
        checker,
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["saved"] is False
    _assert_no_secret_payload(response.body, secret)
    assert "[redacted]" in _validation_message(response.body, "embedding")


def test_validation_error_redacts_raw_submitted_rerank_key_when_inherited(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    secret = "submitted-rerank-secret"
    checker = ModelSecretLeakingChecker("rerank", secret)

    response = save_provider_config_json(
        db_path,
        _payload(
            rerank_use_llm_credentials=True,
            rerank_api_key=secret,
        ),
        checker,
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["saved"] is False
    _assert_no_secret_payload(response.body, secret)
    assert "[redacted]" in _validation_message(response.body, "rerank")


def test_keyless_llm_edit_reuses_existing_llm_api_key(tmp_path: Path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    original_key = "llm-existing-secret"

    save_provider_config_json(
        db_path,
        _payload(llm_api_key=original_key, llm_model="gpt-a"),
        FakeChecker(),
    )
    response = save_provider_config_json(
        db_path,
        _payload(llm_api_key=None, llm_model="gpt-b"),
        FieldAssertingChecker({"llm_api_key": original_key}),
    )

    assert response.status == HTTPStatus.OK
    assert response.body["saved"] is True
    _assert_no_secret_payload(response.body, original_key)

    with Session(create_engine_for_path(db_path)) as session:
        saved = get_provider_config(session)

    assert saved is not None
    assert saved.llm_model == "gpt-b"
    assert saved.llm_api_key == original_key


def test_keyless_edit_reuses_existing_dedicated_embedding_and_rerank_keys(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    llm_key = "llm-secret"
    embedding_key = "embedding-secret"
    rerank_key = "rerank-secret"

    save_provider_config_json(
        db_path,
        _payload(
            llm_api_key=llm_key,
            embedding_use_llm_credentials=False,
            embedding_base_url="https://embedding.test/v1",
            embedding_api_key=embedding_key,
            embedding_model="embed-a",
            rerank_use_llm_credentials=False,
            rerank_base_url="https://rerank.test/v1",
            rerank_api_key=rerank_key,
            rerank_model="rerank-a",
        ),
        FakeChecker(),
    )
    response = save_provider_config_json(
        db_path,
        _payload(
            llm_api_key=None,
            embedding_use_llm_credentials=False,
            embedding_base_url="https://embedding.test/v1",
            embedding_model="embed-b",
            rerank_use_llm_credentials=False,
            rerank_base_url="https://rerank.test/v1",
            rerank_model="rerank-b",
        ),
        FieldAssertingChecker(
            {
                "embedding_api_key": embedding_key,
                "resolved_embedding_api_key": embedding_key,
                "rerank_api_key": rerank_key,
                "resolved_rerank_api_key": rerank_key,
            }
        ),
    )

    assert response.status == HTTPStatus.OK
    assert response.body["saved"] is True
    _assert_provider_config_key_state(
        response.body["providerConfig"],
        has_llm=True,
        has_embedding=True,
        has_rerank=True,
    )
    _assert_no_secret_payload(response.body, llm_key)
    _assert_no_secret_payload(response.body, embedding_key)
    _assert_no_secret_payload(response.body, rerank_key)

    with Session(create_engine_for_path(db_path)) as session:
        saved = get_provider_config(session)

    assert saved is not None
    assert saved.llm_api_key == llm_key
    assert saved.embedding_api_key == embedding_key
    assert saved.embedding_model == "embed-b"
    assert saved.rerank_api_key == rerank_key
    assert saved.rerank_model == "rerank-b"


def test_inherited_credentials_clear_submitted_dedicated_api_keys(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    llm_key = "llm-secret"
    dedicated_embedding_key = "submitted-embedding-secret"
    dedicated_rerank_key = "submitted-rerank-secret"

    save_provider_config_json(
        db_path,
        _payload(
            llm_api_key=llm_key,
            embedding_use_llm_credentials=False,
            embedding_base_url="https://embedding.test/v1",
            embedding_api_key="old-embedding-secret",
            rerank_use_llm_credentials=False,
            rerank_base_url="https://rerank.test/v1",
            rerank_api_key="old-rerank-secret",
        ),
        FakeChecker(),
    )
    response = save_provider_config_json(
        db_path,
        _payload(
            llm_api_key=None,
            embedding_use_llm_credentials=True,
            embedding_base_url="https://ignored-embedding.test/v1",
            embedding_api_key=dedicated_embedding_key,
            rerank_use_llm_credentials=True,
            rerank_base_url="https://ignored-rerank.test/v1",
            rerank_api_key=dedicated_rerank_key,
        ),
        FieldAssertingChecker(
            {
                "embedding_api_key": None,
                "resolved_embedding_api_key": llm_key,
                "rerank_api_key": None,
                "resolved_rerank_api_key": llm_key,
            }
        ),
    )

    assert response.status == HTTPStatus.OK
    assert response.body["saved"] is True
    _assert_provider_config_key_state(
        response.body["providerConfig"],
        has_llm=True,
        has_embedding=True,
        has_rerank=True,
    )
    _assert_no_secret_payload(response.body, llm_key)
    _assert_no_secret_payload(response.body, dedicated_embedding_key)
    _assert_no_secret_payload(response.body, dedicated_rerank_key)

    with Session(create_engine_for_path(db_path)) as session:
        saved = get_provider_config(session)

    assert saved is not None
    assert saved.llm_api_key == llm_key
    assert saved.embedding_use_llm_credentials is True
    assert saved.embedding_api_key is None
    assert saved.rerank_use_llm_credentials is True
    assert saved.rerank_api_key is None


def test_provider_config_from_json_strips_string_booleans() -> None:
    config = provider_config_from_json(
        _payload(
            embedding_use_llm_credentials=" true ",
            rerank_use_llm_credentials=" false ",
        )
    )

    assert config.embedding_use_llm_credentials is True
    assert config.rerank_use_llm_credentials is False


def _payload(
    *,
    llm_api_key: str | None = "sk",
    llm_model: str = "gpt",
    embedding_use_llm_credentials: bool | str = True,
    embedding_base_url: str = "",
    embedding_api_key: str | None = None,
    embedding_model: str = "embed",
    rerank_use_llm_credentials: bool | str = True,
    rerank_base_url: str | None = None,
    rerank_api_key: str | None = None,
    rerank_model: str = "rerank",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "llmBaseUrl": "https://api.test/v1",
        "llmModel": llm_model,
        "embeddingUseLlmCredentials": embedding_use_llm_credentials,
        "embeddingBaseUrl": embedding_base_url,
        "embeddingModel": embedding_model,
        "rerankUseLlmCredentials": rerank_use_llm_credentials,
        "rerankModel": rerank_model,
    }
    if llm_api_key is not None:
        payload["llmApiKey"] = llm_api_key
    if embedding_api_key is not None:
        payload["embeddingApiKey"] = embedding_api_key
    if rerank_base_url is not None:
        payload["rerankBaseUrl"] = rerank_base_url
    if rerank_api_key is not None:
        payload["rerankApiKey"] = rerank_api_key
    return payload


class FieldAssertingChecker(FakeChecker):
    def __init__(self, expected: dict[str, str | None]) -> None:
        super().__init__()
        self.expected = expected

    async def check_chat(self, config: ProviderConfig) -> None:
        self._assert_expected("llm_api_key", config.llm_api_key)
        await super().check_chat(config)

    async def check_embedding(self, config: ProviderConfig) -> None:
        self._assert_expected("embedding_api_key", config.embedding_api_key)
        self._assert_expected("resolved_embedding_api_key", config.resolved_embedding_api_key())
        await super().check_embedding(config)

    async def check_rerank(self, config: ProviderConfig) -> None:
        self._assert_expected("rerank_api_key", config.rerank_api_key)
        self._assert_expected("resolved_rerank_api_key", config.resolved_rerank_api_key())
        await super().check_rerank(config)

    def _assert_expected(self, name: str, actual: str | None) -> None:
        if name in self.expected:
            assert actual == self.expected[name]


class SecretLeakingChecker(FakeChecker):
    def __init__(self, secret: str) -> None:
        super().__init__()
        self.secret = secret

    async def check_rerank(self, config: ProviderConfig) -> None:
        self.calls.append("rerank")
        raise RuntimeError(f"rerank failed for {self.secret}")


class ModelSecretLeakingChecker(FakeChecker):
    def __init__(self, kind: str, secret: str) -> None:
        super().__init__()
        self.kind = kind
        self.secret = secret

    async def check_embedding(self, config: ProviderConfig) -> None:
        self.calls.append("embedding")
        if self.kind == "embedding":
            raise RuntimeError(f"embedding failed for {self.secret}")

    async def check_rerank(self, config: ProviderConfig) -> None:
        self.calls.append("rerank")
        if self.kind == "rerank":
            raise RuntimeError(f"rerank failed for {self.secret}")


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


def _assert_provider_config_key_state(
    provider_config: object,
    *,
    has_llm: bool,
    has_embedding: bool,
    has_rerank: bool,
) -> None:
    assert isinstance(provider_config, dict)
    assert "llmApiKey" not in provider_config
    assert "embeddingApiKey" not in provider_config
    assert "rerankApiKey" not in provider_config
    assert provider_config["hasLlmApiKey"] is has_llm
    assert provider_config["hasEmbeddingApiKey"] is has_embedding
    assert provider_config["hasRerankApiKey"] is has_rerank


def _assert_no_secret_payload(body: dict[str, object], secret: str) -> None:
    assert secret not in json.dumps(body, ensure_ascii=False)
