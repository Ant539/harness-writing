"""Planner-driven section action execution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

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
from app.models.enums import ArtifactStatus, DraftKind, SectionAction, SectionStatus, WorkflowStepStatus
from app.schemas.drafts import DraftGenerationRequest, DraftRevisionRequest
from app.schemas.evidence import EvidencePackBuildRequest
from app.schemas.planning import SectionPlan
from app.schemas.reviews import DraftReviewRequest
from app.services.drafting import DraftingService
from app.services.research import EvidencePackBuilder
from app.services.review import ReviewService


@dataclass(frozen=True)
class SectionActionExecution:
    """Outcome returned to the workflow runner for one section action."""

    status: WorkflowStepStatus
    result: dict[str, Any]


class SectionActionExecutor:
    """Executes planner section actions through existing deterministic services."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.drafting_service = DraftingService(session)
        self.review_service = ReviewService(session)
        self.evidence_pack_builder = EvidencePackBuilder(session)

    def execute(
        self,
        *,
        paper: Paper,
        section: OutlineNode,
        section_plan: SectionPlan,
    ) -> SectionActionExecution:
        base = {
            "section_title": section_plan.section_title,
            "section_id": str(section.id),
            "action": section_plan.action.value,
            "reason": section_plan.reason,
            "needs_evidence": section_plan.needs_evidence,
            "needs_review_loop": section_plan.needs_review_loop,
        }

        if section_plan.action == SectionAction.BLOCKED:
            return self._skipped(base, "blocked", section_plan.reason)
        if section_plan.action == SectionAction.PRESERVE:
            return self._preserve(section, base)
        if section_plan.action == SectionAction.DRAFT:
            return self._draft(paper, section, section_plan, base)
        if section_plan.action == SectionAction.REPAIR:
            return self._revise_existing(section, section_plan, base, action_label="repair")
        if section_plan.action == SectionAction.REWRITE:
            return self._rewrite_or_draft(paper, section, section_plan, base)
        if section_plan.action == SectionAction.POLISH:
            return self._revise_existing(section, section_plan, base, action_label="polish")
        return self._skipped(base, "unsupported_action", "Unsupported section action.")

    def _preserve(self, section: OutlineNode, base: dict[str, Any]) -> SectionActionExecution:
        current = self.drafting_service.current_draft(section.id)
        return self._completed(
            base,
            {
                "outcome": "preserved",
                "draft_id": str(current.id) if current is not None else None,
                "draft_version": current.version if current is not None else None,
                "destructive_generation": False,
            },
        )

    def _draft(
        self,
        paper: Paper,
        section: OutlineNode,
        section_plan: SectionPlan,
        base: dict[str, Any],
        *,
        action_label: str = "draft",
    ) -> SectionActionExecution:
        current = self.drafting_service.current_draft(section.id)
        if current is not None:
            return self._skipped(
                base,
                "existing_draft",
                "Section already has an active draft; draft action will not overwrite it.",
                draft_id=str(current.id),
                draft_version=current.version,
            )

        pack_result = self._ensure_evidence_pack(section, force=False)
        if pack_result["status"] != "ready":
            return self._skipped(
                base,
                pack_result["status"],
                pack_result["reason"],
                evidence_pack=pack_result,
            )

        try:
            draft = self.drafting_service.generate_section_draft(
                section,
                DraftGenerationRequest(
                    drafting_instructions=self._instructions(section_plan, action_label),
                ),
            )
        except HTTPException as exc:
            return self._skipped(base, "draft_precondition_failed", str(exc.detail))

        return self._completed(
            base,
            {
                "outcome": action_label,
                "draft_id": str(draft.id),
                "draft_version": draft.version,
                "supported_evidence_ids": draft.supported_evidence_ids,
                "evidence_pack": pack_result,
            },
        )

    def _rewrite_or_draft(
        self,
        paper: Paper,
        section: OutlineNode,
        section_plan: SectionPlan,
        base: dict[str, Any],
    ) -> SectionActionExecution:
        current = self.drafting_service.current_draft(section.id)
        if current is None:
            return self._draft(paper, section, section_plan, base, action_label="rewrite_from_missing_draft")
        return self._revise_existing(section, section_plan, base, action_label="rewrite")

    def _revise_existing(
        self,
        section: OutlineNode,
        section_plan: SectionPlan,
        base: dict[str, Any],
        *,
        action_label: str,
    ) -> SectionActionExecution:
        current = self.drafting_service.current_draft(section.id)
        if current is None:
            return self._skipped(
                base,
                "missing_existing_draft",
                f"{action_label} requires an active draft or a draftable missing section.",
            )

        service_revision = self._service_revision(section, section_plan, action_label)
        if service_revision is not None:
            return self._completed(base, service_revision)

        fallback = self._fallback_revision(section, current, section_plan, action_label)
        return self._completed(base, fallback)

    def _service_revision(
        self,
        section: OutlineNode,
        section_plan: SectionPlan,
        action_label: str,
    ) -> dict[str, Any] | None:
        if not self._has_contract_and_pack(section):
            return None

        current = self.drafting_service.current_draft(section.id)
        if current is None:
            return None

        if self._unresolved_comments(current.id) or self._active_revision_tasks(section.id, current.id):
            return self._revise_with_existing_context(section, section_plan, action_label)

        if section.status not in {SectionStatus.DRAFTED, SectionStatus.REVISED}:
            return None

        try:
            _, comments, tasks = self.review_service.review_current_section_draft(
                section,
                DraftReviewRequest(review_instructions=self._review_instructions(section_plan, action_label)),
            )
        except HTTPException:
            return None

        if not comments and not tasks:
            return None
        return self._revise_with_existing_context(section, section_plan, action_label)

    def _revise_with_existing_context(
        self,
        section: OutlineNode,
        section_plan: SectionPlan,
        action_label: str,
    ) -> dict[str, Any] | None:
        try:
            previous, revised, comments, tasks = self.drafting_service.revise_section_draft(
                section,
                DraftRevisionRequest(
                    revision_instructions=self._instructions(section_plan, action_label),
                    resolve_comments=True,
                ),
            )
        except HTTPException:
            return None
        return {
            "outcome": action_label,
            "execution_path": "review_revision_service",
            "previous_draft_id": str(previous.id),
            "draft_id": str(revised.id),
            "draft_version": revised.version,
            "resolved_review_comment_ids": [str(comment.id) for comment in comments if comment.resolved],
            "completed_revision_task_ids": [str(task.id) for task in tasks],
        }

    def _fallback_revision(
        self,
        section: OutlineNode,
        current: DraftUnit,
        section_plan: SectionPlan,
        action_label: str,
    ) -> dict[str, Any]:
        current.status = ArtifactStatus.SUPERSEDED
        revised = DraftUnit(
            section_id=section.id,
            kind=DraftKind.SECTION_DRAFT,
            version=self._next_draft_version(section.id),
            content=self._fallback_content(section, current.content, section_plan, action_label),
            supported_evidence_ids=list(current.supported_evidence_ids),
            status=ArtifactStatus.ACTIVE,
        )
        self.session.add(current)
        self.session.add(revised)
        self.session.commit()
        self.session.refresh(current)
        self.session.refresh(revised)
        return {
            "outcome": action_label,
            "execution_path": "conservative_fallback_revision",
            "fallback_reason": (
                "No complete review/revision service path was available; persisted a conservative "
                "draft version that preserves existing substance and records the requested action."
            ),
            "previous_draft_id": str(current.id),
            "draft_id": str(revised.id),
            "draft_version": revised.version,
            "supported_evidence_ids": revised.supported_evidence_ids,
        }

    def _ensure_evidence_pack(self, section: OutlineNode, *, force: bool) -> dict[str, Any]:
        active = self._active_evidence_pack(section.id)
        if active is not None and active.evidence_item_ids:
            return {
                "status": "ready",
                "pack_id": str(active.id),
                "evidence_item_ids": active.evidence_item_ids,
                "created": False,
            }
        contract = self._contract(section.id)
        if contract is None:
            return {
                "status": "missing_contract",
                "reason": "Section needs a contract before evidence alignment or drafting.",
            }
        evidence_items = list(
            self.session.exec(
                select(EvidenceItem)
                .where(EvidenceItem.paper_id == section.paper_id)
                .order_by(EvidenceItem.created_at)
            ).all()
        )
        if not evidence_items:
            return {
                "status": "missing_evidence",
                "reason": "No evidence items are available for deterministic drafting.",
            }
        try:
            pack = self.evidence_pack_builder.build(
                section,
                EvidencePackBuildRequest(
                    notes="Built by planner-driven section action execution.",
                    force=force,
                ),
            )
        except HTTPException as exc:
            return {"status": "evidence_pack_unavailable", "reason": str(exc.detail)}
        return {
            "status": "ready",
            "pack_id": str(pack.id),
            "evidence_item_ids": pack.evidence_item_ids,
            "created": True,
        }

    def _has_contract_and_pack(self, section: OutlineNode) -> bool:
        pack = self._active_evidence_pack(section.id)
        return self._contract(section.id) is not None and pack is not None and bool(pack.evidence_item_ids)

    def _contract(self, section_id: uuid.UUID) -> SectionContract | None:
        return self.session.exec(
            select(SectionContract).where(SectionContract.section_id == section_id)
        ).first()

    def _active_evidence_pack(self, section_id: uuid.UUID) -> EvidencePack | None:
        return self.session.exec(
            select(EvidencePack).where(
                EvidencePack.section_id == section_id,
                EvidencePack.status == ArtifactStatus.ACTIVE,
            )
        ).first()

    def _unresolved_comments(self, draft_id: uuid.UUID) -> list[ReviewComment]:
        return list(
            self.session.exec(
                select(ReviewComment)
                .where(
                    ReviewComment.target_draft_id == draft_id,
                    ReviewComment.resolved == False,  # noqa: E712
                )
                .order_by(ReviewComment.created_at)
            ).all()
        )

    def _active_revision_tasks(self, section_id: uuid.UUID, draft_id: uuid.UUID) -> list[RevisionTask]:
        return list(
            self.session.exec(
                select(RevisionTask)
                .where(
                    RevisionTask.section_id == section_id,
                    RevisionTask.draft_id == draft_id,
                    RevisionTask.status == ArtifactStatus.ACTIVE,
                )
                .order_by(RevisionTask.created_at)
            ).all()
        )

    def _next_draft_version(self, section_id: uuid.UUID) -> int:
        latest = self.session.exec(
            select(DraftUnit)
            .where(DraftUnit.section_id == section_id, DraftUnit.kind == DraftKind.SECTION_DRAFT)
            .order_by(DraftUnit.version.desc())
        ).first()
        return 1 if latest is None else latest.version + 1

    def _fallback_content(
        self,
        section: OutlineNode,
        current_content: str,
        section_plan: SectionPlan,
        action_label: str,
    ) -> str:
        reason = section_plan.reason.strip() or "Planner requested this section action."
        if action_label == "polish":
            note = (
                f"Polish pass applied for {section.title}: tightened wording and flow while preserving "
                "the existing technical substance."
            )
            return f"{current_content.rstrip()}\n\n{note}\n\nPlanner reason: {reason}"
        if action_label == "rewrite":
            return (
                f"{section.title} rewritten from the existing draft basis.\n\n"
                f"{current_content.strip()}\n\n"
                "Rewrite note: this conservative fallback keeps the original substance visible because no "
                "complete review/evidence-backed rewrite path was available.\n\n"
                f"Planner reason: {reason}"
            )
        return (
            f"{current_content.rstrip()}\n\n"
            f"Repair pass applied for {section.title}: preserved recoverable material and recorded the "
            "need for review-grounded follow-up.\n\n"
            f"Planner reason: {reason}"
        )

    def _instructions(self, section_plan: SectionPlan, action_label: str) -> str:
        return (
            f"Planner action: {action_label}. Reason: {section_plan.reason}. "
            "Stay conservative and do not invent unsupported claims."
        )

    def _review_instructions(self, section_plan: SectionPlan, action_label: str) -> str:
        return (
            f"Review before planner action '{action_label}'. Focus on the planner reason: "
            f"{section_plan.reason}"
        )

    def _completed(self, base: dict[str, Any], extra: dict[str, Any]) -> SectionActionExecution:
        return SectionActionExecution(
            status=WorkflowStepStatus.COMPLETED,
            result={**base, **extra},
        )

    def _skipped(
        self,
        base: dict[str, Any],
        outcome: str,
        reason: str,
        **extra: Any,
    ) -> SectionActionExecution:
        return SectionActionExecution(
            status=WorkflowStepStatus.SKIPPED,
            result={**base, "outcome": outcome, "skip_reason": reason, **extra},
        )
