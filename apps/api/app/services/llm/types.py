"""Provider-neutral LLM request and response types."""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class LLMMessage:
    role: Role
    content: str


@dataclass(frozen=True)
class LLMRequest:
    messages: list[LLMMessage]
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    expect_json: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResult:
    content: str
    provider: str
    model: str
    raw: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    provider_name: str

    def generate(self, request: LLMRequest) -> LLMResult:
        """Generate a model response."""
