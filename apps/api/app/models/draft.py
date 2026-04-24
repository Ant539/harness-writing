"""Draft model."""

import uuid
from datetime import datetime

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from app.models.base import utc_now
from app.models.enums import ArtifactStatus, DraftKind


class DraftUnit(SQLModel, table=True):
    __tablename__ = "draft_units"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    section_id: uuid.UUID = Field(foreign_key="outline_nodes.id", index=True)
    kind: DraftKind = Field(default=DraftKind.SECTION_DRAFT, index=True)
    version: int = 1
    content: str
    supported_evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: ArtifactStatus = Field(default=ArtifactStatus.DRAFT, index=True)
    created_at: datetime = Field(default_factory=utc_now)
