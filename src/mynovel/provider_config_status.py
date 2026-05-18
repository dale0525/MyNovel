from __future__ import annotations

from typing import TypeGuard

from mynovel.domain.models import ProviderConfig


def is_provider_config_complete(
    provider_config: ProviderConfig | None,
) -> TypeGuard[ProviderConfig]:
    return bool(
        provider_config
        and provider_config.llm_base_url.strip()
        and provider_config.llm_api_key
        and provider_config.llm_model.strip()
    )
