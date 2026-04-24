"""Outline and section model."""

import uuid
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from app.models.enums import SectionStatus


class OutlineNode(SQLModel, table=True):
    __tablename__ = "outline_nodes"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    parent_id: uuid.UUID | None = Field(default=None, foreign_key="outline_nodes.id", index=True)
    title: str
    level: int = 1
    goal: str | None = None
    expected_claims: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    word_budget: int | None = None
    status: SectionStatus = Field(default=SectionStatus.PLANNED, index=True)
    order_index: int = 0
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
