"""Citation and claim-evidence checker role for Writing Harness."""

from app.schemas.writing_harness import ClaimEvidenceMap, Draft, SourceNote


class CitationChecker:
    """Return conservative citation and claim-evidence warnings."""

    def citation_warnings(self, draft: Draft | None, source_notes: list[SourceNote]) -> list[str]:
        if draft is None:
            return []
        if not source_notes:
            return ["Citation check: no verified source notes are available; references remain TODOs."]
        return ["Source metadata is user-provided and still needs verification before final citation rendering."]

    def claim_evidence_warnings(self, claim_map: ClaimEvidenceMap | None) -> list[str]:
        if claim_map is None:
            return []
        unsupported = [claim.claim_id for claim in claim_map.claims if claim.unsupported_risk == "high"]
        if unsupported:
            return [
                f"Claim-evidence check: unsupported claim(s) require validation: {', '.join(unsupported)}."
            ]
        return []

    def academic_source_warnings(self, source_notes: list[SourceNote]) -> list[str]:
        if source_notes:
            return ["Source metadata is user-provided and still needs verification before final citation rendering."]
        return [
            "No source notes were provided; the academic draft must keep citations and literature claims as TODOs.",
            "No experiments, datasets, benchmarks, or results may be invented.",
        ]
