import asyncio

from mynovel.domain.models import ProviderConfig
from mynovel.provider_config_validation import (
    provider_model_fingerprint,
    validate_provider_config,
)


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


def test_provider_validation_requires_chat_and_records_optional_embedding() -> None:
    config = _provider_config()
    checker = FakeChecker()

    report = asyncio.run(validate_provider_config(config, None, checker))

    assert report.passed is True
    assert checker.calls == ["llm", "embedding"]
    assert [result.kind for result in report.results] == ["llm", "embedding"]
    assert report.validation.llm_fingerprint == provider_model_fingerprint(config, "llm")
    assert report.validation.embedding_fingerprint == provider_model_fingerprint(
        config, "embedding"
    )
    assert report.validation.rerank_fingerprint is None


def test_provider_validation_allows_save_when_optional_embedding_fails() -> None:
    config = _provider_config()
    checker = FakeChecker(failures={"embedding", "rerank"})

    report = asyncio.run(validate_provider_config(config, None, checker))

    assert report.passed is True
    assert checker.calls == ["llm", "embedding"]
    assert _status_for(report, "llm") == "passed"
    assert _status_for(report, "embedding") == "failed"
    assert report.validation.llm_fingerprint == provider_model_fingerprint(config, "llm")
    assert report.validation.embedding_fingerprint is None


def test_provider_validation_blocks_when_chat_fails() -> None:
    config = _provider_config()
    checker = FakeChecker(failures={"llm"})

    report = asyncio.run(validate_provider_config(config, None, checker))

    assert report.passed is False
    assert checker.calls == ["llm", "embedding"]
    assert _status_for(report, "llm") == "failed"


def test_provider_validation_skips_unconfigured_embedding() -> None:
    config = _provider_config(embedding_model="")
    checker = FakeChecker()

    report = asyncio.run(validate_provider_config(config, None, checker))

    assert report.passed is True
    assert checker.calls == ["llm"]
    assert _status_for(report, "embedding") == "skipped"
    assert "未配置检索模型" in _message_for(report, "embedding")


def _status_for(report, kind: str) -> str:
    return next(result.status for result in report.results if result.kind == kind)


def _message_for(report, kind: str) -> str:
    return next(result.message for result in report.results if result.kind == kind)


def _provider_config(
    *,
    llm_model: str = "gpt-test",
    embedding_model: str = "embedding-test",
    rerank_model: str = "rerank-test",
) -> ProviderConfig:
    return ProviderConfig(
        llm_base_url="https://llm.example.test/v1",
        llm_api_key="llm-key",
        llm_model=llm_model,
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model=embedding_model,
        rerank_use_llm_credentials=True,
        rerank_base_url="",
        rerank_model=rerank_model,
    )
