"""Revision task schemas."""

import uuid
from datetime import datetime

from app.models.enums import ArtifactStatus, Severity
from app.schemas.common import ApiSchema


class RevisionTaskBase(ApiSchema):
    task_description: str
    priority: Severity = Severity.MEDIUM
    status: ArtifactStatus = ArtifactStatus.ACTIVE


class RevisionTaskCreate(RevisionTaskBase):
    section_id: uuid.UUID
    draft_id: uuid.UUID


class RevisionTaskForSectionCreate(RevisionTaskBase):
    draft_id: uuid.UUID


class RevisionTaskUpdate(ApiSchema):
    task_description: str | None = None
    priority: Severity | None = None
    status: ArtifactStatus | None = None


class RevisionTaskRead(RevisionTaskBase):
    id: uuid.UUID
    section_id: uuid.UUID
    draft_id: uuid.UUID
    created_at: datetime
