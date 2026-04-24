"""Evidence schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.enums import ArtifactStatus, EvidenceSourceType
from app.schemas.common import ApiSchema


class EvidenceItemBase(ApiSchema):
    section_id: uuid.UUID | None = None
    source_type: EvidenceSourceType
    source_ref: str | None = None
    content: str
    citation_key: str | None = None
    confidence: float = Field(default=0.75, ge=0, le=1)
    metadata: dict[str, Any] = {}


class EvidenceItemCreate(EvidenceItemBase):
    paper_id: uuid.UUID


class EvidenceItemForPaperCreate(EvidenceItemBase):
    pass


class EvidenceItemUpdate(ApiSchema):
    section_id: uuid.UUID | None = None
    source_type: EvidenceSourceType | None = None
    source_ref: str | None = None
    content: str | None = None
    citation_key: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    metadata: dict[str, Any] | None = None


class EvidenceItemRead(EvidenceItemBase):
    id: uuid.UUID
    paper_id: uuid.UUID
    created_at: datetime


class SourceMaterialBase(ApiSchema):
    source_type: EvidenceSourceType
    title: str
    source_ref: str | None = None
    content: str
    citation_key: str | None = None
    metadata: dict[str, Any] = {}


class SourceMaterialCreate(SourceMaterialBase):
    pass


class SourceMaterialUpdate(ApiSchema):
    source_type: EvidenceSourceType | None = None
    title: str | None = None
    source_ref: str | None = None
    content: str | None = None
    citation_key: str | None = None
    metadata: dict[str, Any] | None = None


class SourceMaterialRead(SourceMaterialBase):
    id: uuid.UUID
    paper_id: uuid.UUID
    created_at: datetime


class EvidenceExtractionRequest(ApiSchema):
    section_id: uuid.UUID | None = None


class EvidenceExtractionResponse(ApiSchema):
    source: SourceMaterialRead
    items: list[EvidenceItemRead]


class EvidencePackBase(ApiSchema):
    evidence_item_ids: list[uuid.UUID] = []
    coverage_summary: str = ""
    open_questions: list[str] = []
    status: ArtifactStatus = ArtifactStatus.ACTIVE


class EvidencePackCreate(EvidencePackBase):
    section_id: uuid.UUID


class EvidencePackForSectionCreate(EvidencePackBase):
    pass


class EvidencePackUpdate(ApiSchema):
    evidence_item_ids: list[uuid.UUID] | None = None
    coverage_summary: str | None = None
    open_questions: list[str] | None = None
    status: ArtifactStatus | None = None


class EvidencePackRead(EvidencePackBase):
    id: uuid.UUID
    section_id: uuid.UUID
    created_at: datetime


class EvidencePackBuildRequest(ApiSchema):
    candidate_evidence_item_ids: list[uuid.UUID] | None = None
    notes: str | None = None
    force: bool = False


class EvidencePackBuildResponse(ApiSchema):
    section_id: uuid.UUID
    pack: EvidencePackRead
    items: list[EvidenceItemRead]


class EvidencePackMembershipUpdate(ApiSchema):
    evidence_item_id: uuid.UUID
