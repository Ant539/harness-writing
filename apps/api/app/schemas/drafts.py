"""Draft schemas."""

import uuid
from datetime import datetime

from app.models.enums import ArtifactStatus, DraftKind
from app.schemas.common import ApiSchema
from app.schemas.outlines import OutlineNodeRead


class DraftUnitBase(ApiSchema):
    kind: DraftKind = DraftKind.SECTION_DRAFT
    version: int = 1
    content: str
    supported_evidence_ids: list[uuid.UUID] = []
    status: ArtifactStatus = ArtifactStatus.DRAFT


class DraftUnitCreate(DraftUnitBase):
    section_id: uuid.UUID


class DraftUnitForSectionCreate(DraftUnitBase):
    pass


class DraftUnitUpdate(ApiSchema):
    kind: DraftKind | None = None
    version: int | None = None
    content: str | None = None
    supported_evidence_ids: list[uuid.UUID] | None = None
    status: ArtifactStatus | None = None


class DraftUnitRead(DraftUnitBase):
    id: uuid.UUID
    section_id: uuid.UUID
    created_at: datetime


class DraftGenerationRequest(ApiSchema):
    drafting_instructions: str | None = None
    neighboring_section_context: str | None = None


class DraftGenerationResponse(ApiSchema):
    section: OutlineNodeRead
    draft: DraftUnitRead
    unsupported_claim_notes: list[str] = []


class DraftRevisionRequest(ApiSchema):
    revision_instructions: str | None = None
    review_comment_ids: list[uuid.UUID] | None = None
    revision_task_ids: list[uuid.UUID] | None = None
    resolve_comments: bool = True


class DraftRevisionResponse(ApiSchema):
    section: OutlineNodeRead
    previous_draft_id: uuid.UUID
    draft: DraftUnitRead
    resolved_review_comment_ids: list[uuid.UUID] = []
    completed_revision_task_ids: list[uuid.UUID] = []
