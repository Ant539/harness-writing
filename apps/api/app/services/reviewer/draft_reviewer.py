"""Section draft review."""

import re
from dataclasses import dataclass

from app.models import DraftUnit, EvidenceItem, EvidencePack, OutlineNode, SectionContract
from app.models.enums import ReviewCommentType, Severity
from app.services.llm import LLMMessage, LLMProvider, LLMRequest, get_llm_provider
from app.services.llm.json_utils import parse_json_object
from app.services.llm.providers import LLMProviderError
from app.services.verifier import SupportChecker


@dataclass(frozen=True)
class ReviewFinding:
    """Structured finding before it is persisted as a ReviewComment."""

    comment_type: ReviewCommentType
    severity: Severity
    comment: str
    suggested_action: str


class DraftReviewer:
    """Turns deterministic and optional model review into structured comments."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.support_checker = SupportChecker()
        self.llm_provider = llm_provider if llm_provider is not None else get_llm_provider()

    def review(
        self,
        *,
        section: OutlineNode,
        contract: SectionContract,
        evidence_pack: EvidencePack,
        evidence_items: list[EvidenceItem],
        draft: DraftUnit,
        review_instructions: str | None = None,
    ) -> list[ReviewFinding]:
        findings = [
            *self.support_checker.check(
                contract=contract,
                evidence_pack=evidence_pack,
                evidence_items=evidence_items,
                draft=draft,
            )
        ]
        findings.extend(self._structure_findings(section, contract, draft))
        findings.extend(self._redundancy_findings(draft))
        findings.extend(self._transition_findings(draft))
        findings.extend(self._overclaim_findings(draft))
        if self.llm_provider is not None:
            findings.extend(
                self._llm_findings(
                    section=section,
                    contract=contract,
                    evidence_pack=evidence_pack,
                    evidence_items=evidence_items,
                    draft=draft,
                    review_instructions=review_instructions,
                )
            )

        if review_instructions:
            findings.append(
                ReviewFinding(
                    comment_type=ReviewCommentType.STYLE_ISSUE,
                    severity=Severity.LOW,
                    comment=f"Reviewer instruction noted: {review_instructions.strip()}",
                    suggested_action="Apply the reviewer instruction during the next revision pass.",
                )
            )
        return self._dedupe(findings)

    def _structure_findings(
        self,
        section: OutlineNode,
        contract: SectionContract,
        draft: DraftUnit,
    ) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        paragraphs = [paragraph for paragraph in draft.content.split("\n\n") if paragraph.strip()]
        if len(paragraphs) < 2:
            findings.append(
                ReviewFinding(
                    comment_type=ReviewCommentType.LOGIC_GAP,
                    severity=Severity.MEDIUM,
                    comment=f"{section.title} has fewer than two paragraphs, which weakens section structure.",
                    suggested_action="Split the section into claim, evidence, and transition paragraphs.",
                )
            )
        word_count = len(re.findall(r"\b\w+\b", draft.content))
        if contract.length_min is not None and word_count < contract.length_min:
            findings.append(
                ReviewFinding(
                    comment_type=ReviewCommentType.LOGIC_GAP,
                    severity=Severity.MEDIUM,
                    comment=(
                        f"Draft has {word_count} words, below the contract minimum of "
                        f"{contract.length_min}."
                    ),
                    suggested_action="Expand the section with evidence-grounded explanation before approval.",
                )
            )
        return findings

    def _redundancy_findings(self, draft: DraftUnit) -> list[ReviewFinding]:
        sentences = [
            re.sub(r"[^a-z0-9 ]", "", sentence.lower()).strip()
            for sentence in re.split(r"[.!?]+", draft.content)
        ]
        repeated = {sentence for sentence in sentences if sentence and sentences.count(sentence) > 1}
        if not repeated:
            return []
        return [
            ReviewFinding(
                comment_type=ReviewCommentType.REDUNDANCY,
                severity=Severity.LOW,
                comment="Draft repeats at least one sentence-level idea without adding new support.",
                suggested_action="Remove repeated phrasing or combine duplicated points.",
            )
        ]

    def _transition_findings(self, draft: DraftUnit) -> list[ReviewFinding]:
        transition_terms = ("together", "therefore", "however", "consequently", "in turn")
        if any(term in draft.content.lower() for term in transition_terms):
            return []
        return [
            ReviewFinding(
                comment_type=ReviewCommentType.LOGIC_GAP,
                severity=Severity.MEDIUM,
                comment="Draft lacks an explicit transition connecting its evidence to the section argument.",
                suggested_action="Add a transition sentence that explains how the evidence advances the section.",
            )
        ]

    def _overclaim_findings(self, draft: DraftUnit) -> list[ReviewFinding]:
        overclaim_terms = {"proves", "guarantees", "always", "never", "undeniably"}
        content = draft.content.lower()
        if not any(term in content for term in overclaim_terms):
            return []
        return [
            ReviewFinding(
                comment_type=ReviewCommentType.OVERCLAIM,
                severity=Severity.HIGH,
                comment="Draft uses absolute wording that may exceed the evidence support.",
                suggested_action="Qualify absolute claims or tie them directly to specific evidence.",
            )
        ]

    def _dedupe(self, findings: list[ReviewFinding]) -> list[ReviewFinding]:
        seen: set[tuple[ReviewCommentType, str]] = set()
        unique: list[ReviewFinding] = []
        for finding in findings:
            key = (finding.comment_type, finding.comment)
            if key not in seen:
                seen.add(key)
            unique.append(finding)
        return unique

    def _llm_findings(
        self,
        *,
        section: OutlineNode,
        contract: SectionContract,
        evidence_pack: EvidencePack,
        evidence_items: list[EvidenceItem],
        draft: DraftUnit,
        review_instructions: str | None,
    ) -> list[ReviewFinding]:
        evidence_context = self._evidence_context(evidence_items, set(evidence_pack.evidence_item_ids))
        system = (
            "You are the reviewer in Paper Harness. Review academic section drafts "
            "for unsupported claims, logic gaps, overclaims, redundancy, and style "
            "problems. Use only the supplied evidence and contract. Return strict JSON only."
        )
        user = (
            "Review this section draft.\n\n"
            f"Section title: {section.title}\n"
            f"Contract purpose: {contract.purpose}\n"
            f"Required claims: {contract.required_claims}\n"
            f"Forbidden patterns: {contract.forbidden_patterns}\n"
            f"Review instructions: {review_instructions or 'none'}\n\n"
            "Evidence items:\n"
            f"{evidence_context}\n\n"
            "Draft:\n"
            f"{draft.content}\n\n"
            "Return JSON with this shape only:\n"
            "{\n"
            '  "findings": [\n'
            "    {\n"
            '      "comment_type": "logic_gap",\n'
            '      "severity": "medium",\n'
            '      "comment": "Specific issue.",\n'
            '      "suggested_action": "Concrete revision action."\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Allowed comment_type values: missing_citation, logic_gap, redundancy, "
            "style_issue, overclaim, hallucination_risk. Allowed severity values: "
            "low, medium, high, blocker. Return an empty findings list if no issue remains."
        )
        try:
            result = self.llm_provider.generate(
                LLMRequest(
                    messages=[
                        LLMMessage(role="system", content=system),
                        LLMMessage(role="user", content=user),
                    ],
                    expect_json=True,
                )
            )
            payload = parse_json_object(result.content)
            return self._findings_from_payload(payload)
        except (LLMProviderError, ValueError, KeyError, TypeError) as exc:
            raise RuntimeError(f"LLM draft review failed: {exc}") from exc

    def _findings_from_payload(self, payload: dict) -> list[ReviewFinding]:
        raw_findings = payload.get("findings", [])
        if not isinstance(raw_findings, list):
            raise ValueError("Review JSON field 'findings' must be a list.")
        findings: list[ReviewFinding] = []
        for item in raw_findings:
            if not isinstance(item, dict):
                continue
            comment = item.get("comment")
            action = item.get("suggested_action")
            if not isinstance(comment, str) or not comment.strip():
                continue
            if not isinstance(action, str) or not action.strip():
                continue
            findings.append(
                ReviewFinding(
                    comment_type=self._enum_value(
                        ReviewCommentType,
                        item.get("comment_type"),
                        ReviewCommentType.LOGIC_GAP,
                    ),
                    severity=self._enum_value(Severity, item.get("severity"), Severity.MEDIUM),
                    comment=comment.strip(),
                    suggested_action=action.strip(),
                )
            )
        return findings

    def _enum_value(self, enum_type, value: object, default):
        if isinstance(value, str):
            try:
                return enum_type(value)
            except ValueError:
                return default
        return default

    def _evidence_context(self, evidence_items: list[EvidenceItem], allowed_ids: set[str]) -> str:
        lines = []
        for item in evidence_items:
            item_id = str(item.id)
            if item_id not in allowed_ids:
                continue
            content = " ".join(item.content.split())
            citation = f", citation_key={item.citation_key}" if item.citation_key else ""
            lines.append(f"- id={item_id}{citation}: {content[:1200]}")
        return "\n".join(lines) or "- No usable evidence items supplied."


class ReviewerService:
    """Boundary object for Milestone 4 reviewer orchestration."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.draft_reviewer = DraftReviewer(llm_provider=llm_provider)
