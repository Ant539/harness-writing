"""Build persisted revision task inputs from review findings."""

from app.models import ReviewComment


class RevisionTaskBuilder:
    """Converts each unresolved review comment into one concrete task."""

    def task_description_for(self, comment: ReviewComment) -> str:
        return f"{comment.comment_type}: {comment.suggested_action}"
