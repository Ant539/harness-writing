"""Agent interaction, clarification, and checkpoint routes."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api.deps import get_session
from app.models.enums import ClarificationStatus, WorkflowCheckpointStatus
from app.schemas.interactions import (
    ClarificationAnswer,
    ClarificationRequestCreate,
    ClarificationRequestRead,
    DiscoveryClarificationRequest,
    UserInteractionCreate,
    UserInteractionRead,
    WorkflowCheckpointCreate,
    WorkflowCheckpointRead,
    WorkflowCheckpointResolve,
)
from app.services.interaction_state import InteractionStateService

router = APIRouter(tags=["interactions"])


@router.post("/papers/{paper_id}/interactions", response_model=UserInteractionRead)
def create_interaction(
    paper_id: uuid.UUID,
    payload: UserInteractionCreate,
    session: Session = Depends(get_session),
) -> UserInteractionRead:
    service = InteractionStateService(session)
    return service.interaction_read(service.create_interaction(paper_id, payload))


@router.get("/papers/{paper_id}/interactions", response_model=list[UserInteractionRead])
def list_interactions(
    paper_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[UserInteractionRead]:
    service = InteractionStateService(session)
    return [service.interaction_read(item) for item in service.list_interactions(paper_id)]


@router.post("/papers/{paper_id}/clarifications", response_model=ClarificationRequestRead)
def create_clarification(
    paper_id: uuid.UUID,
    payload: ClarificationRequestCreate,
    session: Session = Depends(get_session),
) -> ClarificationRequestRead:
    service = InteractionStateService(session)
    return service.clarification_read(service.create_clarification(paper_id, payload))


@router.post(
    "/papers/{paper_id}/discovery/clarifications",
    response_model=list[ClarificationRequestRead],
)
def create_discovery_clarifications(
    paper_id: uuid.UUID,
    payload: DiscoveryClarificationRequest,
    session: Session = Depends(get_session),
) -> list[ClarificationRequestRead]:
    service = InteractionStateService(session)
    return [
        service.clarification_read(item)
        for item in service.create_discovery_clarifications(paper_id, payload)
    ]


@router.get("/papers/{paper_id}/clarifications", response_model=list[ClarificationRequestRead])
def list_clarifications(
    paper_id: uuid.UUID,
    status: ClarificationStatus | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[ClarificationRequestRead]:
    service = InteractionStateService(session)
    return [
        service.clarification_read(item)
        for item in service.list_clarifications(paper_id, status=status)
    ]


@router.post("/clarifications/{clarification_id}/answer", response_model=ClarificationRequestRead)
def answer_clarification(
    clarification_id: uuid.UUID,
    payload: ClarificationAnswer,
    session: Session = Depends(get_session),
) -> ClarificationRequestRead:
    service = InteractionStateService(session)
    clarification = service.answer_clarification(
        clarification_id,
        payload.answer,
        metadata=payload.metadata,
    )
    return service.clarification_read(clarification)


@router.post("/papers/{paper_id}/workflow-checkpoints", response_model=WorkflowCheckpointRead)
def create_checkpoint(
    paper_id: uuid.UUID,
    payload: WorkflowCheckpointCreate,
    session: Session = Depends(get_session),
) -> WorkflowCheckpointRead:
    service = InteractionStateService(session)
    return service.checkpoint_read(service.create_checkpoint(paper_id, payload))


@router.get("/papers/{paper_id}/workflow-checkpoints", response_model=list[WorkflowCheckpointRead])
def list_checkpoints(
    paper_id: uuid.UUID,
    status: WorkflowCheckpointStatus | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[WorkflowCheckpointRead]:
    service = InteractionStateService(session)
    return [service.checkpoint_read(item) for item in service.list_checkpoints(paper_id, status=status)]


@router.post(
    "/workflow-checkpoints/{checkpoint_id}/resolve",
    response_model=WorkflowCheckpointRead,
)
def resolve_checkpoint(
    checkpoint_id: uuid.UUID,
    payload: WorkflowCheckpointResolve,
    session: Session = Depends(get_session),
) -> WorkflowCheckpointRead:
    service = InteractionStateService(session)
    return service.checkpoint_read(
        service.resolve_checkpoint(checkpoint_id, resolution_note=payload.resolution_note)
    )
