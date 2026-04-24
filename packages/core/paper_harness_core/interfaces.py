"""Shared interface placeholders."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InterfaceRequest:
    """Generic request boundary."""

    payload: dict[str, Any]


@dataclass(frozen=True)
class InterfaceResult:
    """Generic result boundary."""

    payload: dict[str, Any]
