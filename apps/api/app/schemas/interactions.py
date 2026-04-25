"""User interaction, clarification, and checkpoint schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.enums import (
    ClarificationStatus,
    UserInteractionRole,
    WorkflowCheckpointStatus,
    WorkflowCheckpointType,
)
from app.schemas.common import ApiSchema


class UserInteractionCreate(ApiSchema):
    workflow_run_id: uuid.UUID | None = None
    discovery_id: uuid.UUID | None = None
    clarification_request_id: uuid.UUID | None = None
    role: UserInteractionRole = UserInteractionRole.USER
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class UserInteractionRead(ApiSchema):
    id: uuid.UUID
    paper_id: uuid.UUID
    workflow_run_id: uuid.UUID | None = None
    discovery_id: uuid.UUID | None = None
    clarification_request_id: uuid.UUID | None = None
    role: UserInteractionRole
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ClarificationRequestCreate(ApiSchema):
    workflow_run_id: uuid.UUID | None = None
    discovery_id: uuid.UUID | None = None
    question: str
    context: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryClarificationRequest(ApiSchema):
    workflow_run_id: uuid.UUID | None = None
    questions: list[str] | None = None
    context: str | None = None


class ClarificationAnswer(ApiSchema):
    answer: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClarificationRequestRead(ApiSchema):
    id: uuid.UUID
    paper_id: uuid.UUID
    workflow_run_id: uuid.UUID | None = None
    discovery_id: uuid.UUID | None = None
    question: str
    context: str | None = None
    status: ClarificationStatus
    answer: str | None = None
    response_interaction_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class WorkflowCheckpointCreate(ApiSchema):
    workflow_run_id: uuid.UUID
    planning_run_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    checkpoint_type: WorkflowCheckpointType
    reason: str
    required_actions: list[str] = Field(default_factory=list)
    clarification_request_ids: list[uuid.UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowCheckpointResolve(ApiSchema):
    resolution_note: str | None = None


class WorkflowCheckpointRead(ApiSchema):
    id: uuid.UUID
    paper_id: uuid.UUID
    workflow_run_id: uuid.UUID
    planning_run_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    checkpoint_type: WorkflowCheckpointType
    status: WorkflowCheckpointStatus
    reason: str
    required_actions: list[str] = Field(default_factory=list)
    clarification_request_ids: list[uuid.UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
