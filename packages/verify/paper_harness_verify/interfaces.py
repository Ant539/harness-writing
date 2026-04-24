"""Verification interface placeholders."""

from typing import Protocol

from paper_harness_core.interfaces import InterfaceRequest, InterfaceResult


class Verifier(Protocol):
    """Boundary for future claim and citation verification."""

    def verify(self, request: InterfaceRequest) -> InterfaceResult:
        """Verify from a typed request."""
