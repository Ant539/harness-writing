"""Discovery and planning schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.enums import (
    ArtifactStatus,
    DocumentMaturity,
    DocumentType,
    PlanningMode,
    SectionAction,
    SourceMode,
)
from app.schemas.common import ApiSchema


class DiscoveryBase(ApiSchema):
    document_type: DocumentType = DocumentType.UNKNOWN
    user_goal: str | None = None
    audience: str | None = None
    success_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    available_source_materials: list[str] = Field(default_factory=list)
    current_document_state: str | None = None
    clarifying_questions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryCreate(DiscoveryBase):
    pass


class DiscoveryRead(DiscoveryBase):
    id: uuid.UUID
    paper_id: uuid.UUID
    status: ArtifactStatus
    created_at: datetime
    updated_at: datetime


class TaskProfile(ApiSchema):
    document_type: DocumentType
    audience: str
    success_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class EntryStrategy(ApiSchema):
    source_mode: SourceMode
    current_maturity: DocumentMaturity
    rationale: str


class PaperPlan(ApiSchema):
    objective: str
    global_risks: list[str] = Field(default_factory=list)
    workflow_steps: list[str] = Field(default_factory=list)


class SectionPlan(ApiSchema):
    section_id: uuid.UUID | None = None
    section_title: str
    action: SectionAction
    reason: str
    needs_evidence: bool = True
    needs_review_loop: bool = True


class PromptAssemblyHints(ApiSchema):
    required_prompt_modules: list[str] = Field(default_factory=list)
    style_profile: str
    risk_emphasis: list[str] = Field(default_factory=list)


class PlanningOutput(ApiSchema):
    task_profile: TaskProfile
    entry_strategy: EntryStrategy
    paper_plan: PaperPlan
    section_plans: list[SectionPlan] = Field(default_factory=list)
    prompt_assembly_hints: PromptAssemblyHints


class PlanningRunCreate(ApiSchema):
    discovery_id: uuid.UUID | None = None
    additional_context: str | None = None
    force_deterministic: bool = False


class PlanningRunRead(PlanningOutput):
    id: uuid.UUID
    paper_id: uuid.UUID
    discovery_id: uuid.UUID | None = None
    planner_mode: PlanningMode
    status: ArtifactStatus
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
