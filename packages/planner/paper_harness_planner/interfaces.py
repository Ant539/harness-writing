"""Planner interface placeholders."""

from typing import Protocol

from paper_harness_core.interfaces import InterfaceRequest, InterfaceResult


class Planner(Protocol):
    """Boundary for future outline and contract planning."""

    def plan(self, request: InterfaceRequest) -> InterfaceResult:
        """Plan from a typed request."""
