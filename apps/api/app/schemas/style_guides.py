"""Style guide schemas."""

import uuid
from typing import Any

from app.schemas.common import ApiSchema


class StyleGuideBase(ApiSchema):
    tone: str | None = None
    voice: str | None = None
    citation_style: str | None = None
    terminology_preferences: dict[str, str] = {}
    forbidden_patterns: list[str] = []
    format_rules: dict[str, Any] = {}


class StyleGuideCreate(StyleGuideBase):
    paper_id: uuid.UUID


class StyleGuideForPaperCreate(StyleGuideBase):
    pass


class StyleGuideUpdate(ApiSchema):
    tone: str | None = None
    voice: str | None = None
    citation_style: str | None = None
    terminology_preferences: dict[str, str] | None = None
    forbidden_patterns: list[str] | None = None
    format_rules: dict[str, Any] | None = None


class StyleGuideRead(StyleGuideBase):
    id: uuid.UUID
    paper_id: uuid.UUID
