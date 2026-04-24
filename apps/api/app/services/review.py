"""Section draft review orchestration."""

import uuid

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    DraftUnit,
    EvidenceItem,
    EvidencePack,
    OutlineNode,
    ReviewComment,
    RevisionTask,
    SectionContract,
)
from app.models.enums import ArtifactStatus, DraftKind, SectionStatus
from app.schemas.reviews import DraftReviewRequest
from app.services.reviewer import DraftReviewer, RevisionTaskBuilder
from app.state_machine import InvalidStateTransition, validate_section_transition


class ReviewService:
    """Coordinates deterministic review, comment persistence, and revision task creation."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.reviewer = DraftReviewer()
        self.task_builder = RevisionTaskBuilder()

    def review_current_section_draft(
        self,
        section: OutlineNode,
        request: DraftReviewRequest,
    ) -> tuple[DraftUnit, list[ReviewComment], list[RevisionTask]]:
        draft = self._current_draft(section.id)
        if draft is None:
            raise HTTPException(status_code=400, detail="Section must have a current draft before review.")
        return self.review_draft(section, draft, request)

    def review_draft(
        self,
        section: OutlineNode,
        draft: DraftUnit,
        request: DraftReviewRequest,
    ) -> tuple[DraftUnit, list[ReviewComment], list[RevisionTask]]:
        if draft.section_id != section.id:
            raise HTTPException(status_code=400, detail="Draft does not belong to this section.")
        if draft.kind != DraftKind.SECTION_DRAFT or draft.status != ArtifactStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="Only the current active section draft can be reviewed.")
        if section.status not in {SectionStatus.DRAFTED, SectionStatus.REVISED}:
            raise HTTPException(
                status_code=400,
                detail="Review requires section status drafted or revised.",
            )
        existing = self.session.exec(
            select(ReviewComment).where(
                ReviewComment.target_draft_id == draft.id,
                ReviewComment.resolved == False,  # noqa: E712
            )
        ).first()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="Draft already has unresolved review comments.",
            )

        contract = self._contract_for(section)
        pack = self._active_pack_for(section)
        evidence_items = self._evidence_items_for_pack(section, pack)
        try:
            findings = self.reviewer.review(
                section=section,
                contract=contract,
                evidence_pack=pack,
                evidence_items=evidence_items,
                draft=draft,
                review_instructions=request.review_instructions,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        try:
            validate_section_transition(section.status, SectionStatus.REVIEWED)
        except InvalidStateTransition as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        section.status = SectionStatus.REVIEWED

        comments = [
            ReviewComment(
                target_draft_id=draft.id,
                comment_type=finding.comment_type,
                severity=finding.severity,
                comment=finding.comment,
                suggested_action=finding.suggested_action,
                resolved=False,
            )
            for finding in findings
        ]
        for comment in comments:
            self.session.add(comment)
        self.session.add(section)
        self.session.flush()

        tasks = [
            RevisionTask(
                section_id=section.id,
                draft_id=draft.id,
                task_description=self.task_builder.task_description_for(comment),
                priority=comment.severity,
                status=ArtifactStatus.ACTIVE,
            )
            for comment in comments
        ]
        for task in tasks:
            self.session.add(task)

        if comments:
            try:
                validate_section_transition(section.status, SectionStatus.REVISION_REQUIRED)
            except InvalidStateTransition as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            section.status = SectionStatus.REVISION_REQUIRED
            self.session.add(section)

        self.session.commit()
        self.session.refresh(draft)
        self.session.refresh(section)
        for comment in comments:
            self.session.refresh(comment)
        for task in tasks:
            self.session.refresh(task)
        return draft, comments, tasks

    def _current_draft(self, section_id: uuid.UUID) -> DraftUnit | None:
        return self.session.exec(
            select(DraftUnit)
            .where(
                DraftUnit.section_id == section_id,
                DraftUnit.kind == DraftKind.SECTION_DRAFT,
                DraftUnit.status == ArtifactStatus.ACTIVE,
            )
            .order_by(DraftUnit.version.desc(), DraftUnit.created_at.desc())
        ).first()

    def _contract_for(self, section: OutlineNode) -> SectionContract:
        contract = self.session.exec(
            select(SectionContract).where(SectionContract.section_id == section.id)
        ).first()
        if contract is None:
            raise HTTPException(status_code=400, detail="Section must have a contract before review.")
        return contract

    def _active_pack_for(self, section: OutlineNode) -> EvidencePack:
        pack = self.session.exec(
            select(EvidencePack).where(
                EvidencePack.section_id == section.id,
                EvidencePack.status == ArtifactStatus.ACTIVE,
            )
        ).first()
        if pack is None or not pack.evidence_item_ids:
            raise HTTPException(
                status_code=400,
                detail="Section must have an active evidence pack before review.",
            )
        return pack

    def _evidence_items_for_pack(
        self,
        section: OutlineNode,
        pack: EvidencePack,
    ) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        for item_id in pack.evidence_item_ids:
            item = self.session.get(EvidenceItem, uuid.UUID(item_id))
            if item is None:
                raise HTTPException(status_code=400, detail="Evidence pack references a missing item.")
            if item.paper_id != section.paper_id:
                raise HTTPException(
                    status_code=400,
                    detail="Evidence pack contains an item from a different paper.",
                )
            items.append(item)
        return items
