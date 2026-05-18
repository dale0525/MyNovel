from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Literal, Protocol

from mynovel.domain.models import ProviderConfig, ProviderConfigValidation
from mynovel.llm.openai_compatible import (
    ChatRequest,
    EmbeddingRequest,
    OpenAICompatibleClient,
    RerankRequest,
)

ProviderModelKind = Literal["llm", "embedding", "rerank"]
ProviderCheckStatus = Literal["passed", "failed", "skipped"]


@dataclass(frozen=True)
class ProviderCheckResult:
    kind: ProviderModelKind
    label: str
    status: ProviderCheckStatus
    message: str


@dataclass(frozen=True)
class ProviderValidationReport:
    results: list[ProviderCheckResult]
    validation: ProviderConfigValidation

    @property
    def passed(self) -> bool:
        return all(result.status != "failed" for result in self.results if result.kind == "llm")


class ProviderConfigChecker(Protocol):
    async def check_chat(self, config: ProviderConfig) -> None: ...

    async def check_embedding(self, config: ProviderConfig) -> None: ...

    async def check_rerank(self, config: ProviderConfig) -> None: ...


class OpenAICompatibleProviderConfigChecker:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    async def check_chat(self, config: ProviderConfig) -> None:
        base_url, api_key, model = _effective_fields(config, "llm")
        client = OpenAICompatibleClient(base_url=base_url, api_key=api_key, timeout=self.timeout)
        await client.chat(
            ChatRequest(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                temperature=0,
                extra={"max_tokens": 1},
            )
        )

    async def check_embedding(self, config: ProviderConfig) -> None:
        base_url, api_key, model = _effective_fields(config, "embedding")
        client = OpenAICompatibleClient(base_url=base_url, api_key=api_key, timeout=self.timeout)
        await client.embeddings(EmbeddingRequest(model=model, input="ping"))

    async def check_rerank(self, config: ProviderConfig) -> None:
        base_url, api_key, model = _effective_fields(config, "rerank")
        client = OpenAICompatibleClient(base_url=base_url, api_key=api_key, timeout=self.timeout)
        await client.rerank(
            RerankRequest(
                model=model,
                query="ping",
                documents=["ping", "pong"],
                top_n=1,
            )
        )


async def validate_provider_config(
    config: ProviderConfig,
    previous_validation: ProviderConfigValidation | None,
    checker: ProviderConfigChecker,
) -> ProviderValidationReport:
    validation = _copy_validation(previous_validation)
    results: list[ProviderCheckResult] = []

    for kind in ("llm", "embedding"):
        if kind == "embedding" and not config.embedding_model.strip():
            validation.embedding_fingerprint = None
            results.append(
                ProviderCheckResult(
                    kind,
                    _model_label(kind),
                    "skipped",
                    "未配置检索模型，章节生产将使用本地检索。",
                )
            )
            continue

        missing_message = _missing_required_message(config, kind)
        if missing_message:
            _clear_fingerprint(validation, kind)
            results.append(ProviderCheckResult(kind, _model_label(kind), "failed", missing_message))
            continue

        fingerprint = provider_model_fingerprint(config, kind)
        if _fingerprint_for(validation, kind) == fingerprint:
            results.append(
                ProviderCheckResult(
                    kind,
                    _model_label(kind),
                    "skipped",
                    "沿用上次通过结果",
                )
            )
            continue

        try:
            await _run_check(checker, config, kind)
        except Exception as error:  # noqa: BLE001
            _clear_fingerprint(validation, kind)
            results.append(
                ProviderCheckResult(
                    kind,
                    _model_label(kind),
                    "failed",
                    str(error) or "连接测试失败",
                )
            )
            continue

        _set_fingerprint(validation, kind, fingerprint)
        results.append(ProviderCheckResult(kind, _model_label(kind), "passed", "连接测试通过"))

    return ProviderValidationReport(results=results, validation=validation)


def provider_model_fingerprint(config: ProviderConfig, kind: ProviderModelKind) -> str:
    base_url, api_key, model = _effective_fields(config, kind)
    payload = {
        "kind": kind,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _copy_validation(
    validation: ProviderConfigValidation | None,
) -> ProviderConfigValidation:
    if validation is None:
        return ProviderConfigValidation()
    return ProviderConfigValidation(
        id=validation.id,
        llm_fingerprint=validation.llm_fingerprint,
        embedding_fingerprint=validation.embedding_fingerprint,
        rerank_fingerprint=validation.rerank_fingerprint,
        created_at=validation.created_at,
        updated_at=validation.updated_at,
    )


def _effective_fields(config: ProviderConfig, kind: ProviderModelKind) -> tuple[str, str, str]:
    if kind == "llm":
        return (
            config.llm_base_url.strip(),
            (config.llm_api_key or "").strip(),
            config.llm_model.strip(),
        )
    if kind == "embedding":
        return (
            config.resolved_embedding_base_url().strip(),
            (config.resolved_embedding_api_key() or "").strip(),
            config.embedding_model.strip(),
        )
    return (
        (config.resolved_rerank_base_url() or "").strip(),
        (config.resolved_rerank_api_key() or "").strip(),
        (config.rerank_model or "").strip(),
    )


def _missing_required_message(config: ProviderConfig, kind: ProviderModelKind) -> str | None:
    base_url, api_key, model = _effective_fields(config, kind)
    label = _model_label(kind)
    if not base_url:
        return f"请填写{label}接口地址。"
    if not api_key:
        return f"请填写{label}访问密钥。"
    if not model:
        return f"请填写{label}名称。"
    return None


async def _run_check(
    checker: ProviderConfigChecker,
    config: ProviderConfig,
    kind: ProviderModelKind,
) -> None:
    if kind == "llm":
        await checker.check_chat(config)
    elif kind == "embedding":
        await checker.check_embedding(config)
    else:
        await checker.check_rerank(config)


def _fingerprint_for(
    validation: ProviderConfigValidation,
    kind: ProviderModelKind,
) -> str | None:
    if kind == "llm":
        return validation.llm_fingerprint
    if kind == "embedding":
        return validation.embedding_fingerprint
    return validation.rerank_fingerprint


def _set_fingerprint(
    validation: ProviderConfigValidation,
    kind: ProviderModelKind,
    fingerprint: str,
) -> None:
    if kind == "llm":
        validation.llm_fingerprint = fingerprint
    elif kind == "embedding":
        validation.embedding_fingerprint = fingerprint
    else:
        validation.rerank_fingerprint = fingerprint


def _clear_fingerprint(
    validation: ProviderConfigValidation,
    kind: ProviderModelKind,
) -> None:
    if kind == "llm":
        validation.llm_fingerprint = None
    elif kind == "embedding":
        validation.embedding_fingerprint = None
    else:
        validation.rerank_fingerprint = None


def _model_label(kind: ProviderModelKind) -> str:
    return {
        "llm": "对话模型",
        "embedding": "检索模型",
        "rerank": "重排模型",
    }[kind]
