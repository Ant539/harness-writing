"""Persistent user interaction and workflow checkpoint models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from app.models.base import utc_now
from app.models.enums import (
    ClarificationStatus,
    UserInteractionRole,
    WorkflowCheckpointStatus,
    WorkflowCheckpointType,
)


class UserInteraction(SQLModel, table=True):
    __tablename__ = "user_interactions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    workflow_run_id: uuid.UUID | None = Field(default=None, foreign_key="workflow_runs.id", index=True)
    discovery_id: uuid.UUID | None = Field(default=None, foreign_key="discovery_records.id", index=True)
    clarification_request_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="clarification_requests.id",
        index=True,
    )
    role: UserInteractionRole = Field(index=True)
    message: str
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class ClarificationRequest(SQLModel, table=True):
    __tablename__ = "clarification_requests"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    workflow_run_id: uuid.UUID | None = Field(default=None, foreign_key="workflow_runs.id", index=True)
    discovery_id: uuid.UUID | None = Field(default=None, foreign_key="discovery_records.id", index=True)
    question: str
    context: str | None = None
    status: ClarificationStatus = Field(default=ClarificationStatus.PENDING, index=True)
    answer: str | None = None
    response_interaction_id: uuid.UUID | None = Field(default=None, foreign_key="user_interactions.id")
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class WorkflowCheckpoint(SQLModel, table=True):
    __tablename__ = "workflow_checkpoints"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    workflow_run_id: uuid.UUID = Field(foreign_key="workflow_runs.id", index=True)
    planning_run_id: uuid.UUID | None = Field(default=None, foreign_key="planning_runs.id", index=True)
    section_id: uuid.UUID | None = Field(default=None, foreign_key="outline_nodes.id", index=True)
    checkpoint_type: WorkflowCheckpointType = Field(index=True)
    status: WorkflowCheckpointStatus = Field(default=WorkflowCheckpointStatus.PENDING, index=True)
    reason: str
    required_actions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    clarification_request_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
