"""HTTP-backed LLM providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.services.llm.types import LLMMessage, LLMRequest, LLMResult
from app.services.llm.usage import normalize_usage


class LLMProviderError(RuntimeError):
    """Raised when a configured provider cannot return usable text."""


@dataclass(frozen=True)
class ProviderConfig:
    provider_name: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.2
    timeout_seconds: float = 60.0
    max_tokens: int = 4096
    json_mode: bool = False


class OpenAICompatibleProvider:
    """Provider for OpenAI-compatible chat/completions APIs.

    This covers OpenAI, GLM/Zhipu, DeepSeek, Qwen-compatible endpoints,
    OpenRouter, Ollama, vLLM, LM Studio, and similar gateways.
    """

    provider_name = "openai_compatible"

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.provider_name = config.provider_name

    def generate(self, request: LLMRequest) -> LLMResult:
        base_url = (self.config.base_url or "").rstrip("/")
        if not base_url:
            raise LLMProviderError("OpenAI-compatible provider requires a base URL.")
        model = request.model or self.config.model
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            "temperature": (
                self.config.temperature if request.temperature is None else request.temperature
            ),
            "max_tokens": request.max_tokens or self.config.max_tokens,
        }
        if request.expect_json and self.config.json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        return self._result_from_response(response, model)

    def _result_from_response(self, response: httpx.Response, model: str) -> LLMResult:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(f"{self.provider_name} request failed: {response.text}") from exc
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"{self.provider_name} returned no assistant content.") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMProviderError(f"{self.provider_name} returned empty assistant content.")
        usage = normalize_usage(self.provider_name, payload)
        return LLMResult(
            content=content,
            provider=self.provider_name,
            model=str(payload.get("model") or model),
            raw=payload,
            usage=usage.as_dict(),
            cost_usd=usage.cost_usd,
        )


class AnthropicProvider:
    """Direct Anthropic Messages API provider."""

    provider_name = "anthropic"

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    def generate(self, request: LLMRequest) -> LLMResult:
        if not self.config.api_key:
            raise LLMProviderError("Anthropic provider requires an API key.")
        model = request.model or self.config.model
        system, messages = self._split_system(request.messages)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": (
                self.config.temperature if request.temperature is None else request.temperature
            ),
            "max_tokens": request.max_tokens or self.config.max_tokens,
        }
        if system:
            payload["system"] = system
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
        }
        base_url = (self.config.base_url or "https://api.anthropic.com/v1").rstrip("/")
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.post(f"{base_url}/messages", json=payload, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(f"anthropic request failed: {response.text}") from exc
        data = response.json()
        blocks = data.get("content") or []
        content = "\n".join(
            block.get("text", "") for block in blocks if isinstance(block, dict)
        ).strip()
        if not content:
            raise LLMProviderError("anthropic returned empty assistant content.")
        usage = normalize_usage(self.provider_name, data)
        return LLMResult(
            content=content,
            provider=self.provider_name,
            model=model,
            raw=data,
            usage=usage.as_dict(),
            cost_usd=usage.cost_usd,
        )

    def _split_system(self, messages: list[LLMMessage]) -> tuple[str | None, list[dict[str, str]]]:
        system_parts: list[str] = []
        non_system: list[dict[str, str]] = []
        for message in messages:
            if message.role == "system":
                system_parts.append(message.content)
                continue
            role = "assistant" if message.role == "assistant" else "user"
            non_system.append({"role": role, "content": message.content})
        return ("\n\n".join(system_parts) or None, non_system)


class GeminiProvider:
    """Direct Gemini generateContent provider."""

    provider_name = "gemini"

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    def generate(self, request: LLMRequest) -> LLMResult:
        if not self.config.api_key:
            raise LLMProviderError("Gemini provider requires an API key.")
        model = request.model or self.config.model
        system_parts: list[str] = []
        contents: list[dict[str, Any]] = []
        for message in request.messages:
            if message.role == "system":
                system_parts.append(message.content)
                continue
            role = "model" if message.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": message.content}]})

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": (
                    self.config.temperature if request.temperature is None else request.temperature
                ),
                "maxOutputTokens": request.max_tokens or self.config.max_tokens,
            },
        }
        if system_parts:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}],
            }
        base_url = (
            self.config.base_url or "https://generativelanguage.googleapis.com/v1beta"
        ).rstrip("/")
        url = f"{base_url}/models/{model}:generateContent"
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.post(url, params={"key": self.config.api_key}, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(f"gemini request failed: {response.text}") from exc
        data = response.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("gemini returned no assistant content.") from exc
        content = "\n".join(
            part.get("text", "") for part in parts if isinstance(part, dict)
        ).strip()
        if not content:
            raise LLMProviderError("gemini returned empty assistant content.")
        usage = normalize_usage(self.provider_name, data)
        return LLMResult(
            content=content,
            provider=self.provider_name,
            model=model,
            raw=data,
            usage=usage.as_dict(),
            cost_usd=usage.cost_usd,
        )
