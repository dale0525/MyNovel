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
