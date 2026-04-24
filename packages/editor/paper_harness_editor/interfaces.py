"""Editor interface placeholders."""

from typing import Protocol

from paper_harness_core.interfaces import InterfaceRequest, InterfaceResult


class Editor(Protocol):
    """Boundary for future manuscript editing."""

    def edit(self, request: InterfaceRequest) -> InterfaceResult:
        """Edit from a typed request."""
