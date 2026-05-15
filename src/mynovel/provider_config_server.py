from __future__ import annotations

import asyncio
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from urllib.parse import quote

from sqlmodel import Session

from mynovel.api_serializers import is_provider_config_validated
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.repositories import (
    get_provider_config,
    get_provider_config_validation,
    save_provider_config,
    save_provider_config_validation,
)
from mynovel.i18n import t
from mynovel.product_views import render_model_setup_page
from mynovel.provider_config_forms import provider_config_from_form
from mynovel.provider_config_validation import (
    OpenAICompatibleProviderConfigChecker,
    ProviderConfigChecker,
    ProviderValidationReport,
    validate_provider_config,
)


@dataclass(frozen=True)
class ProviderConfigPostResponse:
    status: HTTPStatus
    body: str = ""
    redirect_to: str | None = None


def handle_provider_config_post(
    db_path: Path,
    form: dict[str, str],
    checker: ProviderConfigChecker | None = None,
) -> ProviderConfigPostResponse:
    config = provider_config_from_form(form)
    model_checker = checker or OpenAICompatibleProviderConfigChecker()
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)

    with Session(engine) as session:
        saved_config = get_provider_config(session)
        saved_validation = get_provider_config_validation(session)
        saved_config_valid = is_provider_config_validated(saved_config, saved_validation)
        report = asyncio.run(
            validate_provider_config(
                config,
                saved_validation,
                model_checker,
            )
        )
        if not report.passed:
            if not saved_config_valid:
                save_provider_config_validation(session, report.validation)
            message = _validation_failure_message(report)
            return ProviderConfigPostResponse(
                status=HTTPStatus.BAD_REQUEST,
                body=render_model_setup_page(
                    db_path,
                    config,
                    message,
                    validation_report=report,
                ),
            )

        save_provider_config_validation(session, report.validation)
        save_provider_config(session, config)

    return ProviderConfigPostResponse(
        status=HTTPStatus.SEE_OTHER,
        redirect_to=f"/?message={quote(t('provider.saved'))}",
    )


def _validation_failure_message(report: ProviderValidationReport) -> str:
    failures = [
        f"{result.label}：{result.message}"
        for result in report.results
        if result.status == "failed"
    ]
    if not failures:
        return "模型连接测试未全部通过。"
    return "模型连接测试未全部通过：" + "；".join(failures)
