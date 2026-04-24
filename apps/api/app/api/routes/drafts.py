"""Draft unit CRUD routes."""

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session, select

from app.api.deps import get_session
from app.models import DraftUnit, OutlineNode
from app.schemas.drafts import (
    DraftGenerationRequest,
    DraftGenerationResponse,
    DraftRevisionRequest,
    DraftRevisionResponse,
    DraftUnitForSectionCreate,
    DraftUnitRead,
    DraftUnitUpdate,
)
from app.schemas.outlines import OutlineNodeRead
from app.services.crud import create_item, delete_item, get_or_404, update_item
from app.services.drafting import DraftingService

router = APIRouter(tags=["drafts"])


def _draft_read(draft: DraftUnit) -> DraftUnitRead:
    data = draft.model_dump()
    data["supported_evidence_ids"] = [
        value if isinstance(value, uuid.UUID) else uuid.UUID(value)
        for value in draft.supported_evidence_ids
    ]
    return DraftUnitRead.model_validate(data)


def _section_read(section: OutlineNode) -> OutlineNodeRead:
    return OutlineNodeRead.model_validate(section)


@router.post("/sections/{section_id}/draft", response_model=DraftGenerationResponse)
def generate_section_draft(
    section_id: uuid.UUID,
    payload: DraftGenerationRequest,
    session: Session = Depends(get_session),
) -> DraftGenerationResponse:
    section = get_or_404(session, OutlineNode, section_id, "Section")
    draft = DraftingService(session).generate_section_draft(section, payload)
    return DraftGenerationResponse(
        section=_section_read(section),
        draft=_draft_read(draft),
        unsupported_claim_notes=[],
    )


@router.post("/sections/{section_id}/revise", response_model=DraftRevisionResponse)
def revise_section_draft(
    section_id: uuid.UUID,
    payload: DraftRevisionRequest,
    session: Session = Depends(get_session),
) -> DraftRevisionResponse:
    section = get_or_404(session, OutlineNode, section_id, "Section")
    previous, revised, comments, tasks = DraftingService(session).revise_section_draft(
        section,
        payload,
    )
    return DraftRevisionResponse(
        section=_section_read(section),
        previous_draft_id=previous.id,
        draft=_draft_read(revised),
        resolved_review_comment_ids=[comment.id for comment in comments if comment.resolved],
        completed_revision_task_ids=[task.id for task in tasks],
    )


@router.post(
    "/sections/{section_id}/drafts",
    response_model=DraftUnitRead,
    status_code=status.HTTP_201_CREATED,
)
def create_draft(
    section_id: uuid.UUID,
    payload: DraftUnitForSectionCreate,
    session: Session = Depends(get_session),
) -> DraftUnitRead:
    get_or_404(session, OutlineNode, section_id, "Section")
    data = payload.model_dump()
    data["supported_evidence_ids"] = [str(item_id) for item_id in data["supported_evidence_ids"]]
    draft = create_item(session, DraftUnit(section_id=section_id, **data))
    return _draft_read(draft)


@router.get("/sections/{section_id}/drafts", response_model=list[DraftUnitRead])
def list_section_drafts(
    section_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[DraftUnitRead]:
    get_or_404(session, OutlineNode, section_id, "Section")
    drafts = session.exec(
        select(DraftUnit).where(DraftUnit.section_id == section_id).order_by(DraftUnit.version)
    ).all()
    return [_draft_read(draft) for draft in drafts]


@router.get("/sections/{section_id}/drafts/current", response_model=DraftUnitRead | None)
def get_current_section_draft(
    section_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> DraftUnitRead | None:
    get_or_404(session, OutlineNode, section_id, "Section")
    draft = DraftingService(session).current_draft(section_id)
    return _draft_read(draft) if draft else None


@router.get("/drafts/{draft_id}", response_model=DraftUnitRead)
def get_draft(draft_id: uuid.UUID, session: Session = Depends(get_session)) -> DraftUnitRead:
    return _draft_read(get_or_404(session, DraftUnit, draft_id, "Draft"))


@router.patch("/drafts/{draft_id}", response_model=DraftUnitRead)
def update_draft(
    draft_id: uuid.UUID,
    payload: DraftUnitUpdate,
    session: Session = Depends(get_session),
) -> DraftUnitRead:
    draft = get_or_404(session, DraftUnit, draft_id, "Draft")
    data = payload.model_dump(exclude_unset=True)
    if "supported_evidence_ids" in data:
        data["supported_evidence_ids"] = [str(item_id) for item_id in data["supported_evidence_ids"]]
    return _draft_read(update_item(session, draft, data))


@router.delete("/drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(draft_id: uuid.UUID, session: Session = Depends(get_session)) -> Response:
    draft = get_or_404(session, DraftUnit, draft_id, "Draft")
    delete_item(session, draft)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
