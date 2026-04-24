"""Export interface placeholders."""

from typing import Protocol

from paper_harness_core.interfaces import InterfaceRequest, InterfaceResult


class Exporter(Protocol):
    """Boundary for future manuscript export."""

    def export(self, request: InterfaceRequest) -> InterfaceResult:
        """Export from a typed request."""
