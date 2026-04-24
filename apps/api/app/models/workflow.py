"""Workflow run persistence models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from app.models.base import utc_now
from app.models.enums import WorkflowRunStatus, WorkflowStepKind, WorkflowStepStatus


class WorkflowRun(SQLModel, table=True):
    __tablename__ = "workflow_runs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    discovery_id: uuid.UUID | None = Field(default=None, foreign_key="discovery_records.id", index=True)
    planning_run_id: uuid.UUID | None = Field(default=None, foreign_key="planning_runs.id", index=True)
    status: WorkflowRunStatus = Field(default=WorkflowRunStatus.PENDING, index=True)
    dry_run: bool = False
    auto_execute: bool = True
    requested_section_limit: int | None = None
    current_step_key: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class WorkflowStepRun(SQLModel, table=True):
    __tablename__ = "workflow_step_runs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workflow_run_id: uuid.UUID = Field(foreign_key="workflow_runs.id", index=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    discovery_id: uuid.UUID | None = Field(default=None, foreign_key="discovery_records.id", index=True)
    planning_run_id: uuid.UUID | None = Field(default=None, foreign_key="planning_runs.id", index=True)
    section_id: uuid.UUID | None = Field(default=None, foreign_key="outline_nodes.id", index=True)
    sequence_index: int = Field(index=True)
    step_key: str = Field(index=True)
    step_type: WorkflowStepKind = Field(index=True)
    title: str
    status: WorkflowStepStatus = Field(default=WorkflowStepStatus.PENDING, index=True)
    result_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
