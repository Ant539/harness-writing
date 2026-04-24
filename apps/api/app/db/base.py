"""Model metadata import point."""

from sqlmodel import SQLModel

from app import models  # noqa: F401

__all__ = ["SQLModel"]
