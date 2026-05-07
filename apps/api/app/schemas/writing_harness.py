"""Generic Writing Harness artifact and workflow schemas."""

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import Field

from app.models.enums import ExportFormat
from app.schemas.common import ApiSchema


class WritingTaskType(StrEnum):
    QUICK_REWRITE = "quick_rewrite"
    SIMPLE_DRAFT = "simple_draft"
    STRUCTURED_WRITING = "structured_writing"
    RESEARCH_WRITING = "research_writing"
    ACADEMIC_PAPER = "academic_paper"
    LONG_FORM_PROJECT = "long_form_project"


class WritingWorkflowState(StrEnum):
    NEW_TASK = "new_task"
    ROUTED = "routed"
    BRIEFING = "briefing"
    BRIEF_READY = "brief_ready"
    PLANNING = "planning"
    OUTLINE_READY = "outline_ready"
    DRAFTING = "drafting"
    DRAFT_READY = "draft_ready"
    REVIEWING = "reviewing"
    REVIEW_READY = "review_ready"
    REVISION_PLANNED = "revision_planned"
    REVISING = "revising"
    FINAL_READY = "final_ready"
    ACADEMIC_BRIEFING = "academic_briefing"
    RESEARCH_QUESTION_READY = "research_question_ready"
    CLAIM_MAP_READY = "claim_map_ready"
    LITERATURE_PLAN_READY = "literature_plan_ready"
    SOURCE_NOTES_READY = "source_notes_ready"
    PAPER_OUTLINE_READY = "paper_outline_ready"
    SECTION_DRAFTING = "section_drafting"
    PAPER_DRAFT_READY = "paper_draft_ready"
    CITATION_CHECKING = "citation_checking"
    CLAIM_EVIDENCE_CHECKING = "claim_evidence_checking"
    ACADEMIC_REVIEWING = "academic_reviewing"
    FINAL_PAPER_READY = "final_paper_ready"


class ReviewIssue(ApiSchema):
    issue_id: str
    dimension: str
    severity: str
    location: str
    problem: str
    why_it_matters: str
    suggested_fix: str
    blocking: bool = False


class WritingBrief(ApiSchema):
    topic: str
    goal: str
    audience: str
    deliverable_type: str
    language: str
    tone: str
    length: str
    stance: str | None = None
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    research_required: bool = False
    citation_required: bool = False
    approval_points: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class AcademicBrief(WritingBrief):
    research_area: str | None = None
    research_question: str | None = None
    thesis_or_main_claim: str | None = None
    target_venue: str | None = None
    paper_type: str = "position paper"
    expected_contribution: str | None = None
    methodology: str | None = None
    datasets: list[str] = Field(default_factory=list)
    experiments: list[str] = Field(default_factory=list)
    related_work_scope: list[str] = Field(default_factory=list)
    citation_style: str = "unspecified"
    novelty_claims: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    ethical_considerations: list[str] = Field(default_factory=list)


class OutlineSection(ApiSchema):
    title: str
    section_goal: str
    key_points: list[str] = Field(default_factory=list)
    required_sources: list[str] = Field(default_factory=list)
    expected_claims: list[str] = Field(default_factory=list)
    status: str = "planned"


class Outline(ApiSchema):
    outline_id: str = "outline-v1"
    sections: list[OutlineSection] = Field(default_factory=list)


class SourceNote(ApiSchema):
    source_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    url_or_doi: str | None = None
    key_points: list[str] = Field(default_factory=list)
    usable_for: list[str] = Field(default_factory=list)
    related_claims: list[str] = Field(default_factory=list)
    reliability: str = "unverified"
    limitations: list[str] = Field(default_factory=list)
    quoted_text: str | None = None
    summary: str | None = None
    citation_metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimEvidenceItem(ApiSchema):
    claim_id: str
    claim_text: str
    claim_type: str
    supporting_sources: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    unsupported_risk: str = "medium"
    required_validation: list[str] = Field(default_factory=list)
    appears_in_sections: list[str] = Field(default_factory=list)
    confidence: float = 0.5


