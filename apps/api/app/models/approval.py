"""Section approval and locking artifacts."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from app.models.base import utc_now
from app.models.enums import SectionApprovalStatus


class SectionApproval(SQLModel, table=True):
    __tablename__ = "section_approvals"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    section_id: uuid.UUID = Field(foreign_key="outline_nodes.id", index=True)
    draft_id: uuid.UUID | None = Field(default=None, foreign_key="draft_units.id", index=True)
    workflow_checkpoint_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="workflow_checkpoints.id",
        index=True,
    )
    status: SectionApprovalStatus = Field(default=SectionApprovalStatus.PENDING, index=True)
    requested_by: str | None = None
    decided_by: str | None = None
    note: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
