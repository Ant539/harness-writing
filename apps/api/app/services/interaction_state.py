"""Agent interaction, clarification, and checkpoint persistence."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    ClarificationRequest,
    DiscoveryRecord,
    Paper,
    UserInteraction,
    WorkflowCheckpoint,
    WorkflowRun,
)
from app.models.enums import (
    ArtifactStatus,
    ClarificationStatus,
    UserInteractionRole,
    WorkflowCheckpointStatus,
)
from app.schemas.interactions import (
    ClarificationRequestCreate,
    ClarificationRequestRead,
    DiscoveryClarificationRequest,
    UserInteractionCreate,
    UserInteractionRead,
    WorkflowCheckpointCreate,
    WorkflowCheckpointRead,
)
from app.services.crud import get_or_404


class InteractionStateService:
    """Persist conversational state that surrounds discovery and workflow runs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_interaction(
        self,
        paper_id: uuid.UUID,
        payload: UserInteractionCreate,
    ) -> UserInteraction:
        get_or_404(self.session, Paper, paper_id, "Paper")
        self._validate_run(paper_id, payload.workflow_run_id)
        self._validate_discovery(paper_id, payload.discovery_id)
        if payload.clarification_request_id is not None:
            clarification = get_or_404(
                self.session,
                ClarificationRequest,
                payload.clarification_request_id,
                "Clarification request",
            )
            if clarification.paper_id != paper_id:
                raise HTTPException(status_code=400, detail="Clarification does not belong to paper.")

        interaction = UserInteraction(
            paper_id=paper_id,
            workflow_run_id=payload.workflow_run_id,
            discovery_id=payload.discovery_id,
            clarification_request_id=payload.clarification_request_id,
            role=payload.role,
            message=payload.message.strip(),
            metadata_json=dict(payload.metadata),
        )
        if not interaction.message:
            raise HTTPException(status_code=400, detail="Interaction message cannot be empty.")
        self.session.add(interaction)
        self.session.commit()
        self.session.refresh(interaction)
        return interaction

    def list_interactions(self, paper_id: uuid.UUID) -> list[UserInteraction]:
        get_or_404(self.session, Paper, paper_id, "Paper")
        return list(
            self.session.exec(
                select(UserInteraction)
                .where(UserInteraction.paper_id == paper_id)
                .order_by(UserInteraction.created_at)
            ).all()
        )

    def create_clarification(
        self,
        paper_id: uuid.UUID,
        payload: ClarificationRequestCreate,
    ) -> ClarificationRequest:
        get_or_404(self.session, Paper, paper_id, "Paper")
        self._validate_run(paper_id, payload.workflow_run_id)
        self._validate_discovery(paper_id, payload.discovery_id)
        clarification = ClarificationRequest(
            paper_id=paper_id,
            workflow_run_id=payload.workflow_run_id,
            discovery_id=payload.discovery_id,
            question=payload.question.strip(),
            context=self._clean_text(payload.context),
            metadata_json=dict(payload.metadata),
        )
        if not clarification.question:
            raise HTTPException(status_code=400, detail="Clarification question cannot be empty.")
        self.session.add(clarification)
        self.session.flush()
        self._add_assistant_interaction_for_clarification(clarification)
        self.session.commit()
        self.session.refresh(clarification)
        return clarification

    def create_discovery_clarifications(
        self,
        paper_id: uuid.UUID,
        payload: DiscoveryClarificationRequest,
    ) -> list[ClarificationRequest]:
        get_or_404(self.session, Paper, paper_id, "Paper")
        self._validate_run(paper_id, payload.workflow_run_id)
        discovery = self._latest_discovery(paper_id)
        discovery_id = discovery.id if discovery is not None else None
        questions = self._discovery_questions(discovery, payload.questions)
        clarifications: list[ClarificationRequest] = []
        for question in questions:
            clarification = ClarificationRequest(
                paper_id=paper_id,
                workflow_run_id=payload.workflow_run_id,
                discovery_id=discovery_id,
                question=question,
                context=self._clean_text(payload.context)
                or "Discovery needs this answer before planning can proceed safely.",
                metadata_json={"source": "discovery_loop"},
            )
            self.session.add(clarification)
            self.session.flush()
            self._add_assistant_interaction_for_clarification(clarification)
            clarifications.append(clarification)
        self.session.commit()
        for clarification in clarifications:
            self.session.refresh(clarification)
        return clarifications

    def answer_clarification(
        self,
        clarification_id: uuid.UUID,
        answer: str,
        *,
        metadata: dict | None = None,
    ) -> ClarificationRequest:
        clarification = get_or_404(
            self.session,
            ClarificationRequest,
            clarification_id,
            "Clarification request",
        )
        cleaned = answer.strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="Clarification answer cannot be empty.")
        interaction = UserInteraction(
            paper_id=clarification.paper_id,
            workflow_run_id=clarification.workflow_run_id,
            discovery_id=clarification.discovery_id,
            clarification_request_id=clarification.id,
            role=UserInteractionRole.USER,
            message=cleaned,
            metadata_json=dict(metadata or {}),
        )
        now = datetime.now(timezone.utc)
        clarification.status = ClarificationStatus.ANSWERED
        clarification.answer = cleaned
        clarification.updated_at = now
        self.session.add(interaction)
        self.session.flush()
        clarification.response_interaction_id = interaction.id
        self.session.add(clarification)
        self._persist_answer_into_discovery(clarification, cleaned, now)
        self.session.commit()
        self.session.refresh(clarification)
        return clarification

    def list_clarifications(
        self,
        paper_id: uuid.UUID,
        *,
        status: ClarificationStatus | None = None,
    ) -> list[ClarificationRequest]:
        get_or_404(self.session, Paper, paper_id, "Paper")
        query = select(ClarificationRequest).where(ClarificationRequest.paper_id == paper_id)
        if status is not None:
            query = query.where(ClarificationRequest.status == status)
        return list(self.session.exec(query.order_by(ClarificationRequest.created_at)).all())

    def create_checkpoint(
        self,
        paper_id: uuid.UUID,
        payload: WorkflowCheckpointCreate,
    ) -> WorkflowCheckpoint:
        get_or_404(self.session, Paper, paper_id, "Paper")
        self._validate_run(paper_id, payload.workflow_run_id)
        checkpoint = WorkflowCheckpoint(
            paper_id=paper_id,
            workflow_run_id=payload.workflow_run_id,
            planning_run_id=payload.planning_run_id,
            section_id=payload.section_id,
            checkpoint_type=payload.checkpoint_type,
            reason=payload.reason.strip(),
            required_actions=list(payload.required_actions),
            clarification_request_ids=[str(item) for item in payload.clarification_request_ids],
            metadata_json=dict(payload.metadata),
        )
        if not checkpoint.reason:
            raise HTTPException(status_code=400, detail="Checkpoint reason cannot be empty.")
        self.session.add(checkpoint)
        self.session.commit()
        self.session.refresh(checkpoint)
        return checkpoint

    def resolve_checkpoint(
        self,
        checkpoint_id: uuid.UUID,
        *,
        resolution_note: str | None = None,
    ) -> WorkflowCheckpoint:
        checkpoint = get_or_404(
            self.session,
            WorkflowCheckpoint,
            checkpoint_id,
            "Workflow checkpoint",
        )
        checkpoint.status = WorkflowCheckpointStatus.RESOLVED
        checkpoint.updated_at = datetime.now(timezone.utc)
        if resolution_note:
            checkpoint.metadata_json = {
                **checkpoint.metadata_json,
                "resolution_note": resolution_note.strip(),
            }
        self.session.add(checkpoint)
        self.session.commit()
        self.session.refresh(checkpoint)
        return checkpoint

    def list_checkpoints(
        self,
        paper_id: uuid.UUID,
        *,
        status: WorkflowCheckpointStatus | None = None,
    ) -> list[WorkflowCheckpoint]:
        get_or_404(self.session, Paper, paper_id, "Paper")
        query = select(WorkflowCheckpoint).where(WorkflowCheckpoint.paper_id == paper_id)
        if status is not None:
            query = query.where(WorkflowCheckpoint.status == status)
        return list(self.session.exec(query.order_by(WorkflowCheckpoint.created_at)).all())

    def interaction_read(self, interaction: UserInteraction) -> UserInteractionRead:
        return UserInteractionRead(
            id=interaction.id,
            paper_id=interaction.paper_id,
            workflow_run_id=interaction.workflow_run_id,
            discovery_id=interaction.discovery_id,
            clarification_request_id=interaction.clarification_request_id,
            role=interaction.role,
            message=interaction.message,
            metadata=interaction.metadata_json,
            created_at=interaction.created_at,
        )

    def clarification_read(self, clarification: ClarificationRequest) -> ClarificationRequestRead:
        return ClarificationRequestRead(
            id=clarification.id,
            paper_id=clarification.paper_id,
            workflow_run_id=clarification.workflow_run_id,
            discovery_id=clarification.discovery_id,
            question=clarification.question,
            context=clarification.context,
            status=clarification.status,
            answer=clarification.answer,
            response_interaction_id=clarification.response_interaction_id,
            metadata=clarification.metadata_json,
            created_at=clarification.created_at,
            updated_at=clarification.updated_at,
        )

    def checkpoint_read(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpointRead:
        return WorkflowCheckpointRead(
            id=checkpoint.id,
            paper_id=checkpoint.paper_id,
            workflow_run_id=checkpoint.workflow_run_id,
            planning_run_id=checkpoint.planning_run_id,
            section_id=checkpoint.section_id,
            checkpoint_type=checkpoint.checkpoint_type,
            status=checkpoint.status,
            reason=checkpoint.reason,
            required_actions=checkpoint.required_actions,
            clarification_request_ids=[
                uuid.UUID(value) for value in checkpoint.clarification_request_ids
            ],
            metadata=checkpoint.metadata_json,
            created_at=checkpoint.created_at,
            updated_at=checkpoint.updated_at,
        )

    def _add_assistant_interaction_for_clarification(
        self,
        clarification: ClarificationRequest,
    ) -> None:
        self.session.add(
            UserInteraction(
                paper_id=clarification.paper_id,
                workflow_run_id=clarification.workflow_run_id,
                discovery_id=clarification.discovery_id,
                clarification_request_id=clarification.id,
                role=UserInteractionRole.ASSISTANT,
                message=clarification.question,
                metadata_json={"source": "clarification_request"},
            )
        )

    def _persist_answer_into_discovery(
        self,
        clarification: ClarificationRequest,
        answer: str,
        now: datetime,
    ) -> None:
        if clarification.discovery_id is None:
            return
        discovery = self.session.get(DiscoveryRecord, clarification.discovery_id)
        if discovery is None or discovery.status != ArtifactStatus.ACTIVE:
            return
        answers = list(discovery.metadata_json.get("clarification_answers", []))
        answers.append(
            {
                "clarification_request_id": str(clarification.id),
                "question": clarification.question,
                "answer": answer,
            }
        )
        discovery.metadata_json = {**discovery.metadata_json, "clarification_answers": answers}
        discovery.updated_at = now
        self.session.add(discovery)

    def _latest_discovery(self, paper_id: uuid.UUID) -> DiscoveryRecord | None:
        return self.session.exec(
            select(DiscoveryRecord)
            .where(DiscoveryRecord.paper_id == paper_id)
            .order_by(DiscoveryRecord.created_at.desc())
        ).first()

    def _discovery_questions(
        self,
        discovery: DiscoveryRecord | None,
        requested: list[str] | None,
    ) -> list[str]:
        if requested:
            return self._unique_clean(requested)
        if discovery is not None:
            pending = [
                question
                for question in discovery.clarifying_questions
                if question not in self._answered_questions(discovery)
            ]
            if pending:
                return self._unique_clean(pending)
        questions: list[str] = []
        if discovery is None or not discovery.user_goal:
            questions.append("What document do you want to produce or improve?")
        if discovery is None or not discovery.audience:
            questions.append("Who is the intended audience or venue for this document?")
        if discovery is None or not discovery.success_criteria:
            questions.append("What would make this writing task successful?")
        if discovery is None or not discovery.current_document_state:
            questions.append("What source material or draft state already exists?")
        return questions or ["Is the current discovery snapshot accurate enough to start planning?"]

    def _answered_questions(self, discovery: DiscoveryRecord) -> set[str]:
        answers = discovery.metadata_json.get("clarification_answers", [])
        if not isinstance(answers, list):
            return set()
        return {
            item.get("question")
            for item in answers
            if isinstance(item, dict) and isinstance(item.get("question"), str)
        }

    def _validate_run(self, paper_id: uuid.UUID, workflow_run_id: uuid.UUID | None) -> None:
        if workflow_run_id is None:
            return
        run = get_or_404(self.session, WorkflowRun, workflow_run_id, "Workflow run")
        if run.paper_id != paper_id:
            raise HTTPException(status_code=400, detail="Workflow run does not belong to paper.")

    def _validate_discovery(self, paper_id: uuid.UUID, discovery_id: uuid.UUID | None) -> None:
        if discovery_id is None:
            return
        discovery = get_or_404(self.session, DiscoveryRecord, discovery_id, "Discovery record")
        if discovery.paper_id != paper_id:
            raise HTTPException(status_code=400, detail="Discovery record does not belong to paper.")

    def _unique_clean(self, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = value.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
        return result

    def _clean_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
