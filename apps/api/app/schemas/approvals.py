"""Section approval schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.enums import SectionApprovalStatus
from app.schemas.common import ApiSchema
from app.schemas.outlines import OutlineNodeRead


class SectionApprovalRequest(ApiSchema):
    requested_by: str | None = None
    note: str | None = None
    workflow_checkpoint_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SectionApprovalDecision(ApiSchema):
    decided_by: str | None = None
    note: str | None = None
    workflow_checkpoint_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SectionUnlockRequest(ApiSchema):
    decided_by: str | None = None
    note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SectionApprovalRead(ApiSchema):
    id: uuid.UUID
    paper_id: uuid.UUID
    section_id: uuid.UUID
    draft_id: uuid.UUID | None = None
    workflow_checkpoint_id: uuid.UUID | None = None
    status: SectionApprovalStatus
    requested_by: str | None = None
    decided_by: str | None = None
    note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class SectionApprovalResponse(ApiSchema):
    section: OutlineNodeRead
    approval: SectionApprovalRead
