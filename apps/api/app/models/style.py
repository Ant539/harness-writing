"""Style guide model."""

import uuid
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class StyleGuide(SQLModel, table=True):
    __tablename__ = "style_guides"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    tone: str | None = None
    voice: str | None = None
    citation_style: str | None = None
    terminology_preferences: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))
    forbidden_patterns: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    format_rules: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
