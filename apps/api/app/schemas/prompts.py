"""Prompt assembly schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.enums import ArtifactStatus, PromptStage
from app.schemas.common import ApiSchema


class PromptModuleRead(ApiSchema):
    key: str
    title: str
    content: str
    source: str | None = None


class PromptAssemblyRequest(ApiSchema):
    stage: PromptStage
    planning_run_id: uuid.UUID | None = None
    workflow_run_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    additional_instructions: str | None = None


class PromptAssemblyRead(ApiSchema):
    id: uuid.UUID
    paper_id: uuid.UUID
    planning_run_id: uuid.UUID | None = None
    workflow_run_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    stage: PromptStage
    version: int
    module_keys: list[str] = Field(default_factory=list)
    modules: list[PromptModuleRead] = Field(default_factory=list)
    system_prompt: str
    user_prompt: str
    prompt_hash: str | None = None
    prompt_pack_version: str | None = None
    status: ArtifactStatus
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class PromptExecutionLogRead(ApiSchema):
    id: uuid.UUID
    paper_id: uuid.UUID
    planning_run_id: uuid.UUID | None = None
    workflow_run_id: uuid.UUID | None = None
    prompt_assembly_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    stage: PromptStage
    provider: str | None = None
    model_name: str | None = None
    status: str
    prompt_hash: str | None = None
    prompt_version: int | None = None
    prompt_pack_version: str | None = None
    module_keys: list[str] = Field(default_factory=list)
    request_metadata: dict[str, Any] = Field(default_factory=dict)
    system_prompt: str | None = None
    user_prompt: str | None = None
    response_text: str | None = None
    error_message: str | None = None
    created_at: datetime
