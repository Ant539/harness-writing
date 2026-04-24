"""Section contract model."""

import uuid
from datetime import datetime

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from app.models.base import utc_now


class SectionContract(SQLModel, table=True):
    __tablename__ = "section_contracts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    section_id: uuid.UUID = Field(foreign_key="outline_nodes.id", index=True)
    purpose: str
    questions_to_answer: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    required_claims: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    required_evidence_count: int = 1
    required_citations: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    forbidden_patterns: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    tone: str | None = None
    length_min: int | None = None
    length_max: int | None = None
    created_at: datetime = Field(default_factory=utc_now)
