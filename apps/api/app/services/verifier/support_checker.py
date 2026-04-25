"""Deterministic evidence-support and provenance checks used by the reviewer.

TODO(real-llm): replace ID/citation checks with claim-to-evidence verification
that can still report structured ReviewFinding-compatible issues.
"""

import re

from app.models import DraftUnit, EvidenceItem, EvidencePack, OutlineNode, SectionContract
from app.models.enums import ReviewCommentType, Severity


class SupportChecker:
    """Checks draft-to-evidence alignment without calling an external verifier."""

    def check(
        self,
        *,
        section: OutlineNode,
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
        used_citations = self._citation_keys(content)
        citations_by_key = {item.citation_key: item for item in evidence_items if item.citation_key}
        citations_by_supported_key = {
            item.citation_key: item
            for item in evidence_items
            if item.citation_key and str(item.id) in draft_ids
        }
        pack_citation_keys = set(citations_by_key)
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
        unknown_citations = sorted(used_citations - pack_citation_keys)
        if unknown_citations:
            findings.append(
                self._finding(
                    ReviewCommentType.HALLUCINATION_RISK,
                    Severity.HIGH,
                    "Draft uses bracketed citation keys that are not present in the active evidence pack.",
                    "Remove unsupported citations or add matching evidence items to the active pack.",
                )
            )
        unsupported_used_citations = sorted(used_citations & (pack_citation_keys - set(citations_by_supported_key)))
        if unsupported_used_citations:
            findings.append(
                self._finding(
                    ReviewCommentType.MISSING_CITATION,
                    Severity.MEDIUM,
                    "Draft cites evidence whose IDs are not listed in supported_evidence_ids.",
                    "Add the cited evidence IDs to the draft support list or remove the citations.",
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
        for item in evidence_items:
            if item.section_id is not None and item.section_id != section.id:
                findings.append(
                    self._finding(
                        ReviewCommentType.HALLUCINATION_RISK,
                        Severity.HIGH,
                        "Active evidence pack includes an item assigned to a different section.",
                        "Move the evidence item to the correct section or remove it from this pack.",
                    )
                )
            if item.source_ref is None and not item.metadata_json.get("source_material_id"):
                findings.append(
                    self._finding(
                        ReviewCommentType.MISSING_CITATION,
                        Severity.MEDIUM,
                        "Evidence item lacks source_ref and source_material provenance.",
                        "Attach source_ref or source_material_id metadata before relying on this evidence.",
                    )
                )
        return findings

    def _citation_keys(self, content: str) -> set[str]:
        return {match.group(1).strip() for match in re.finditer(r"\[([A-Za-z0-9_.:-]+)\]", content)}

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
