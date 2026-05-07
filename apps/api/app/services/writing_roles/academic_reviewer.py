"""Academic reviewer role for Writing Harness."""

from app.schemas.writing_harness import AcademicBrief, ClaimEvidenceMap, ReviewIssue, ReviewReport, SourceNote


class AcademicReviewer:
    """Review academic drafts for claim, evidence, citation, and readiness risks."""

    def review(
        self,
        *,
        brief: AcademicBrief,
        claim_map: ClaimEvidenceMap,
        source_notes: list[SourceNote],
    ) -> ReviewReport:
        has_sources = bool(source_notes)
        issues: list[ReviewIssue] = []
        if not brief.research_question:
            issues.append(
                self._issue(
                    "A1",
                    "research_question_clarity",
                    "blocker",
                    "AcademicBrief.research_question",
                    "Research question is missing or only implicit.",
                    "A paper workflow needs a stable research question before claims and sections can be final.",
                    "Ask the user to confirm the exact research question.",
                    True,
                )
            )
        if not has_sources:
            issues.append(
                self._issue(
                    "A2",
                    "citation_support",
                    "blocker",
                    "SourceNotes",
                    "No verified source notes are available.",
                    "The system must not fabricate citations or present literature claims without evidence.",
                    "Add verified sources, DOI metadata, or user-approved notes before finalizing.",
                    True,
                )
            )
        unsupported = [claim for claim in claim_map.claims if claim.unsupported_risk == "high"]
        if unsupported:
            issues.append(
                self._issue(
                    "A3",
                    "claim_evidence_alignment",
                    "blocker",
                    "ClaimEvidenceMap",
                    f"{len(unsupported)} important claim(s) lack support.",
                    "Academic writing should be organized around evidence-backed claims.",
                    "Attach sources, experiments, user-provided facts, or soften the claim.",
                    True,
                )
            )
        rubric = {
            "research_question_clarity": 0.2 if not brief.research_question else 0.7,
            "contribution_clarity": 0.35,
            "novelty_claim_strength": 0.65,
            "related_work_coverage": 0.2 if not has_sources else 0.55,
            "claim_evidence_alignment": 0.25 if unsupported else 0.65,
            "method_clarity": 0.4,
            "experiment_validity": 0.4,
            "result_interpretation": 0.45,
            "limitation_coverage": 0.75,
            "citation_support": 0.2 if not has_sources else 0.65,
            "abstract_accuracy": 0.6,
            "section_coherence": 0.65,
            "overclaiming_risk": 0.7,
            "reproducibility": 0.4,
            "final_readiness": 0.2 if issues else 0.7,
        }
        blockers = [issue for issue in issues if issue.blocking]
        return ReviewReport(
            overall_score=sum(rubric.values()) / len(rubric),
            blocking_issues=blockers,
            major_issues=[issue for issue in issues if issue.severity == "high"],
            minor_issues=[],
            rubric_scores=rubric,
            factuality_risks=["Unsupported claims must remain marked until validated."],
            citation_risks=["Do not add bibliography entries unless source metadata is verified."],
            structure_risks=[],
            style_risks=[],
            ready_for_revision=True,
            ready_for_final=not blockers,
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
