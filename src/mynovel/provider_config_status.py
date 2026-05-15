from __future__ import annotations

from mynovel.domain.models import ProviderConfig


def is_provider_config_complete(provider_config: ProviderConfig | None) -> bool:
    return bool(
        provider_config
        and provider_config.llm_base_url.strip()
        and provider_config.llm_api_key
        and provider_config.llm_model.strip()
        and provider_config.resolved_embedding_base_url().strip()
        and provider_config.resolved_embedding_api_key()
        and provider_config.embedding_model.strip()
        and (provider_config.resolved_rerank_base_url() or "").strip()
        and provider_config.resolved_rerank_api_key()
        and (provider_config.rerank_model or "").strip()
    )
