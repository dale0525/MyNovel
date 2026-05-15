from http import HTTPStatus
from pathlib import Path

from sqlmodel import Session

from mynovel.api_routes import dispatch_api_get
from mynovel.db import create_engine_for_path
from mynovel.domain.models import ProviderConfig
from mynovel.domain.repositories import get_provider_config, get_provider_config_validation
from mynovel.provider_config_server import handle_provider_config_post


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


def test_provider_config_failure_does_not_save_config_but_keeps_passed_checks(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    checker = FakeChecker(failures={"rerank"})

    response = handle_provider_config_post(db_path, _form(), checker)

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.redirect_to is None
    assert "rerank failed" in response.body
    assert checker.calls == ["llm", "embedding", "rerank"]

    with Session(create_engine_for_path(db_path)) as session:
        assert get_provider_config(session) is None
        validation = get_provider_config_validation(session)

    assert validation is not None
    assert validation.llm_fingerprint is not None
    assert validation.embedding_fingerprint is not None
    assert validation.rerank_fingerprint is None


def test_provider_config_second_save_only_retests_previous_failures(tmp_path: Path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    first_checker = FakeChecker(failures={"rerank"})
    second_checker = FakeChecker()

    handle_provider_config_post(db_path, _form(), first_checker)
    response = handle_provider_config_post(db_path, _form(), second_checker)

    assert response.status == HTTPStatus.SEE_OTHER
    assert response.redirect_to is not None
    assert response.redirect_to.startswith("/?message=")
    assert second_checker.calls == ["rerank"]

    with Session(create_engine_for_path(db_path)) as session:
        saved = get_provider_config(session)

    assert saved is not None
    assert saved.rerank_model == "rerank-test"


def test_provider_config_save_tests_changed_previously_passed_model_again(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    first_checker = FakeChecker(failures={"rerank"})
    second_checker = FakeChecker()
    changed_form = _form()
    changed_form["llm_model"] = "gpt-new"

    handle_provider_config_post(db_path, _form(), first_checker)
    response = handle_provider_config_post(db_path, changed_form, second_checker)

    assert response.status == HTTPStatus.SEE_OTHER
    assert second_checker.calls == ["llm", "rerank"]


def test_failed_edit_keeps_existing_valid_provider_config_active(tmp_path: Path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    original_form = _form()
    changed_form = _form()
    changed_form["llm_model"] = "gpt-new"
    changed_form["rerank_model"] = "rerank-new"
    changed_checker = FakeChecker(failures={"rerank"})

    saved_response = handle_provider_config_post(db_path, original_form, FakeChecker())
    failed_response = handle_provider_config_post(
        db_path,
        changed_form,
        changed_checker,
    )

    assert saved_response.status == HTTPStatus.SEE_OTHER
    assert failed_response.status == HTTPStatus.BAD_REQUEST
    assert changed_checker.calls == ["llm", "rerank"]
    assert "rerank failed" in failed_response.body

    with Session(create_engine_for_path(db_path)) as session:
        saved = get_provider_config(session)

    assert saved is not None
    assert saved.llm_model == "gpt-test"
    assert saved.rerank_model == "rerank-test"

    bootstrap = dispatch_api_get("/api/app/bootstrap", "", db_path)
    assert bootstrap.body["providerConfigured"] is True
    assert bootstrap.body["initialRoute"] == "/"


def _form() -> dict[str, str]:
    return {
        "llm_base_url": "https://llm.example.test/v1",
        "llm_api_key": "llm-key",
        "llm_model": "gpt-test",
        "embedding_model": "embedding-test",
        "rerank_model": "rerank-test",
    }
