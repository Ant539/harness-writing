"""Agent interface placeholders."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AgentRequest:
    """Generic agent request placeholder."""

    payload: dict[str, Any]


@dataclass(frozen=True)
class AgentResult:
    """Generic agent result placeholder."""

    payload: dict[str, Any]


class Agent(Protocol):
    """Common role-agent protocol."""

    def run(self, request: AgentRequest) -> AgentResult:
        """Run the agent role."""
