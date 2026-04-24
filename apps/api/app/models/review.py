"""Review comment model."""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import utc_now
from app.models.enums import ReviewCommentType, Severity


class ReviewComment(SQLModel, table=True):
    __tablename__ = "review_comments"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    target_draft_id: uuid.UUID = Field(foreign_key="draft_units.id", index=True)
    comment_type: ReviewCommentType
    severity: Severity
    comment: str
    suggested_action: str
    resolved: bool = False
    created_at: datetime = Field(default_factory=utc_now)
