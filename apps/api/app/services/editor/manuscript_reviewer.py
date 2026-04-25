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
        section_text = self._section_text_by_title(manuscript)
        findings.extend(self._contribution_findings(section_text))
        findings.extend(self._abstract_conclusion_findings(section_text))
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
        findings: list[ManuscriptFinding] = []
        if re.search(r"\bLLM\b", content) and "large language model" in content.lower():
            findings.append(
                ManuscriptFinding(
                    issue_type=ManuscriptIssueType.TERMINOLOGY_DRIFT,
                    severity=Severity.LOW,
                    message="Manuscript mixes 'LLM' and 'large language model' terminology.",
                    suggested_action="Choose one preferred term or define the abbreviation once.",
                )
            )
        variant_groups = [
            (
                ("workflow", "pipeline"),
                "Manuscript alternates between 'workflow' and 'pipeline' for the core process.",
                "Choose one process term or define the distinction explicitly.",
            ),
            (
                ("agent", "assistant"),
                "Manuscript alternates between 'agent' and 'assistant' for the system role.",
                "Use one role term consistently or explain the difference.",
            ),
        ]
        lowered = content.lower()
        for terms, message, suggested_action in variant_groups:
            if all(re.search(rf"\b{re.escape(term)}s?\b", lowered) for term in terms):
                findings.append(
                    ManuscriptFinding(
                        issue_type=ManuscriptIssueType.TERMINOLOGY_DRIFT,
                        severity=Severity.LOW,
                        message=message,
                        suggested_action=suggested_action,
                    )
                )
        return findings

    def _section_text_by_title(self, manuscript: AssembledManuscript) -> dict[str, str]:
        sections: dict[str, list[str]] = {}
        current_title: str | None = None
        for line in manuscript.content.splitlines():
            heading = re.match(r"^(#{2,6})\s+(?P<title>.+?)\s*$", line)
            if heading:
                current_title = heading.group("title").strip().lower()
                sections.setdefault(current_title, [])
                continue
            if current_title is not None:
                sections[current_title].append(line)
        return {title: "\n".join(lines).strip() for title, lines in sections.items()}

    def _contribution_findings(self, section_text: dict[str, str]) -> list[ManuscriptFinding]:
        introduction = self._section_text(section_text, "introduction")
        conclusion = self._section_text(section_text, "conclusion")
        if not introduction and not conclusion:
            return []

        findings: list[ManuscriptFinding] = []
        intro_has_contribution = self._has_contribution_statement(introduction)
        conclusion_has_contribution = self._has_contribution_statement(conclusion)
        if introduction and not intro_has_contribution:
            findings.append(
                ManuscriptFinding(
                    issue_type=ManuscriptIssueType.CONTRIBUTION_ALIGNMENT,
                    severity=Severity.MEDIUM,
                    message="Introduction does not clearly state the manuscript contribution.",
                    suggested_action="Add a concise contribution statement to the introduction.",
                )
            )
        if conclusion and intro_has_contribution and not conclusion_has_contribution:
            findings.append(
                ManuscriptFinding(
                    issue_type=ManuscriptIssueType.CONTRIBUTION_ALIGNMENT,
                    severity=Severity.MEDIUM,
                    message="Conclusion does not return to the contribution stated in the introduction.",
                    suggested_action="Echo the introduction's contribution in the conclusion without adding new unsupported claims.",
                )
            )
        if introduction and conclusion and intro_has_contribution and conclusion_has_contribution:
            intro_terms = self._keyword_set(self._contribution_sentence(introduction) or introduction)
            conclusion_terms = self._keyword_set(self._contribution_sentence(conclusion) or conclusion)
            if intro_terms and self._overlap_ratio(intro_terms, conclusion_terms) < 0.2:
                findings.append(
                    ManuscriptFinding(
                        issue_type=ManuscriptIssueType.CONTRIBUTION_ALIGNMENT,
                        severity=Severity.MEDIUM,
                        message="Introduction and conclusion appear to describe different contributions.",
                        suggested_action="Revise the conclusion so it closes the same contribution framed in the introduction.",
                    )
                )
        return findings

    def _abstract_conclusion_findings(
        self,
        section_text: dict[str, str],
    ) -> list[ManuscriptFinding]:
        abstract = self._section_text(section_text, "abstract")
        conclusion = self._section_text(section_text, "conclusion")
        if not abstract or not conclusion:
            return []

        findings: list[ManuscriptFinding] = []
        abstract_terms = self._keyword_set(abstract)
        conclusion_terms = self._keyword_set(conclusion)
        if abstract_terms and self._overlap_ratio(abstract_terms, conclusion_terms) < 0.15:
            findings.append(
                ManuscriptFinding(
                    issue_type=ManuscriptIssueType.ABSTRACT_CONCLUSION_MISMATCH,
                    severity=Severity.MEDIUM,
                    message="Abstract and conclusion emphasize different topics.",
                    suggested_action="Align the conclusion with the abstract's main terms and delivery promise.",
                )
            )
        if self._has_contribution_statement(conclusion) and not self._has_contribution_statement(abstract):
            findings.append(
                ManuscriptFinding(
                    issue_type=ManuscriptIssueType.ABSTRACT_CONCLUSION_MISMATCH,
                    severity=Severity.MEDIUM,
                    message="Conclusion states a contribution that the abstract does not preview.",
                    suggested_action="Preview the final contribution in the abstract or narrow the conclusion.",
                )
            )
        return findings

    def _section_text(self, section_text: dict[str, str], title_fragment: str) -> str:
        for title, text in section_text.items():
            if title_fragment in title:
                return text
        return ""

    def _has_contribution_statement(self, text: str) -> bool:
        lowered = text.lower()
        patterns = [
            r"\bcontribution(s)?\b",
            r"\bwe (propose|present|introduce|contribute)\b",
            r"\bthis (paper|work|study) (proposes|presents|introduces|contributes)\b",
            r"\bour (approach|framework|method|system) (contributes|provides|offers)\b",
        ]
        return any(re.search(pattern, lowered) for pattern in patterns)

    def _contribution_sentence(self, text: str) -> str | None:
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
            if sentence.strip()
        ]
        for sentence in sentences:
            if self._has_contribution_statement(sentence):
                return sentence
        return None

    def _keyword_set(self, text: str) -> set[str]:
        stopwords = {
            "about",
            "after",
            "also",
            "and",
            "are",
            "before",
            "but",
            "can",
            "for",
            "from",
            "has",
            "have",
            "into",
            "its",
            "later",
            "manuscript",
            "paper",
            "section",
            "that",
            "the",
            "their",
            "these",
            "this",
            "through",
            "with",
        }
        return {
            token
            for token in re.findall(r"\b[a-z][a-z0-9-]{4,}\b", text.lower())
            if token not in stopwords
        }

    def _overlap_ratio(self, first: set[str], second: set[str]) -> float:
        if not first or not second:
            return 0.0
        return len(first & second) / max(1, min(len(first), len(second)))

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
