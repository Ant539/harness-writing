"""Explicit lifecycle transition maps."""

from app.models.enums import PaperStatus, SectionStatus


class InvalidStateTransition(ValueError):
    """Raised when a lifecycle transition is not allowed."""


PAPER_TRANSITIONS: dict[PaperStatus, set[PaperStatus]] = {
    PaperStatus.IDEA: {PaperStatus.OUTLINE_READY},
    PaperStatus.OUTLINE_READY: {PaperStatus.EVIDENCE_IN_PROGRESS},
    PaperStatus.EVIDENCE_IN_PROGRESS: {PaperStatus.DRAFTING_IN_PROGRESS},
    PaperStatus.DRAFTING_IN_PROGRESS: {PaperStatus.SECTION_REVIEW_IN_PROGRESS},
    PaperStatus.SECTION_REVIEW_IN_PROGRESS: {
        PaperStatus.REVISION_IN_PROGRESS,
        PaperStatus.ASSEMBLY_READY,
    },
    PaperStatus.REVISION_IN_PROGRESS: {
        PaperStatus.DRAFTING_IN_PROGRESS,
        PaperStatus.SECTION_REVIEW_IN_PROGRESS,
    },
    PaperStatus.ASSEMBLY_READY: {PaperStatus.GLOBAL_REVIEW},
    PaperStatus.GLOBAL_REVIEW: {PaperStatus.FINAL_REVISION, PaperStatus.SUBMISSION_READY},
    PaperStatus.FINAL_REVISION: {PaperStatus.GLOBAL_REVIEW, PaperStatus.SUBMISSION_READY},
    PaperStatus.SUBMISSION_READY: set(),
}


SECTION_TRANSITIONS: dict[SectionStatus, set[SectionStatus]] = {
    SectionStatus.PLANNED: {SectionStatus.CONTRACT_READY},
    SectionStatus.CONTRACT_READY: {SectionStatus.EVIDENCE_READY},
    SectionStatus.EVIDENCE_READY: {SectionStatus.DRAFTED},
    SectionStatus.DRAFTED: {SectionStatus.REVIEWED},
    SectionStatus.REVIEWED: {SectionStatus.REVISION_REQUIRED, SectionStatus.LOCKED},
    SectionStatus.REVISION_REQUIRED: {SectionStatus.REVISED},
    SectionStatus.REVISED: {SectionStatus.REVIEWED, SectionStatus.LOCKED},
    SectionStatus.LOCKED: {SectionStatus.REVIEWED},
}


def can_transition_paper(current: PaperStatus, target: PaperStatus) -> bool:
    return current == target or target in PAPER_TRANSITIONS[current]


def can_transition_section(current: SectionStatus, target: SectionStatus) -> bool:
    return current == target or target in SECTION_TRANSITIONS[current]


def validate_paper_transition(current: PaperStatus, target: PaperStatus) -> None:
    if not can_transition_paper(current, target):
        raise InvalidStateTransition(f"Cannot transition paper from {current} to {target}.")


def validate_section_transition(current: SectionStatus, target: SectionStatus) -> None:
    if not can_transition_section(current, target):
        raise InvalidStateTransition(f"Cannot transition section from {current} to {target}.")
