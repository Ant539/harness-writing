"""General reviewer role for Writing Harness."""

from app.schemas.writing_harness import Draft, ReviewIssue, ReviewReport


class Reviewer:
    """Create structured review reports for non-academic writing."""

    def review(
        self,
        draft: Draft,
        *,
        citation_required: bool = False,
        has_sources: bool = False,
    ) -> ReviewReport:
        issues: list[ReviewIssue] = []
        if len(draft.content.strip()) < 120:
            issues.append(
                self._issue(
                    "R1",
                    "completeness",
                    "medium",
                    "draft",
                    "Draft is very short.",
                    "Thin drafts are hard to evaluate for structure and usefulness.",
                    "Expand the draft with concrete supporting points.",
                    False,
                )
            )
        if citation_required and not has_sources:
            issues.append(
                self._issue(
                    "R2",
                    "citation_quality",
                    "blocker",
                    "draft",
                    "Citation-required task has no verified source notes.",
                    "Research writing should not present unsupported factual claims as sourced.",
                    "Add source notes or mark all factual claims as unverified.",
                    True,
                )
            )
        rubric = {
            "goal_adherence": 0.75,
            "audience_fit": 0.7,
            "structure": 0.65,
            "clarity": 0.75,
            "specificity": 0.55,
            "factuality": 0.45 if citation_required and not has_sources else 0.7,
            "citation_quality": 0.2 if citation_required and not has_sources else 0.7,
            "style_match": 0.7,
            "completeness": 0.55 if issues else 0.7,
            "actionability": 0.7,
        }
        blockers = [issue for issue in issues if issue.blocking]
        return ReviewReport(
            overall_score=sum(rubric.values()) / len(rubric),
            blocking_issues=blockers,
            major_issues=[issue for issue in issues if issue.severity == "high"],
            minor_issues=[issue for issue in issues if issue.severity != "blocker"],
            rubric_scores=rubric,
            factuality_risks=[] if not blockers else ["Unsupported factual or citation-dependent content."],
            citation_risks=[] if not citation_required else ["Citations require verified source metadata."],
            structure_risks=[],
            style_risks=[],
            ready_for_revision=bool(issues),
            ready_for_final=not issues,
        )

    def _issue(
        self,
        issue_id: str,
        dimension: str,
        severity: str,
        location: str,
        problem: str,
        why_it_matters: str,
        suggested_fix: str,
        blocking: bool,
    ) -> ReviewIssue:
        return ReviewIssue(
            issue_id=issue_id,
            dimension=dimension,
            severity=severity,
            location=location,
            problem=problem,
            why_it_matters=why_it_matters,
            suggested_fix=suggested_fix,
            blocking=blocking,
        )
