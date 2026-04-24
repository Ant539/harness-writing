"""Evidence models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from app.models.base import utc_now
from app.models.enums import ArtifactStatus, EvidenceSourceType


class EvidenceItem(SQLModel, table=True):
    __tablename__ = "evidence_items"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    section_id: uuid.UUID | None = Field(default=None, foreign_key="outline_nodes.id", index=True)
    source_type: EvidenceSourceType
    source_ref: str | None = None
    content: str
    citation_key: str | None = None
    confidence: float = 0.75
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class SourceMaterial(SQLModel, table=True):
    __tablename__ = "source_materials"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    source_type: EvidenceSourceType
    title: str
    source_ref: str | None = None
    content: str
    citation_key: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class EvidencePack(SQLModel, table=True):
    __tablename__ = "evidence_packs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    section_id: uuid.UUID = Field(foreign_key="outline_nodes.id", index=True)
    evidence_item_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    coverage_summary: str = ""
    open_questions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: ArtifactStatus = Field(default=ArtifactStatus.ACTIVE, index=True)
    created_at: datetime = Field(default_factory=utc_now)
