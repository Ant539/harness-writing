"""Generic writing harness run persistence."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from app.models.base import utc_now
from app.schemas.writing_harness import WritingTaskType, WritingWorkflowState


class WritingHarnessRun(SQLModel, table=True):
    __tablename__ = "writing_harness_runs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_type: WritingTaskType = Field(index=True)
    state: WritingWorkflowState = Field(index=True)
    user_input: str
    route_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    artifacts_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    state_history_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
