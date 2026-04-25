"""Prompt assembly persistence models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from app.models.base import utc_now
from app.models.enums import ArtifactStatus, PromptStage


class PromptAssemblyArtifact(SQLModel, table=True):
    __tablename__ = "prompt_assembly_artifacts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    planning_run_id: uuid.UUID | None = Field(default=None, foreign_key="planning_runs.id", index=True)
    workflow_run_id: uuid.UUID | None = Field(default=None, foreign_key="workflow_runs.id", index=True)
    section_id: uuid.UUID | None = Field(default=None, foreign_key="outline_nodes.id", index=True)
    stage: PromptStage = Field(index=True)
    version: int = 1
    module_keys: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    modules_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    system_prompt: str
    user_prompt: str
    prompt_hash: str | None = Field(default=None, index=True)
    prompt_pack_version: str | None = None
    status: ArtifactStatus = Field(default=ArtifactStatus.ACTIVE, index=True)
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class PromptExecutionLog(SQLModel, table=True):
    __tablename__ = "prompt_execution_logs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    planning_run_id: uuid.UUID | None = Field(default=None, foreign_key="planning_runs.id", index=True)
    workflow_run_id: uuid.UUID | None = Field(default=None, foreign_key="workflow_runs.id", index=True)
    prompt_assembly_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="prompt_assembly_artifacts.id",
        index=True,
    )
    section_id: uuid.UUID | None = Field(default=None, foreign_key="outline_nodes.id", index=True)
    stage: PromptStage = Field(index=True)
    provider: str | None = Field(default=None, index=True)
    model_name: str | None = None
    status: str = Field(default="completed", index=True)
    prompt_hash: str | None = Field(default=None, index=True)
    prompt_version: int | None = None
    prompt_pack_version: str | None = None
    module_keys: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    request_metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    usage_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None
    cost_usd: float | None = None
    system_prompt: str | None = None
    user_prompt: str | None = None
    response_text: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
