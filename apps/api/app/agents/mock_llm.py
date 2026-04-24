"""Mock LLM boundary placeholder.

No provider integration or generation behavior is implemented here.
"""

from app.agents.base import AgentRequest, AgentResult


class MockLLMAdapter:
    """Placeholder adapter for future deterministic tests."""

    def run(self, request: AgentRequest) -> AgentResult:
        raise NotImplementedError("Mock LLM behavior is not implemented in the skeleton.")
