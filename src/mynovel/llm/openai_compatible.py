import json
from collections.abc import Iterator
from typing import Any

import httpx
from pydantic import BaseModel


class ChatRequest(BaseModel):
    model: str
    messages: list[dict[str, str]]
    temperature: float | None = None
    extra: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model, "messages": self.messages}
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.extra:
            payload.update(self.extra)
        return payload


class EmbeddingRequest(BaseModel):
    model: str
    input: str | list[str]
    extra: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model, "input": self.input}
        if self.extra:
            payload.update(self.extra)
        return payload


class RerankRequest(BaseModel):
    model: str
    query: str
    documents: list[str]
    top_n: int | None = None
    extra: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "query": self.query,
            "documents": self.documents,
        }
        if self.top_n is not None:
            payload["top_n"] = self.top_n
        if self.extra:
            payload.update(self.extra)
        return payload


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def chat(self, request: ChatRequest) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=request.to_payload(),
            )
            response.raise_for_status()
            return response.json()

    def stream_chat_content(self, request: ChatRequest) -> Iterator[str]:
        payload = request.to_payload()
        payload["stream"] = True
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    content = _stream_content_delta(line)
                    if content:
                        yield content

    async def embeddings(self, request: EmbeddingRequest) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=request.to_payload(),
            )
            response.raise_for_status()
            return response.json()

    async def rerank(self, request: RerankRequest) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/rerank",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=request.to_payload(),
            )
            response.raise_for_status()
            return response.json()


def _stream_content_delta(line: str) -> str:
    text = line.strip()
    if not text:
        return ""
    if text.startswith("data:"):
        text = text.removeprefix("data:").strip()
    if text == "[DONE]":
        return ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    delta = first.get("delta")
    if isinstance(delta, dict) and isinstance(delta.get("content"), str):
        return delta["content"]
    message = first.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    return ""
