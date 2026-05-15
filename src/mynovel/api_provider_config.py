from __future__ import annotations

import asyncio
from http import HTTPStatus
from pathlib import Path
from typing import Any

from sqlmodel import Session

from mynovel.api_errors import ApiResponse
from mynovel.api_serializers import is_provider_config_validated
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import ProviderConfig
from mynovel.domain.repositories import (
    get_provider_config,
    get_provider_config_validation,
    save_provider_config,
    save_provider_config_validation,
)
from mynovel.provider_config_validation import (
    OpenAICompatibleProviderConfigChecker,
    ProviderConfigChecker,
    ProviderValidationReport,
    validate_provider_config,
)


def provider_config_from_json(payload: dict[str, Any]) -> ProviderConfig:
    return ProviderConfig(
        llm_base_url=_str_value(payload, "llmBaseUrl"),
        llm_api_key=_optional_str_value(payload, "llmApiKey"),
        llm_model=_str_value(payload, "llmModel"),
        embedding_use_llm_credentials=_bool_value(
            payload,
            "embeddingUseLlmCredentials",
            default=True,
        ),
        embedding_base_url=_str_value(payload, "embeddingBaseUrl"),
        embedding_api_key=_optional_str_value(payload, "embeddingApiKey"),
        embedding_model=_str_value(payload, "embeddingModel"),
        rerank_use_llm_credentials=_bool_value(
            payload,
            "rerankUseLlmCredentials",
            default=True,
        ),
        rerank_base_url=_optional_str_value(payload, "rerankBaseUrl"),
        rerank_api_key=_optional_str_value(payload, "rerankApiKey"),
        rerank_model=_optional_str_value(payload, "rerankModel"),
    )


def provider_config_payload(config: ProviderConfig) -> dict[str, Any]:
    return {
        "llmBaseUrl": config.llm_base_url,
        "llmModel": config.llm_model,
        "embeddingUseLlmCredentials": config.embedding_use_llm_credentials,
        "embeddingBaseUrl": config.embedding_base_url,
        "embeddingModel": config.embedding_model,
        "rerankUseLlmCredentials": config.rerank_use_llm_credentials,
        "rerankBaseUrl": config.rerank_base_url,
        "rerankModel": config.rerank_model,
    }


def validation_report_payload(report: ProviderValidationReport) -> dict[str, Any]:
    return {
        "passed": report.passed,
        "results": [
            {
                "kind": result.kind,
                "label": result.label,
                "status": result.status,
                "message": result.message,
            }
            for result in report.results
        ],
    }


def get_provider_config_json(db_path: Path) -> ApiResponse:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        config = get_provider_config(session)
        validation = get_provider_config_validation(session)
        validated = is_provider_config_validated(config, validation)

    return ApiResponse(
        HTTPStatus.OK,
        {
            "providerConfig": provider_config_payload(config) if config is not None else None,
            "validated": validated,
        },
    )


def save_provider_config_json(
    db_path: Path,
    payload: dict[str, Any],
    checker: ProviderConfigChecker | None = None,
) -> ApiResponse:
    config = provider_config_from_json(payload)
    model_checker = checker or OpenAICompatibleProviderConfigChecker()
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)

    with Session(engine) as session:
        saved_config = get_provider_config(session)
        saved_validation = get_provider_config_validation(session)
        saved_config_valid = is_provider_config_validated(saved_config, saved_validation)
        report = asyncio.run(validate_provider_config(config, saved_validation, model_checker))

        if not report.passed:
            if not saved_config_valid:
                save_provider_config_validation(session, report.validation)
            return ApiResponse(
                HTTPStatus.BAD_REQUEST,
                {
                    "error": {
                        "code": "provider_validation_failed",
                        "message": "模型连接测试未全部通过。",
                        "details": {},
                    },
                    "validation": validation_report_payload(report),
                },
            )

        save_provider_config_validation(session, report.validation)
        saved = save_provider_config(session, config)

    return ApiResponse(
        HTTPStatus.OK,
        {
            "providerConfig": provider_config_payload(saved),
            "validation": validation_report_payload(report),
        },
    )


def _str_value(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _optional_str_value(payload: dict[str, Any], key: str) -> str | None:
    value = _str_value(payload, key)
    return value or None


def _bool_value(payload: dict[str, Any], key: str, *, default: bool) -> bool:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)
