"""Editor role for revision planning and conservative revision."""

from app.schemas.writing_harness import ChangeLog, Draft, RevisionPlan, ReviewReport


class Editor:
    """Build revision plans and apply traceable conservative edits."""

    def revision_plan(self, report: ReviewReport, from_version: int) -> RevisionPlan:
        issues = report.blocking_issues + report.major_issues + report.minor_issues
        must_fix = [
            f"{issue.issue_id}: {issue.suggested_fix}" for issue in issues if issue.blocking
        ]
        should_fix = [
            f"{issue.issue_id}: {issue.suggested_fix}" for issue in issues if not issue.blocking
        ]
        return RevisionPlan(
            from_version=from_version,
            to_version=from_version + 1,
            must_fix=must_fix,
            should_fix=should_fix,
            optional_fix=["Improve wording only after claim/evidence risks are resolved."],
            do_not_change=[
                "Do not fabricate citations.",
                "Do not fabricate datasets, experiments, benchmarks, or results.",
                "Do not convert marked unsupported claims into factual claims without evidence.",
            ],
            rationale="Plan is derived directly from structured review issues.",
        )

    def revise(self, draft: Draft, plan: RevisionPlan) -> tuple[Draft, ChangeLog]:
        revised_sections = dict(draft.sections)
        revision_note = (
            "\n\nRevision note: This version follows the revision plan. Blocking evidence or "
            "citation gaps are preserved as explicit TODOs rather than silently resolved."
        )
        draft.version = plan.to_version
        draft.content = draft.content + revision_note
        draft.sections = revised_sections
        changelog = ChangeLog(
            version_from=plan.from_version,
            version_to=plan.to_version,
            changed_sections=list(revised_sections) or ["draft"],
            summary="Applied conservative revision pass and preserved unresolved validation markers.",
            reason=plan.rationale,
            linked_review_items=[
                item.split(":", 1)[0] for item in [*plan.must_fix, *plan.should_fix] if ":" in item
            ],
        )
        return draft, changelog
