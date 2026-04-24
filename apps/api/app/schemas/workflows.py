"""Workflow runner schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.enums import WorkflowRunStatus, WorkflowStepKind, WorkflowStepStatus
from app.schemas.common import ApiSchema
from app.schemas.outlines import OutlineGenerationRequest
from app.schemas.planning import DiscoveryCreate, DiscoveryRead, PlanningRunCreate, PlanningRunRead


class WorkflowRunStartRequest(ApiSchema):
    discovery: DiscoveryCreate | None = None
    planning: PlanningRunCreate = Field(default_factory=PlanningRunCreate)
    outline: OutlineGenerationRequest = Field(default_factory=OutlineGenerationRequest)
    auto_execute: bool = True
    dry_run: bool = False
    section_limit: int | None = None


class WorkflowStepRunRead(ApiSchema):
    id: uuid.UUID
    workflow_run_id: uuid.UUID
    paper_id: uuid.UUID
    discovery_id: uuid.UUID | None = None
    planning_run_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    sequence_index: int
    step_key: str
    step_type: WorkflowStepKind
    title: str
    status: WorkflowStepStatus
    result: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WorkflowRunRead(ApiSchema):
    id: uuid.UUID
    paper_id: uuid.UUID
    discovery_id: uuid.UUID | None = None
    planning_run_id: uuid.UUID | None = None
    status: WorkflowRunStatus
    dry_run: bool
    auto_execute: bool
    requested_section_limit: int | None = None
    current_step_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class WorkflowRunDetailRead(WorkflowRunRead):
    steps: list[WorkflowStepRunRead] = Field(default_factory=list)


class WorkflowRunStartResponse(ApiSchema):
    workflow_run: WorkflowRunDetailRead
    discovery: DiscoveryRead | None = None
    plan: PlanningRunRead | None = None
