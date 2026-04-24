"""Shared enum placeholders."""

from enum import StrEnum


class PaperType(StrEnum):
    """Supported paper type labels."""

    SURVEY = "survey"
    EMPIRICAL = "empirical"
    CONCEPTUAL = "conceptual"


class PaperStatus(StrEnum):
    """Paper lifecycle labels."""

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
    """Section lifecycle labels."""

    PLANNED = "planned"
    CONTRACT_READY = "contract_ready"
    EVIDENCE_READY = "evidence_ready"
    DRAFTED = "drafted"
    REVIEWED = "reviewed"
    REVISION_REQUIRED = "revision_required"
    REVISED = "revised"
    LOCKED = "locked"


class EvidenceSourceType(StrEnum):
    """Evidence source labels."""

    PAPER_QUOTE = "paper_quote"
    PAPER_SUMMARY = "paper_summary"
    NOTE = "note"
    EXPERIMENT_RESULT = "experiment_result"
    TABLE = "table"
    FIGURE = "figure"
    AUTHOR_CLAIM = "author_claim"


class DraftKind(StrEnum):
    """Draft unit labels."""

    SECTION_DRAFT = "section_draft"
    PARAGRAPH = "paragraph"


class ReviewCommentType(StrEnum):
    """Review comment labels."""

    MISSING_CITATION = "missing_citation"
    LOGIC_GAP = "logic_gap"
    REDUNDANCY = "redundancy"
    STYLE_ISSUE = "style_issue"
    OVERCLAIM = "overclaim"
    HALLUCINATION_RISK = "hallucination_risk"


class Severity(StrEnum):
    """Severity labels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKER = "blocker"


class ArtifactStatus(StrEnum):
    """Generic artifact status labels."""

    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    APPROVED = "approved"
    REJECTED = "rejected"
