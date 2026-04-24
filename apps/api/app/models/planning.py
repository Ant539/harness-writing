"""Discovery and planning models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from app.models.base import utc_now
from app.models.enums import (
    ArtifactStatus,
    DocumentType,
    PlanningMode,
)


class DiscoveryRecord(SQLModel, table=True):
    __tablename__ = "discovery_records"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    document_type: DocumentType = Field(default=DocumentType.UNKNOWN, index=True)
    user_goal: str | None = None
    audience: str | None = None
    success_criteria: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    constraints: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    available_source_materials: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    current_document_state: str | None = None
    clarifying_questions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    assumptions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    notes: str | None = None
    status: ArtifactStatus = Field(default=ArtifactStatus.ACTIVE, index=True)
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PlanningRun(SQLModel, table=True):
    __tablename__ = "planning_runs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    discovery_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="discovery_records.id",
        index=True,
    )
    planner_mode: PlanningMode = Field(default=PlanningMode.DETERMINISTIC, index=True)
    status: ArtifactStatus = Field(default=ArtifactStatus.ACTIVE, index=True)
    task_profile_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    entry_strategy_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    paper_plan_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    section_plans_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    prompt_assembly_hints_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
