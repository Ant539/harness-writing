"""Section approval and locking workflow service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import DraftUnit, OutlineNode, ReviewComment, SectionApproval, WorkflowCheckpoint
from app.models.enums import (
    ArtifactStatus,
    DraftKind,
    SectionApprovalStatus,
    SectionStatus,
    WorkflowCheckpointStatus,
)
from app.schemas.approvals import (
    SectionApprovalDecision,
    SectionApprovalRequest,
    SectionApprovalRead,
    SectionUnlockRequest,
)
from app.schemas.outlines import OutlineNodeRead
from app.services.crud import get_or_404
from app.state_machine import InvalidStateTransition, validate_section_transition


class SectionApprovalService:
    """Persist approval decisions and lock/unlock reviewed sections."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def request_approval(
        self,
        section_id: uuid.UUID,
        payload: SectionApprovalRequest,
    ) -> SectionApproval:
        section = get_or_404(self.session, OutlineNode, section_id, "Section")
        draft = self._current_draft(section.id)
        if draft is None:
            raise HTTPException(status_code=400, detail="Approval requires an active section draft.")
        self._validate_checkpoint(section, payload.workflow_checkpoint_id)
        approval = SectionApproval(
            paper_id=section.paper_id,
            section_id=section.id,
            draft_id=draft.id,
            workflow_checkpoint_id=payload.workflow_checkpoint_id,
            status=SectionApprovalStatus.PENDING,
            requested_by=self._clean(payload.requested_by),
            note=self._clean(payload.note),
            metadata_json=dict(payload.metadata),
        )
        self.session.add(approval)
        self.session.commit()
        self.session.refresh(approval)
        return approval

    def approve_section(
        self,
        section_id: uuid.UUID,
        payload: SectionApprovalDecision,
    ) -> tuple[OutlineNode, SectionApproval]:
        section = get_or_404(self.session, OutlineNode, section_id, "Section")
        draft = self._current_draft(section.id)
        if draft is None:
            raise HTTPException(status_code=400, detail="Approval requires an active section draft.")
        if self._unresolved_comments(draft.id):
            raise HTTPException(
                status_code=400,
                detail="Section approval requires resolving active review comments first.",
            )
        if section.status not in {SectionStatus.REVIEWED, SectionStatus.REVISED}:
            raise HTTPException(
                status_code=400,
                detail="Section approval requires section status reviewed or revised.",
            )
        self._validate_checkpoint(section, payload.workflow_checkpoint_id)
        self._supersede_pending(section.id)
        self._transition_section(section, SectionStatus.LOCKED)
        approval = SectionApproval(
            paper_id=section.paper_id,
            section_id=section.id,
            draft_id=draft.id,
            workflow_checkpoint_id=payload.workflow_checkpoint_id,
            status=SectionApprovalStatus.APPROVED,
            decided_by=self._clean(payload.decided_by),
            note=self._clean(payload.note),
            metadata_json=dict(payload.metadata),
        )
        self.session.add(section)
        self.session.add(approval)
        if payload.workflow_checkpoint_id is not None:
            self._resolve_checkpoint(payload.workflow_checkpoint_id, "Section approved and locked.")
        self.session.commit()
        self.session.refresh(section)
        self.session.refresh(approval)
        return section, approval

    def request_changes(
        self,
        section_id: uuid.UUID,
        payload: SectionApprovalDecision,
    ) -> tuple[OutlineNode, SectionApproval]:
        section = get_or_404(self.session, OutlineNode, section_id, "Section")
        draft = self._current_draft(section.id)
        if draft is None:
            raise HTTPException(status_code=400, detail="Change request requires an active section draft.")
        if section.status == SectionStatus.LOCKED:
            raise HTTPException(status_code=400, detail="Unlock the section before requesting changes.")
        self._validate_checkpoint(section, payload.workflow_checkpoint_id)
        self._supersede_pending(section.id)
        approval = SectionApproval(
            paper_id=section.paper_id,
            section_id=section.id,
            draft_id=draft.id,
            workflow_checkpoint_id=payload.workflow_checkpoint_id,
            status=SectionApprovalStatus.CHANGES_REQUESTED,
            decided_by=self._clean(payload.decided_by),
            note=self._clean(payload.note),
            metadata_json=dict(payload.metadata),
        )
        self.session.add(approval)
        if payload.workflow_checkpoint_id is not None:
            self._resolve_checkpoint(payload.workflow_checkpoint_id, "Section changes requested.")
        self.session.commit()
        self.session.refresh(section)
        self.session.refresh(approval)
        return section, approval

    def unlock_section(
        self,
        section_id: uuid.UUID,
        payload: SectionUnlockRequest,
    ) -> tuple[OutlineNode, SectionApproval]:
        section = get_or_404(self.session, OutlineNode, section_id, "Section")
        if section.status != SectionStatus.LOCKED:
            raise HTTPException(status_code=400, detail="Only locked sections can be unlocked.")
        draft = self._current_draft(section.id)
        self._transition_section(section, SectionStatus.REVIEWED)
        approval = SectionApproval(
            paper_id=section.paper_id,
            section_id=section.id,
            draft_id=draft.id if draft is not None else None,
            status=SectionApprovalStatus.UNLOCKED,
            decided_by=self._clean(payload.decided_by),
            note=self._clean(payload.note),
            metadata_json=dict(payload.metadata),
        )
        self.session.add(section)
        self.session.add(approval)
        self.session.commit()
        self.session.refresh(section)
        self.session.refresh(approval)
        return section, approval

    def list_approvals(self, section_id: uuid.UUID) -> list[SectionApproval]:
        get_or_404(self.session, OutlineNode, section_id, "Section")
        return list(
            self.session.exec(
                select(SectionApproval)
                .where(SectionApproval.section_id == section_id)
                .order_by(SectionApproval.created_at)
            ).all()
        )

    def get_approval(self, approval_id: uuid.UUID) -> SectionApproval:
        return get_or_404(self.session, SectionApproval, approval_id, "Section approval")

    def approval_read(self, approval: SectionApproval) -> SectionApprovalRead:
        return SectionApprovalRead(
            id=approval.id,
            paper_id=approval.paper_id,
            section_id=approval.section_id,
            draft_id=approval.draft_id,
            workflow_checkpoint_id=approval.workflow_checkpoint_id,
            status=approval.status,
            requested_by=approval.requested_by,
            decided_by=approval.decided_by,
            note=approval.note,
            metadata=approval.metadata_json,
            created_at=approval.created_at,
            updated_at=approval.updated_at,
        )

    def section_read(self, section: OutlineNode) -> OutlineNodeRead:
        return OutlineNodeRead.model_validate(section)

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

    def _unresolved_comments(self, draft_id: uuid.UUID) -> list[ReviewComment]:
        return list(
            self.session.exec(
                select(ReviewComment).where(
                    ReviewComment.target_draft_id == draft_id,
                    ReviewComment.resolved == False,  # noqa: E712
                )
            ).all()
        )

    def _validate_checkpoint(
        self,
        section: OutlineNode,
        workflow_checkpoint_id: uuid.UUID | None,
    ) -> None:
        if workflow_checkpoint_id is None:
            return
        checkpoint = get_or_404(
            self.session,
            WorkflowCheckpoint,
            workflow_checkpoint_id,
            "Workflow checkpoint",
        )
        if checkpoint.paper_id != section.paper_id:
            raise HTTPException(status_code=400, detail="Checkpoint does not belong to this paper.")
        if checkpoint.section_id is not None and checkpoint.section_id != section.id:
            raise HTTPException(status_code=400, detail="Checkpoint does not belong to this section.")

    def _resolve_checkpoint(self, checkpoint_id: uuid.UUID, note: str) -> None:
        checkpoint = get_or_404(self.session, WorkflowCheckpoint, checkpoint_id, "Workflow checkpoint")
        checkpoint.status = WorkflowCheckpointStatus.RESOLVED
        checkpoint.metadata_json = {**checkpoint.metadata_json, "approval_resolution": note}
        checkpoint.updated_at = datetime.now(timezone.utc)
        self.session.add(checkpoint)

    def _supersede_pending(self, section_id: uuid.UUID) -> None:
        now = datetime.now(timezone.utc)
        pending = self.session.exec(
            select(SectionApproval).where(
                SectionApproval.section_id == section_id,
                SectionApproval.status == SectionApprovalStatus.PENDING,
            )
        ).all()
        for approval in pending:
            approval.status = SectionApprovalStatus.SUPERSEDED
            approval.updated_at = now
            self.session.add(approval)

    def _transition_section(self, section: OutlineNode, target: SectionStatus) -> None:
        try:
            validate_section_transition(section.status, target)
        except InvalidStateTransition as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        section.status = target

    def _clean(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None
