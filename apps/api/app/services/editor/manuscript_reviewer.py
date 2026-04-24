"""Deterministic global manuscript review for Milestone 5.

TODO(real-llm): replace global heuristics with manuscript-level reviewer/editor
adapters that preserve ManuscriptIssue persistence.
"""

import re
from dataclasses import dataclass

from app.models import AssembledManuscript, OutlineNode, ReviewComment
from app.models.enums import ManuscriptIssueType, Severity


@dataclass(frozen=True)
class ManuscriptFinding:
    """Structured manuscript-level finding before persistence."""

    issue_type: ManuscriptIssueType
    severity: Severity
    message: str
    suggested_action: str


class ManuscriptReviewer:
    """Checks assembled manuscripts for global consistency without model calls."""

    def review(
        self,
        *,
        manuscript: AssembledManuscript,
        sections: list[OutlineNode],
        unresolved_comments_by_section: dict[str, list[ReviewComment]],
        duplicate_sibling_orders: list[str],
        review_instructions: str | None = None,
    ) -> list[ManuscriptFinding]:
        findings: list[ManuscriptFinding] = []
        findings.extend(self._missing_section_findings(manuscript, sections))
        findings.extend(self._unresolved_comment_findings(sections, unresolved_comments_by_section))
        findings.extend(self._required_section_findings(sections))
        findings.extend(self._transition_findings(manuscript))
        findings.extend(self._terminology_findings(manuscript))
        findings.extend(self._ordering_findings(duplicate_sibling_orders))
        if review_instructions:
            findings.append(
                ManuscriptFinding(
                    issue_type=ManuscriptIssueType.STYLE_ISSUE,
                    severity=Severity.LOW,
                    message=f"Global review instruction noted: {review_instructions.strip()}",
                    suggested_action="Apply this instruction during the next manuscript-level edit pass.",
                )
            )
        return self._dedupe(findings)

    def _missing_section_findings(
        self,
        manuscript: AssembledManuscript,
        sections: list[OutlineNode],
    ) -> list[ManuscriptFinding]:
        by_id = {str(section.id): section for section in sections}
        findings = []
        for section_id in manuscript.missing_section_ids:
            section = by_id.get(section_id)
            title = section.title if section else section_id
            findings.append(
                ManuscriptFinding(
                    issue_type=ManuscriptIssueType.MISSING_SECTION_DRAFT,
                    severity=Severity.MEDIUM,
                    message=f"Section '{title}' was assembled with a missing-draft placeholder.",
                    suggested_action="Draft or revise the section, then assemble a new manuscript version.",
                )
            )
        return findings

    def _unresolved_comment_findings(
        self,
        sections: list[OutlineNode],
        unresolved_comments_by_section: dict[str, list[ReviewComment]],
    ) -> list[ManuscriptFinding]:
        by_id = {str(section.id): section for section in sections}
        findings = []
        for section_id, comments in unresolved_comments_by_section.items():
            if not comments:
                continue
            section = by_id.get(section_id)
            title = section.title if section else section_id
            findings.append(
                ManuscriptFinding(
                    issue_type=ManuscriptIssueType.UNRESOLVED_SECTION_REVIEW,
                    severity=Severity.HIGH,
                    message=f"Section '{title}' has {len(comments)} unresolved review comment(s).",
                    suggested_action="Resolve section-level comments before treating the manuscript as final.",
                )
            )
        return findings

    def _required_section_findings(self, sections: list[OutlineNode]) -> list[ManuscriptFinding]:
        titles = {section.title.lower() for section in sections}
        findings = []
        if not any("introduction" in title for title in titles):
            findings.append(
                ManuscriptFinding(
                    issue_type=ManuscriptIssueType.MISSING_INTRODUCTION,
                    severity=Severity.HIGH,
                    message="Outline does not contain an introduction section.",
                    suggested_action="Add or rename a section so the manuscript has an introduction.",
                )
            )
        if not any("conclusion" in title for title in titles):
            findings.append(
                ManuscriptFinding(
                    issue_type=ManuscriptIssueType.MISSING_CONCLUSION,
                    severity=Severity.HIGH,
                    message="Outline does not contain a conclusion section.",
                    suggested_action="Add or rename a section so the manuscript has a conclusion.",
                )
            )
        return findings

    def _transition_findings(self, manuscript: AssembledManuscript) -> list[ManuscriptFinding]:
        section_count = manuscript.content.count("\n## ")
        transition_terms = ("together", "therefore", "however", "in turn", "consequently")
        if section_count < 2 or any(term in manuscript.content.lower() for term in transition_terms):
            return []
        return [
            ManuscriptFinding(
                issue_type=ManuscriptIssueType.MISSING_TRANSITION,
                severity=Severity.MEDIUM,
                message="Manuscript lacks obvious transition language between major sections.",
                suggested_action="Add bridge sentences between major section drafts.",
            )
        ]

    def _terminology_findings(self, manuscript: AssembledManuscript) -> list[ManuscriptFinding]:
        content = manuscript.content
        if re.search(r"\bLLM\b", content) and "large language model" in content.lower():
            return [
                ManuscriptFinding(
                    issue_type=ManuscriptIssueType.TERMINOLOGY_DRIFT,
                    severity=Severity.LOW,
                    message="Manuscript mixes 'LLM' and 'large language model' terminology.",
                    suggested_action="Choose one preferred term or define the abbreviation once.",
                )
            ]
        return []

    def _ordering_findings(self, duplicate_sibling_orders: list[str]) -> list[ManuscriptFinding]:
        return [
            ManuscriptFinding(
                issue_type=ManuscriptIssueType.SECTION_ORDERING_PROBLEM,
                severity=Severity.MEDIUM,
                message=message,
                suggested_action="Give sibling sections unique order_index values.",
            )
            for message in duplicate_sibling_orders
        ]

    def _dedupe(self, findings: list[ManuscriptFinding]) -> list[ManuscriptFinding]:
        seen: set[tuple[ManuscriptIssueType, str]] = set()
        unique: list[ManuscriptFinding] = []
        for finding in findings:
            key = (finding.issue_type, finding.message)
            if key not in seen:
                seen.add(key)
                unique.append(finding)
        return unique
