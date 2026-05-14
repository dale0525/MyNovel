from __future__ import annotations

from mynovel.domain.models import ProviderConfig


def provider_config_from_form(form: dict[str, str]) -> ProviderConfig:
    return ProviderConfig(
        llm_base_url=form.get("llm_base_url", ""),
        llm_api_key=form.get("llm_api_key") or None,
        llm_model=form.get("llm_model", ""),
        embedding_use_llm_credentials=_checked(form, "embedding_use_llm_credentials", True),
        embedding_base_url=form.get("embedding_base_url", ""),
        embedding_api_key=form.get("embedding_api_key") or None,
        embedding_model=form.get("embedding_model", ""),
        rerank_use_llm_credentials=_checked(form, "rerank_use_llm_credentials", True),
        rerank_base_url=form.get("rerank_base_url") or None,
        rerank_api_key=form.get("rerank_api_key") or None,
        rerank_model=form.get("rerank_model") or None,
    )


def _checked(form: dict[str, str], name: str, default: bool = False) -> bool:
    default_value = "1" if default else "0"
    return form.get(name, default_value) == "1"
