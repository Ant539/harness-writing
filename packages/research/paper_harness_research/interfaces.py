"""Research interface placeholders."""

from typing import Protocol

from paper_harness_core.interfaces import InterfaceRequest, InterfaceResult


class Researcher(Protocol):
    """Boundary for future evidence processing."""

    def research(self, request: InterfaceRequest) -> InterfaceResult:
        """Process research input."""
