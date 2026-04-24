"""Section contract schemas."""

import uuid
from datetime import datetime

from app.schemas.common import ApiSchema
from app.schemas.outlines import OutlineNodeRead


class SectionContractBase(ApiSchema):
    purpose: str
    questions_to_answer: list[str] = []
    required_claims: list[str] = []
    required_evidence_count: int = 1
    required_citations: list[str] = []
    forbidden_patterns: list[str] = []
    tone: str | None = None
    length_min: int | None = None
    length_max: int | None = None


class SectionContractCreate(SectionContractBase):
    section_id: uuid.UUID


class SectionContractForSectionCreate(SectionContractBase):
    pass


class SectionContractUpdate(ApiSchema):
    purpose: str | None = None
    questions_to_answer: list[str] | None = None
    required_claims: list[str] | None = None
    required_evidence_count: int | None = None
    required_citations: list[str] | None = None
    forbidden_patterns: list[str] | None = None
    tone: str | None = None
    length_min: int | None = None
    length_max: int | None = None


class SectionContractRead(SectionContractBase):
    id: uuid.UUID
    section_id: uuid.UUID
    created_at: datetime


class ContractGenerationRequest(ApiSchema):
    additional_constraints: str | None = None
    force: bool = False


class ContractGenerationResponse(ApiSchema):
    section: OutlineNodeRead
    contract: SectionContractRead
