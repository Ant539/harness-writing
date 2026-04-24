"""Deterministic evidence-support checks used by the Milestone 4 reviewer.

TODO(real-llm): replace ID/citation checks with claim-to-evidence verification
that can still report structured ReviewFinding-compatible issues.
"""

from app.models import DraftUnit, EvidenceItem, EvidencePack, SectionContract
from app.models.enums import ReviewCommentType, Severity


class SupportChecker:
    """Checks draft-to-evidence alignment without calling an external verifier."""

    def check(
        self,
        *,
        contract: SectionContract,
        evidence_pack: EvidencePack,
        evidence_items: list[EvidenceItem],
        draft: DraftUnit,
    ):
        findings = []
        draft_ids = set(draft.supported_evidence_ids)
        pack_ids = set(evidence_pack.evidence_item_ids)
        if not draft_ids:
            findings.append(
                self._finding(
                    ReviewCommentType.MISSING_CITATION,
                    Severity.HIGH,
                    "Draft has no supported evidence IDs.",
                    "Attach at least one evidence item to the draft before approval.",
                )
            )
        missing_from_pack = sorted(draft_ids - pack_ids)
        if missing_from_pack:
            findings.append(
                self._finding(
                    ReviewCommentType.MISSING_CITATION,
                    Severity.HIGH,
                    "Draft references evidence IDs that are not in the active evidence pack.",
                    "Replace unsupported evidence references with IDs from the active pack.",
                )
            )
        if len(draft_ids & pack_ids) < contract.required_evidence_count:
            findings.append(
                self._finding(
                    ReviewCommentType.HALLUCINATION_RISK,
                    Severity.HIGH,
                    "Draft uses fewer evidence items than the section contract requires.",
                    "Add evidence-grounded support until the contract evidence count is met.",
                )
            )

        content = draft.content
        citations_by_key = {item.citation_key: item for item in evidence_items if item.citation_key}
        for citation_key in contract.required_citations:
            if citation_key and f"[{citation_key}]" not in content:
                findings.append(
                    self._finding(
                        ReviewCommentType.MISSING_CITATION,
                        Severity.HIGH,
                        f"Required citation [{citation_key}] is missing from the draft.",
                        f"Add citation [{citation_key}] where its evidence supports a claim.",
                    )
                )
        for citation_key in citations_by_key:
            if f"[{citation_key}]" not in content:
                findings.append(
                    self._finding(
                        ReviewCommentType.MISSING_CITATION,
                        Severity.MEDIUM,
                        f"Evidence citation [{citation_key}] is available but absent from draft text.",
                        f"Use [{citation_key}] near the claim supported by that evidence item.",
                    )
                )
        return findings

    def _finding(
        self,
        comment_type: ReviewCommentType,
        severity: Severity,
        comment: str,
        suggested_action: str,
    ):
        from app.services.reviewer.draft_reviewer import ReviewFinding

        return ReviewFinding(
            comment_type=comment_type,
            severity=severity,
            comment=comment,
            suggested_action=suggested_action,
        )


class VerifierService:
    """Boundary object for Milestone 4 verifier orchestration."""

    def __init__(self) -> None:
        self.support_checker = SupportChecker()
