"""Shared API schema helpers."""

from pydantic import BaseModel, ConfigDict


class ApiSchema(BaseModel):
    """Base schema with ORM attribute support."""

    model_config = ConfigDict(from_attributes=True)


class ErrorBody(ApiSchema):
    code: str
    message: str
    details: dict = {}


class ErrorResponse(ApiSchema):
    error: ErrorBody
