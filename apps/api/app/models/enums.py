"""Domain enums used by persisted models and API schemas."""

from enum import StrEnum


class PaperType(StrEnum):
    SURVEY = "survey"
    EMPIRICAL = "empirical"
    CONCEPTUAL = "conceptual"


class PaperStatus(StrEnum):
    IDEA = "idea"
    OUTLINE_READY = "outline_ready"
    EVIDENCE_IN_PROGRESS = "evidence_in_progress"
    DRAFTING_IN_PROGRESS = "drafting_in_progress"
    SECTION_REVIEW_IN_PROGRESS = "section_review_in_progress"
    REVISION_IN_PROGRESS = "revision_in_progress"
    ASSEMBLY_READY = "assembly_ready"
    GLOBAL_REVIEW = "global_review"
    FINAL_REVISION = "final_revision"
    SUBMISSION_READY = "submission_ready"


class SectionStatus(StrEnum):
    PLANNED = "planned"
    CONTRACT_READY = "contract_ready"
    EVIDENCE_READY = "evidence_ready"
    DRAFTED = "drafted"
    REVIEWED = "reviewed"
    REVISION_REQUIRED = "revision_required"
    REVISED = "revised"
    LOCKED = "locked"


class EvidenceSourceType(StrEnum):
    PAPER_QUOTE = "paper_quote"
    PAPER_SUMMARY = "paper_summary"
    NOTE = "note"
    EXPERIMENT_RESULT = "experiment_result"
    TABLE = "table"
    FIGURE = "figure"
    AUTHOR_CLAIM = "author_claim"


class DraftKind(StrEnum):
    SECTION_DRAFT = "section_draft"
    PARAGRAPH = "paragraph"


class ReviewCommentType(StrEnum):
    MISSING_CITATION = "missing_citation"
    LOGIC_GAP = "logic_gap"
    REDUNDANCY = "redundancy"
    STYLE_ISSUE = "style_issue"
    OVERCLAIM = "overclaim"
    HALLUCINATION_RISK = "hallucination_risk"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKER = "blocker"


class ArtifactStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    APPROVED = "approved"
    REJECTED = "rejected"


class ManuscriptIssueType(StrEnum):
    MISSING_SECTION_DRAFT = "missing_section_draft"
    UNRESOLVED_SECTION_REVIEW = "unresolved_section_review"
    TERMINOLOGY_DRIFT = "terminology_drift"
    CONTRIBUTION_ALIGNMENT = "contribution_alignment"
    ABSTRACT_CONCLUSION_MISMATCH = "abstract_conclusion_mismatch"
    MISSING_TRANSITION = "missing_transition"
    MISSING_INTRODUCTION = "missing_introduction"
    MISSING_CONCLUSION = "missing_conclusion"
    SECTION_ORDERING_PROBLEM = "section_ordering_problem"
    STYLE_ISSUE = "style_issue"


class ExportFormat(StrEnum):
    MARKDOWN = "markdown"
    LATEX = "latex"


class DocumentType(StrEnum):
    ACADEMIC_PAPER = "academic_paper"
    REPORT = "report"
    THESIS = "thesis"
    PROPOSAL = "proposal"
    TECHNICAL_DOCUMENT = "technical_document"
    UNKNOWN = "unknown"


class SourceMode(StrEnum):
    NEW_PAPER = "new_paper"
    EXISTING_DRAFT = "existing_draft"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class DocumentMaturity(StrEnum):
    IDEA = "idea"
    OUTLINE = "outline"
    PARTIAL_DRAFT = "partial_draft"
    FULL_DRAFT = "full_draft"
    REVISION_CYCLE = "revision_cycle"


class SectionAction(StrEnum):
    PRESERVE = "preserve"
    POLISH = "polish"
    REWRITE = "rewrite"
    REPAIR = "repair"
    DRAFT = "draft"
    BLOCKED = "blocked"


class PlanningMode(StrEnum):
    DETERMINISTIC = "deterministic"
    MODEL = "model"
    FALLBACK = "fallback"


class WorkflowRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStepKind(StrEnum):
    DISCOVER = "discover"
    PLAN = "plan"
    ASSEMBLE_PROMPTS = "assemble_prompts"
    GENERATE_OUTLINE = "generate_outline"
    REPLAN = "replan"
    GENERATE_CONTRACT = "generate_contract"
    SECTION_ACTION = "section_action"


class PromptStage(StrEnum):
    PLANNER = "planner"
    WRITER = "writer"
    REVIEWER = "reviewer"
    REVISER = "reviser"
    VERIFIER = "verifier"
    EDITOR = "editor"


class UserInteractionRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ClarificationStatus(StrEnum):
    PENDING = "pending"
    ANSWERED = "answered"
    CANCELLED = "cancelled"


class WorkflowCheckpointType(StrEnum):
    CLARIFICATION = "clarification"
    UNKNOWN_PLAN = "unknown_plan"
    BLOCKED_SECTION = "blocked_section"
    APPROVAL_REQUIRED = "approval_required"


class WorkflowCheckpointStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class SectionApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    UNLOCKED = "unlocked"
    SUPERSEDED = "superseded"
