"""Deterministic section evidence pack builder for Milestone 3.

TODO(real-llm): replace keyword scoring with retrieval/ranking while preserving
the evidence_ready guard and active EvidencePack contract.
"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import EvidenceItem, EvidencePack, OutlineNode, SectionContract
from app.models.enums import ArtifactStatus, SectionStatus
from app.schemas.evidence import EvidencePackBuildRequest
from app.state_machine import InvalidStateTransition, validate_section_transition


class EvidencePackBuilder:
    """Selects a stable subset of evidence for a section contract."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def build(self, section: OutlineNode, request: EvidencePackBuildRequest) -> EvidencePack:
        contract = self.session.exec(
            select(SectionContract).where(SectionContract.section_id == section.id)
        ).first()
        if contract is None:
            raise HTTPException(
                status_code=400,
                detail="Section must have a contract before building an evidence pack.",
            )
        selected = self._select_evidence(section, contract, request)
        if not selected:
            raise HTTPException(
                status_code=400,
                detail="No evidence items are available for this section.",
            )

        existing = self.session.exec(
            select(EvidencePack).where(EvidencePack.section_id == section.id)
        ).first()
        if existing is not None and not request.force:
            raise HTTPException(
                status_code=409,
                detail="Evidence pack already exists. Use force=true to rebuild it.",
            )
        if existing is None and section.status != SectionStatus.CONTRACT_READY:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot build an evidence pack for section status {section.status}.",
            )
        if existing is not None and section.status not in {
            SectionStatus.CONTRACT_READY,
            SectionStatus.EVIDENCE_READY,
        }:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot rebuild an evidence pack for section status {section.status}.",
            )

        evidence_ids = [str(item.id) for item in selected]
        coverage_summary = self._coverage_summary(section, contract, selected, request)
        open_questions = self._open_questions(contract, selected)

        if existing is not None:
            existing.evidence_item_ids = evidence_ids
            existing.coverage_summary = coverage_summary
            existing.open_questions = open_questions
            existing.status = ArtifactStatus.ACTIVE
            pack = existing
        else:
            pack = EvidencePack(
                section_id=section.id,
                evidence_item_ids=evidence_ids,
                coverage_summary=coverage_summary,
                open_questions=open_questions,
                status=ArtifactStatus.ACTIVE,
            )

        if section.status == SectionStatus.CONTRACT_READY:
            try:
                validate_section_transition(section.status, SectionStatus.EVIDENCE_READY)
            except InvalidStateTransition as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        section.status = SectionStatus.EVIDENCE_READY
        self.session.add(pack)
        self.session.add(section)
        self.session.commit()
        self.session.refresh(pack)
        self.session.refresh(section)
        return pack

    def _select_evidence(
        self,
        section: OutlineNode,
        contract: SectionContract,
        request: EvidencePackBuildRequest,
    ) -> list[EvidenceItem]:
        if request.candidate_evidence_item_ids:
            candidates = []
            for item_id in request.candidate_evidence_item_ids:
                item = self.session.get(EvidenceItem, item_id)
                if item is None:
                    raise HTTPException(status_code=404, detail=f"Evidence item {item_id} not found.")
                if item.paper_id != section.paper_id:
                    raise HTTPException(
                        status_code=400,
                        detail="Evidence items must belong to the same paper as the section.",
                    )
                candidates.append(item)
        else:
            candidates = list(
                self.session.exec(
                    select(EvidenceItem)
                    .where(EvidenceItem.paper_id == section.paper_id)
                    .order_by(EvidenceItem.created_at)
                ).all()
            )

        ranked = sorted(
            candidates,
            key=lambda item: (
                0 if item.section_id == section.id else 1,
                -self._score(item, section, contract),
                item.created_at.isoformat(),
                str(item.id),
            ),
        )
        required = max(contract.required_evidence_count, 1)
        return ranked[: max(required, min(len(ranked), 3))]

    def _score(self, item: EvidenceItem, section: OutlineNode, contract: SectionContract) -> int:
        haystack = " ".join(
            [
                item.content,
                item.source_ref or "",
                item.citation_key or "",
            ]
        ).lower()
        terms = [section.title, section.goal or "", *contract.required_claims]
        score = 0
        for term in terms:
            for token in self._tokens(term):
                if token in haystack:
                    score += 1
        return score

    def _coverage_summary(
        self,
        section: OutlineNode,
        contract: SectionContract,
        selected: list[EvidenceItem],
        request: EvidencePackBuildRequest,
    ) -> str:
        note = f" Notes: {request.notes}" if request.notes else ""
        return (
            f"Selected {len(selected)} evidence item(s) for {section.title}. "
            f"Required claims covered: {len(contract.required_claims)} planned claim(s).{note}"
        )

    def _open_questions(
        self,
        contract: SectionContract,
        selected: list[EvidenceItem],
    ) -> list[str]:
        if len(selected) >= contract.required_evidence_count:
            return []
        return [
            f"Needs {contract.required_evidence_count - len(selected)} more evidence item(s) "
            "to meet the section contract."
        ]

    def _tokens(self, text: str) -> set[str]:
        return {token for token in text.lower().replace("-", " ").split() if len(token) > 3}


def evidence_ids_from_pack(pack: EvidencePack) -> list[uuid.UUID]:
    return [uuid.UUID(value) for value in pack.evidence_item_ids]
