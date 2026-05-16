from __future__ import annotations

import asyncio
from typing import Any, Protocol

from mynovel.api_serializers import is_embedding_config_validated
from mynovel.domain.models import ProviderConfig, ProviderConfigValidation
from mynovel.llm.openai_compatible import EmbeddingRequest, OpenAICompatibleClient


class TextEmbeddingClient(Protocol):
    model: str

    def embed_text(self, text: str) -> list[float]: ...


class OpenAITextEmbeddingClient:
    def __init__(self, client: OpenAICompatibleClient, model: str) -> None:
        self.client = client
        self.model = model

    def embed_text(self, text: str) -> list[float]:
        response = asyncio.run(
            self.client.embeddings(EmbeddingRequest(model=self.model, input=text))
        )
        return parse_embedding_response(response)


def parse_embedding_response(response: dict[str, Any]) -> list[float]:
    data = response.get("data")
    if not isinstance(data, list) or not data:
        raise ValueError("Embedding response has no usable vector.")

    first_item = data[0]
    if not isinstance(first_item, dict):
        raise ValueError("Embedding response has no usable vector.")

    embedding = first_item.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise ValueError("Embedding response has no usable vector.")

    vector: list[float] = []
    for value in embedding:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("Embedding response has no usable vector.")
        vector.append(float(value))
    return vector


def embedding_client_from_provider_config(
    config: ProviderConfig | None,
    validation: ProviderConfigValidation | None,
) -> TextEmbeddingClient | None:
    if not is_embedding_config_validated(config, validation):
        return None
    assert config is not None
    return OpenAITextEmbeddingClient(
        OpenAICompatibleClient(
            base_url=config.resolved_embedding_base_url().strip(),
            api_key=(config.resolved_embedding_api_key() or "").strip(),
        ),
        config.embedding_model.strip(),
    )
