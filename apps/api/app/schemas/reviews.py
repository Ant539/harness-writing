"""Review comment schemas."""

import uuid
from datetime import datetime

from app.models.enums import ReviewCommentType, Severity
from app.schemas.common import ApiSchema
from app.schemas.drafts import DraftUnitRead
from app.schemas.outlines import OutlineNodeRead
from app.schemas.revisions import RevisionTaskRead


class ReviewCommentBase(ApiSchema):
    comment_type: ReviewCommentType
    severity: Severity
    comment: str
    suggested_action: str
    resolved: bool = False


class ReviewCommentCreate(ReviewCommentBase):
    target_draft_id: uuid.UUID


class ReviewCommentForDraftCreate(ReviewCommentBase):
    pass


class ReviewCommentUpdate(ApiSchema):
    comment_type: ReviewCommentType | None = None
    severity: Severity | None = None
    comment: str | None = None
    suggested_action: str | None = None
    resolved: bool | None = None


class ReviewCommentRead(ReviewCommentBase):
    id: uuid.UUID
    target_draft_id: uuid.UUID
    created_at: datetime


class ReviewResolve(ApiSchema):
    resolution_note: str | None = None


class DraftReviewRequest(ApiSchema):
    review_instructions: str | None = None


class DraftReviewResponse(ApiSchema):
    section: OutlineNodeRead
    draft: DraftUnitRead
    comments: list[ReviewCommentRead]
    revision_tasks: list[RevisionTaskRead]
