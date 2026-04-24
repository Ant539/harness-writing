from app.models.enums import PaperStatus, SectionStatus
from app.state_machine import can_transition_paper, can_transition_section


def test_paper_transition_map_accepts_expected_next_state() -> None:
    assert can_transition_paper(PaperStatus.IDEA, PaperStatus.OUTLINE_READY)


def test_paper_transition_map_rejects_skip() -> None:
    assert not can_transition_paper(PaperStatus.IDEA, PaperStatus.SUBMISSION_READY)


def test_section_transition_map_accepts_expected_next_state() -> None:
    assert can_transition_section(SectionStatus.PLANNED, SectionStatus.CONTRACT_READY)


def test_section_transition_map_rejects_skip() -> None:
    assert not can_transition_section(SectionStatus.PLANNED, SectionStatus.DRAFTED)
