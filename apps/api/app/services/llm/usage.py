"""Provider-neutral usage normalization for model responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LLMUsage:
    """Normalized token and provider-cost metadata."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None
    cost_usd: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cached_tokens": self.cached_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cost_usd": self.cost_usd,
            "provider_usage": self.raw or None,
        }
        return {key: value for key, value in data.items() if value is not None}


def normalize_usage(provider: str, payload: dict[str, Any]) -> LLMUsage:
    """Extract usage fields from common provider response shapes."""

    provider_key = provider.lower()
    if provider_key == "anthropic":
        return _anthropic_usage(payload)
    if provider_key == "gemini":
        return _gemini_usage(payload)
    return _openai_compatible_usage(payload)


def _openai_compatible_usage(payload: dict[str, Any]) -> LLMUsage:
    usage = _dict(payload.get("usage"))
    prompt_details = _dict(usage.get("prompt_tokens_details"))
    completion_details = _dict(usage.get("completion_tokens_details"))
    return LLMUsage(
        prompt_tokens=_int(usage.get("prompt_tokens") or usage.get("input_tokens")),
        completion_tokens=_int(usage.get("completion_tokens") or usage.get("output_tokens")),
        total_tokens=_int(usage.get("total_tokens")),
        cached_tokens=_int(prompt_details.get("cached_tokens") or usage.get("cached_tokens")),
        reasoning_tokens=_int(
            completion_details.get("reasoning_tokens") or usage.get("reasoning_tokens")
        ),
        cost_usd=_cost_usd(usage, payload),
        raw=usage,
    )


def _anthropic_usage(payload: dict[str, Any]) -> LLMUsage:
    usage = _dict(payload.get("usage"))
    input_tokens = _int(usage.get("input_tokens"))
    output_tokens = _int(usage.get("output_tokens"))
    cache_creation = _int(usage.get("cache_creation_input_tokens"))
    cache_read = _int(usage.get("cache_read_input_tokens"))
    prompt_parts = [value for value in [input_tokens, cache_creation, cache_read] if value is not None]
    prompt_tokens = sum(prompt_parts) if prompt_parts else None
    total_tokens = None
    if prompt_tokens is not None or output_tokens is not None:
        total_tokens = (prompt_tokens or 0) + (output_tokens or 0)
    return LLMUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=output_tokens,
        total_tokens=_int(usage.get("total_tokens")) or total_tokens,
        cached_tokens=cache_read,
        cost_usd=_cost_usd(usage, payload),
        raw=usage,
    )


def _gemini_usage(payload: dict[str, Any]) -> LLMUsage:
    usage = _dict(payload.get("usageMetadata"))
    return LLMUsage(
        prompt_tokens=_int(usage.get("promptTokenCount")),
        completion_tokens=_int(usage.get("candidatesTokenCount")),
        total_tokens=_int(usage.get("totalTokenCount")),
        cached_tokens=_int(usage.get("cachedContentTokenCount")),
        cost_usd=_cost_usd(usage, payload),
        raw=usage,
    )


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _cost_usd(*containers: dict[str, Any]) -> float | None:
    explicit_keys = (
        "cost_usd",
        "total_cost_usd",
        "request_cost_usd",
        "estimated_cost_usd",
    )
    for container in containers:
        for key in explicit_keys:
            value = _float(container.get(key))
            if value is not None:
                return value
    return None
