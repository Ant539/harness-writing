"""Paper schemas."""

import uuid
from datetime import datetime
from typing import Any

from app.models.enums import PaperStatus, PaperType
from app.schemas.common import ApiSchema


class PaperBase(ApiSchema):
    title: str
    paper_type: PaperType
    target_language: str = "English"
    target_venue: str | None = None
    global_style_guide: dict[str, Any] = {}


class PaperCreate(PaperBase):
    user_goals: str | None = None


class PaperUpdate(ApiSchema):
    title: str | None = None
    paper_type: PaperType | None = None
    target_language: str | None = None
    target_venue: str | None = None
    status: PaperStatus | None = None
    global_style_guide: dict[str, Any] | None = None


class PaperRead(PaperBase):
    id: uuid.UUID
    status: PaperStatus
    created_at: datetime
    updated_at: datetime


class PaperTransition(ApiSchema):
    status: PaperStatus
