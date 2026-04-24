"""Drafting interface placeholders."""

from typing import Protocol

from paper_harness_core.interfaces import InterfaceRequest, InterfaceResult


class Drafter(Protocol):
    """Boundary for future section drafting."""

    def draft(self, request: InterfaceRequest) -> InterfaceResult:
        """Draft from a typed request."""
