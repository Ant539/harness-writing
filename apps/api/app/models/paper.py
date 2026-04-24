"""Paper model."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from app.models.base import utc_now
from app.models.enums import PaperStatus, PaperType


class Paper(SQLModel, table=True):
    __tablename__ = "papers"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(index=True)
    paper_type: PaperType
    target_language: str = "English"
    target_venue: str | None = None
    status: PaperStatus = Field(default=PaperStatus.IDEA, index=True)
    global_style_guide: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
