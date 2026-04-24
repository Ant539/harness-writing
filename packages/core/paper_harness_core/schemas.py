"""Shared schema placeholders."""

from pydantic import BaseModel, ConfigDict


class CoreSchema(BaseModel):
    """Base schema for future shared models."""

    model_config = ConfigDict(from_attributes=True)