class ClaimEvidenceMap(ApiSchema):
    claims: list[ClaimEvidenceItem] = Field(default_factory=list)


class Draft(ApiSchema):
    version: int = 1
    content: str
    sections: dict[str, str] = Field(default_factory=dict)
    citations_used: list[str] = Field(default_factory=list)
    known_issues: list[str] = Field(default_factory=list)
    created_from_outline_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewReport(ApiSchema):
    overall_score: float
    blocking_issues: list[ReviewIssue] = Field(default_factory=list)
    major_issues: list[ReviewIssue] = Field(default_factory=list)
    minor_issues: list[ReviewIssue] = Field(default_factory=list)
    rubric_scores: dict[str, float] = Field(default_factory=dict)
    factuality_risks: list[str] = Field(default_factory=list)
    citation_risks: list[str] = Field(default_factory=list)
    structure_risks: list[str] = Field(default_factory=list)
    style_risks: list[str] = Field(default_factory=list)
    ready_for_revision: bool = True
    ready_for_final: bool = False


class RevisionPlan(ApiSchema):
    from_version: int
    to_version: int
    must_fix: list[str] = Field(default_factory=list)
    should_fix: list[str] = Field(default_factory=list)
    optional_fix: list[str] = Field(default_factory=list)
    do_not_change: list[str] = Field(default_factory=list)
    rationale: str


class ChangeLog(ApiSchema):
    version_from: int
    version_to: int
    changed_sections: list[str] = Field(default_factory=list)
    summary: str
    reason: str
    linked_review_items: list[str] = Field(default_factory=list)


class WritingStateSnapshot(ApiSchema):
    state: WritingWorkflowState
    artifact_keys: list[str] = Field(default_factory=list)
    version: int = 1
    can_continue: bool = True
    needs_user_confirmation: bool = False
    blocking_issues: list[str] = Field(default_factory=list)
    rollback_to: WritingWorkflowState | None = None
    regeneratable_stages: list[WritingWorkflowState] = Field(default_factory=list)


class PaperHarnessPipelineOptions(ApiSchema):
    generate_contracts: bool = False
    extract_evidence: bool = False
    build_evidence_packs: bool = False
    generate_section_drafts: bool = False
    assemble_manuscript: bool = False
    export_formats: list[ExportFormat] = Field(default_factory=list)
    force_rebuild: bool = False


class WritingArtifacts(ApiSchema):
    writing_brief: WritingBrief | None = None
    academic_brief: AcademicBrief | None = None
    outline: Outline | None = None
    source_notes: list[SourceNote] = Field(default_factory=list)
    claim_evidence_map: ClaimEvidenceMap | None = None
    draft: Draft | None = None
    review_report: ReviewReport | None = None
    revision_plan: RevisionPlan | None = None
    changelog: ChangeLog | None = None
    final_output: str | None = None
    warnings: list[str] = Field(default_factory=list)


class WritingHarnessRunRequest(ApiSchema):
    user_input: str
    source_text: str | None = None
    language: str | None = None
    tone: str | None = None
    audience: str | None = None
    length: str | None = None
    target_venue: str | None = None
    requested_task_type: WritingTaskType | None = None
    persist_to_paper_harness: bool = False
    paper_id: uuid.UUID | None = None
    paper_harness_pipeline: PaperHarnessPipelineOptions = Field(
        default_factory=PaperHarnessPipelineOptions
    )
    max_revision_loops: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskRoute(ApiSchema):
    task_type: WritingTaskType
    complexity_score: int
    rationale: str
    signals: list[str] = Field(default_factory=list)
    requires_research: bool = False
    requires_citations: bool = False
    requires_review_loop: bool = False


class WritingHarnessRunRead(ApiSchema):
    id: uuid.UUID
    task_type: WritingTaskType
    state: WritingWorkflowState
    route: TaskRoute
    artifacts: WritingArtifacts
    state_history: list[WritingStateSnapshot] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
