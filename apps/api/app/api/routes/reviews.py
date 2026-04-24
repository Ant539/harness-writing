"""Review comment and revision task CRUD routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.api.deps import get_session
from app.models import DraftUnit, OutlineNode, ReviewComment, RevisionTask
from app.models.enums import DraftKind
from app.schemas.drafts import DraftUnitRead
from app.schemas.outlines import OutlineNodeRead
from app.schemas.reviews import (
    DraftReviewRequest,
    DraftReviewResponse,
    ReviewCommentForDraftCreate,
    ReviewCommentRead,
    ReviewCommentUpdate,
    ReviewResolve,
)
from app.schemas.revisions import RevisionTaskForSectionCreate, RevisionTaskRead, RevisionTaskUpdate
from app.services.crud import create_item, delete_item, get_or_404, update_item
from app.services.review import ReviewService

router = APIRouter(tags=["reviews"])


def _draft_read(draft: DraftUnit) -> DraftUnitRead:
    data = draft.model_dump()
    data["supported_evidence_ids"] = [
        value if isinstance(value, uuid.UUID) else uuid.UUID(value)
        for value in draft.supported_evidence_ids
    ]
    return DraftUnitRead.model_validate(data)


def _section_read(section: OutlineNode) -> OutlineNodeRead:
    return OutlineNodeRead.model_validate(section)


def _review_response(
    section: OutlineNode,
    draft: DraftUnit,
    comments: list[ReviewComment],
    tasks: list[RevisionTask],
) -> DraftReviewResponse:
    return DraftReviewResponse(
        section=_section_read(section),
        draft=_draft_read(draft),
        comments=[ReviewCommentRead.model_validate(comment) for comment in comments],
        revision_tasks=[RevisionTaskRead.model_validate(task) for task in tasks],
    )


@router.post("/sections/{section_id}/review", response_model=DraftReviewResponse)
def review_current_section_draft(
    section_id: uuid.UUID,
    payload: DraftReviewRequest,
    session: Session = Depends(get_session),
) -> DraftReviewResponse:
    section = get_or_404(session, OutlineNode, section_id, "Section")
    draft, comments, tasks = ReviewService(session).review_current_section_draft(section, payload)
    return _review_response(section, draft, comments, tasks)


@router.post("/drafts/{draft_id}/review", response_model=DraftReviewResponse)
def review_selected_draft(
    draft_id: uuid.UUID,
    payload: DraftReviewRequest,
    session: Session = Depends(get_session),
) -> DraftReviewResponse:
    draft = get_or_404(session, DraftUnit, draft_id, "Draft")
    section = get_or_404(session, OutlineNode, draft.section_id, "Section")
    reviewed_draft, comments, tasks = ReviewService(session).review_draft(section, draft, payload)
    return _review_response(section, reviewed_draft, comments, tasks)


@router.post(
    "/drafts/{draft_id}/reviews",
    response_model=ReviewCommentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_review_comment(
    draft_id: uuid.UUID,
    payload: ReviewCommentForDraftCreate,
    session: Session = Depends(get_session),
) -> ReviewComment:
    get_or_404(session, DraftUnit, draft_id, "Draft")
    return create_item(session, ReviewComment(target_draft_id=draft_id, **payload.model_dump()))


@router.get("/drafts/{draft_id}/reviews", response_model=list[ReviewCommentRead])
def list_draft_reviews(
    draft_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[ReviewComment]:
    get_or_404(session, DraftUnit, draft_id, "Draft")
    return list(
        session.exec(
            select(ReviewComment)
            .where(ReviewComment.target_draft_id == draft_id)
            .order_by(ReviewComment.created_at)
        ).all()
    )


@router.get("/sections/{section_id}/reviews", response_model=list[ReviewCommentRead])
def list_section_reviews(
    section_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[ReviewComment]:
    get_or_404(session, OutlineNode, section_id, "Section")
    draft_ids = [
        draft.id
        for draft in session.exec(
            select(DraftUnit).where(
                DraftUnit.section_id == section_id,
                DraftUnit.kind == DraftKind.SECTION_DRAFT,
            )
        ).all()
    ]
    if not draft_ids:
        return []
    return list(
        session.exec(
            select(ReviewComment)
            .where(ReviewComment.target_draft_id.in_(draft_ids))
            .order_by(ReviewComment.created_at)
        ).all()
    )


@router.get("/reviews/{review_id}", response_model=ReviewCommentRead)
def get_review_comment(
    review_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> ReviewComment:
    return get_or_404(session, ReviewComment, review_id, "Review comment")


@router.patch("/reviews/{review_id}", response_model=ReviewCommentRead)
def update_review_comment(
    review_id: uuid.UUID,
    payload: ReviewCommentUpdate,
    session: Session = Depends(get_session),
) -> ReviewComment:
    review = get_or_404(session, ReviewComment, review_id, "Review comment")
    return update_item(session, review, payload.model_dump(exclude_unset=True))


@router.post("/reviews/{review_id}/resolve", response_model=ReviewCommentRead)
def resolve_review_comment(
    review_id: uuid.UUID,
    payload: ReviewResolve,
    session: Session = Depends(get_session),
) -> ReviewComment:
    review = get_or_404(session, ReviewComment, review_id, "Review comment")
    _ = payload.resolution_note
    return update_item(session, review, {"resolved": True})


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review_comment(
    review_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> Response:
    review = get_or_404(session, ReviewComment, review_id, "Review comment")
    delete_item(session, review)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/sections/{section_id}/revision-tasks",
    response_model=RevisionTaskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_revision_task(
    section_id: uuid.UUID,
    payload: RevisionTaskForSectionCreate,
    session: Session = Depends(get_session),
) -> RevisionTask:
    get_or_404(session, OutlineNode, section_id, "Section")
    draft = get_or_404(session, DraftUnit, payload.draft_id, "Draft")
    if draft.section_id != section_id:
        raise HTTPException(status_code=400, detail="Draft must belong to the section.")
    return create_item(session, RevisionTask(section_id=section_id, **payload.model_dump()))


@router.get("/sections/{section_id}/revision-tasks", response_model=list[RevisionTaskRead])
def list_section_revision_tasks(
    section_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[RevisionTask]:
    get_or_404(session, OutlineNode, section_id, "Section")
    return list(
        session.exec(
            select(RevisionTask)
            .where(RevisionTask.section_id == section_id)
            .order_by(RevisionTask.created_at)
        ).all()
    )


@router.get("/revision-tasks/{task_id}", response_model=RevisionTaskRead)
def get_revision_task(task_id: uuid.UUID, session: Session = Depends(get_session)) -> RevisionTask:
    return get_or_404(session, RevisionTask, task_id, "Revision task")


@router.patch("/revision-tasks/{task_id}", response_model=RevisionTaskRead)
def update_revision_task(
    task_id: uuid.UUID,
    payload: RevisionTaskUpdate,
    session: Session = Depends(get_session),
) -> RevisionTask:
    task = get_or_404(session, RevisionTask, task_id, "Revision task")
    return update_item(session, task, payload.model_dump(exclude_unset=True))


@router.delete("/revision-tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_revision_task(task_id: uuid.UUID, session: Session = Depends(get_session)) -> Response:
    task = get_or_404(session, RevisionTask, task_id, "Revision task")
    delete_item(session, task)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
