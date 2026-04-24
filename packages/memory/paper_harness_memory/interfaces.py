"""Memory interface placeholders."""

from typing import Protocol

from paper_harness_core.interfaces import InterfaceRequest, InterfaceResult


class MemoryStore(Protocol):
    """Boundary for future structured memory."""

    def record(self, request: InterfaceRequest) -> InterfaceResult:
        """Record memory from a typed request."""
