"""Revision task model."""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import utc_now
from app.models.enums import ArtifactStatus, Severity


class RevisionTask(SQLModel, table=True):
    __tablename__ = "revision_tasks"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    section_id: uuid.UUID = Field(foreign_key="outline_nodes.id", index=True)
    draft_id: uuid.UUID = Field(foreign_key="draft_units.id", index=True)
    task_description: str
    priority: Severity = Severity.MEDIUM
    status: ArtifactStatus = Field(default=ArtifactStatus.ACTIVE, index=True)
    created_at: datetime = Field(default_factory=utc_now)
