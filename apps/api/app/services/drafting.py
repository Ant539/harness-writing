"""Section drafting and revision orchestration."""

import uuid

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    DraftUnit,
    EvidenceItem,
    EvidencePack,
    OutlineNode,
    Paper,
    ReviewComment,
    RevisionTask,
    SectionContract,
)
from app.models.enums import ArtifactStatus, DraftKind, SectionStatus
from app.schemas.drafts import DraftGenerationRequest, DraftRevisionRequest
from app.services.writer import RevisionGenerator, SectionDraftGenerator
from app.state_machine import InvalidStateTransition, validate_section_transition


class DraftingService:
    """Coordinates deterministic writer output with persistence and lifecycle guards."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.draft_generator = SectionDraftGenerator()
        self.revision_generator = RevisionGenerator()

    def generate_section_draft(
        self,
        section: OutlineNode,
        request: DraftGenerationRequest,
    ) -> DraftUnit:
        if self.current_draft(section.id) is not None:
            raise HTTPException(
                status_code=409,
                detail="Section already has a current draft. Use the revision flow to create a new version.",
            )
        if section.status != SectionStatus.EVIDENCE_READY:
            raise HTTPException(
                status_code=400,
                detail="Draft generation requires section status evidence_ready.",
            )

        paper = self.session.get(Paper, section.paper_id)
        if paper is None:
            raise HTTPException(status_code=404, detail="Paper not found")
        contract = self._contract_for(section)
        pack = self._active_pack_for(section)
        evidence_items = self._evidence_items_for_pack(section, pack)

        try:
            generated = self.draft_generator.generate(
                paper=paper,
                section=section,
                contract=contract,
                evidence_pack=pack,
                evidence_items=evidence_items,
                drafting_instructions=request.drafting_instructions,
                neighboring_section_context=request.neighboring_section_context,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        draft = DraftUnit(
            section_id=section.id,
            kind=DraftKind.SECTION_DRAFT,
            version=self._next_version(section.id),
            content=generated.content,
            supported_evidence_ids=generated.supported_evidence_ids,
            status=ArtifactStatus.ACTIVE,
        )

        try:
            validate_section_transition(section.status, SectionStatus.DRAFTED)
        except InvalidStateTransition as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        section.status = SectionStatus.DRAFTED
        self.session.add(draft)
        self.session.add(section)
        self.session.commit()
        self.session.refresh(draft)
        self.session.refresh(section)
        return draft

    def revise_section_draft(
        self,
        section: OutlineNode,
        request: DraftRevisionRequest,
    ) -> tuple[DraftUnit, DraftUnit, list[ReviewComment], list[RevisionTask]]:
        if section.status not in {SectionStatus.REVIEWED, SectionStatus.REVISION_REQUIRED}:
            raise HTTPException(
                status_code=400,
                detail="Revision requires section status reviewed or revision_required.",
            )
        current = self.current_draft(section.id)
        if current is None:
            raise HTTPException(status_code=400, detail="Section must have a current draft before revision.")

        contract = self._contract_for(section)
        pack = self._active_pack_for(section)
        evidence_items = self._evidence_items_for_pack(section, pack)
        comments = self._review_comments_for(current, request.review_comment_ids)
        tasks = self._revision_tasks_for(section, current, request.revision_task_ids)
        if not comments and not tasks:
            raise HTTPException(
                status_code=400,
                detail="Revision requires at least one review comment or revision task.",
            )

        if section.status == SectionStatus.REVIEWED:
            try:
                validate_section_transition(section.status, SectionStatus.REVISION_REQUIRED)
            except InvalidStateTransition as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            section.status = SectionStatus.REVISION_REQUIRED

        try:
            validate_section_transition(section.status, SectionStatus.REVISED)
        except InvalidStateTransition as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            generated = self.revision_generator.generate(
                section=section,
                contract=contract,
                evidence_pack=pack,
                evidence_items=evidence_items,
                current_content=current.content,
                review_comments=comments,
                revision_tasks=tasks,
                revision_instructions=request.revision_instructions,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        current.status = ArtifactStatus.SUPERSEDED
        revised = DraftUnit(
            section_id=section.id,
            kind=DraftKind.SECTION_DRAFT,
            version=self._next_version(section.id),
            content=generated.content,
            supported_evidence_ids=generated.supported_evidence_ids,
            status=ArtifactStatus.ACTIVE,
        )
        if request.resolve_comments:
            for comment in comments:
                comment.resolved = True
                self.session.add(comment)
        for task in tasks:
            task.status = ArtifactStatus.APPROVED
            self.session.add(task)

        section.status = SectionStatus.REVISED
        self.session.add(current)
        self.session.add(revised)
        self.session.add(section)
        self.session.commit()
        self.session.refresh(current)
        self.session.refresh(revised)
        self.session.refresh(section)
        for comment in comments:
            self.session.refresh(comment)
        for task in tasks:
            self.session.refresh(task)
        return current, revised, comments, tasks

    def current_draft(self, section_id: uuid.UUID) -> DraftUnit | None:
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
            raise HTTPException(status_code=400, detail="Section must have a contract before drafting.")
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
                detail="Section must have an active evidence pack with at least one item.",
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

    def _review_comments_for(
        self,
        draft: DraftUnit,
        requested_ids: list[uuid.UUID] | None,
    ) -> list[ReviewComment]:
        query = select(ReviewComment).where(
            ReviewComment.target_draft_id == draft.id,
            ReviewComment.resolved == False,  # noqa: E712
        )
        comments = list(self.session.exec(query.order_by(ReviewComment.created_at)).all())
        if requested_ids is None:
            return comments
        requested = set(requested_ids)
        selected = [comment for comment in comments if comment.id in requested]
        if len(selected) != len(requested):
            raise HTTPException(
                status_code=400,
                detail="Requested review comments must be unresolved and belong to the current draft.",
            )
        return selected

    def _revision_tasks_for(
        self,
        section: OutlineNode,
        draft: DraftUnit,
        requested_ids: list[uuid.UUID] | None,
    ) -> list[RevisionTask]:
        tasks = list(
            self.session.exec(
                select(RevisionTask)
                .where(
                    RevisionTask.section_id == section.id,
                    RevisionTask.draft_id == draft.id,
                    RevisionTask.status == ArtifactStatus.ACTIVE,
                )
                .order_by(RevisionTask.created_at)
            ).all()
        )
        if requested_ids is None:
            return tasks
        requested = set(requested_ids)
        selected = [task for task in tasks if task.id in requested]
        if len(selected) != len(requested):
            raise HTTPException(
                status_code=400,
                detail="Requested revision tasks must be active and belong to the current draft.",
            )
        return selected

    def _next_version(self, section_id: uuid.UUID) -> int:
        latest = self.session.exec(
            select(DraftUnit)
            .where(DraftUnit.section_id == section_id, DraftUnit.kind == DraftKind.SECTION_DRAFT)
            .order_by(DraftUnit.version.desc())
        ).first()
        return 1 if latest is None else latest.version + 1
