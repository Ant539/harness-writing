"""Review interface placeholders."""

from typing import Protocol

from paper_harness_core.interfaces import InterfaceRequest, InterfaceResult


class Reviewer(Protocol):
    """Boundary for future section review."""

    def review(self, request: InterfaceRequest) -> InterfaceResult:
        """Review from a typed request."""
