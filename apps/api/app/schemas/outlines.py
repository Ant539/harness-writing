"""Outline node schemas."""

import uuid

from app.models.enums import SectionStatus
from app.schemas.common import ApiSchema
from app.schemas.papers import PaperRead


class OutlineNodeBase(ApiSchema):
    parent_id: uuid.UUID | None = None
    title: str
    level: int = 1
    goal: str | None = None
    expected_claims: list[str] = []
    word_budget: int | None = None
    order_index: int = 0


class OutlineNodeCreate(OutlineNodeBase):
    paper_id: uuid.UUID


class PaperOutlineNodeCreate(OutlineNodeBase):
    pass


class OutlineNodeUpdate(ApiSchema):
    parent_id: uuid.UUID | None = None
    title: str | None = None
    level: int | None = None
    goal: str | None = None
    expected_claims: list[str] | None = None
    word_budget: int | None = None
    order_index: int | None = None
    status: SectionStatus | None = None


class OutlineNodeRead(OutlineNodeBase):
    id: uuid.UUID
    paper_id: uuid.UUID
    status: SectionStatus


class OutlineRead(ApiSchema):
    paper_id: uuid.UUID
    nodes: list[OutlineNodeRead]


class OutlineGenerationRequest(ApiSchema):
    additional_context: str | None = None
    target_word_count: int | None = None


class OutlineGenerationResponse(ApiSchema):
    paper: PaperRead
    outline: list[OutlineNodeRead]


class SectionTransition(ApiSchema):
    status: SectionStatus
