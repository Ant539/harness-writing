"""Evidence citation and provenance verification."""

import re
import uuid

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import DraftUnit, EvidenceItem, EvidencePack, OutlineNode, SectionContract, SourceMaterial
from app.models.enums import ArtifactStatus, DraftKind, Severity
from app.schemas.evidence import EvidenceVerificationIssue, EvidenceVerificationResponse


class EvidenceVerificationService:
    """Builds deterministic evidence/citation provenance reports for current section drafts."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def verify_section(self, section: OutlineNode) -> EvidenceVerificationResponse:
        draft = self._current_draft(section.id)
        if draft is None:
            raise HTTPException(status_code=400, detail="Evidence verification requires a current draft.")
        contract = self._contract_for(section)
        pack = self._active_pack_for(section)
        evidence_items = self._evidence_items_for_pack(section, pack)
        issues = self._issues(
            section=section,
            contract=contract,
            pack=pack,
            evidence_items=evidence_items,
            draft=draft,
        )
        return EvidenceVerificationResponse(
            section_id=section.id,
            draft_id=draft.id,
            evidence_pack_id=pack.id,
            issue_count=len(issues),
            issues=issues,
        )

    def _issues(
        self,
        *,
        section: OutlineNode,
        contract: SectionContract,
        pack: EvidencePack,
        evidence_items: list[EvidenceItem],
        draft: DraftUnit,
    ) -> list[EvidenceVerificationIssue]:
        issues: list[EvidenceVerificationIssue] = []
        draft_ids = set(draft.supported_evidence_ids)
        pack_ids = set(pack.evidence_item_ids)
        evidence_by_id = {str(item.id): item for item in evidence_items}

        if not draft_ids:
            self._add_issue(
                issues,
                code="missing_supported_evidence",
                severity=Severity.HIGH,
                message="Draft has no supported evidence IDs.",
                suggested_action="Attach at least one active-pack evidence item to the draft.",
            )
        for item_id in sorted(draft_ids - pack_ids):
            self._add_issue(
                issues,
                code="supported_evidence_outside_active_pack",
                severity=Severity.HIGH,
                message="Draft references an evidence ID outside the active evidence pack.",
                suggested_action="Replace unsupported evidence references with IDs from the active pack.",
                evidence_id=self._uuid_or_none(item_id),
            )
        if len(draft_ids & pack_ids) < contract.required_evidence_count:
            self._add_issue(
                issues,
                code="insufficient_supported_evidence",
                severity=Severity.HIGH,
                message="Draft uses fewer evidence items than the section contract requires.",
                suggested_action="Add evidence-grounded support until the contract evidence count is met.",
            )

        used_citations = self._citation_keys(draft.content)
        pack_citations = {item.citation_key for item in evidence_items if item.citation_key}
        supported_citations = {
            item.citation_key
            for item in evidence_items
            if item.citation_key and str(item.id) in draft_ids
        }
        for citation_key in contract.required_citations:
            if citation_key and citation_key not in used_citations:
                self._add_issue(
                    issues,
                    code="required_citation_missing",
                    severity=Severity.HIGH,
                    message=f"Required citation [{citation_key}] is missing from the draft.",
                    suggested_action=f"Add citation [{citation_key}] where its evidence supports a claim.",
                    citation_key=citation_key,
                )
        for citation_key in sorted(used_citations - pack_citations):
            self._add_issue(
                issues,
                code="citation_without_active_pack_evidence",
                severity=Severity.HIGH,
                message="Draft uses a citation key that is not present in the active evidence pack.",
                suggested_action="Remove the unsupported citation or add matching evidence to the active pack.",
                citation_key=citation_key,
            )
        for citation_key in sorted(used_citations & (pack_citations - supported_citations)):
            self._add_issue(
                issues,
                code="cited_evidence_not_in_supported_ids",
                severity=Severity.MEDIUM,
                message="Draft cites evidence whose ID is not listed in supported_evidence_ids.",
                suggested_action="Add the cited evidence ID to the draft support list or remove the citation.",
                citation_key=citation_key,
            )

        for item in evidence_items:
            item_id = str(item.id)
            if item.section_id is not None and item.section_id != section.id:
                self._add_issue(
                    issues,
                    code="evidence_assigned_to_different_section",
                    severity=Severity.HIGH,
                    message="Active evidence pack includes an item assigned to a different section.",
                    suggested_action="Move the evidence item to the correct section or remove it from this pack.",
                    evidence_id=item.id,
                    citation_key=item.citation_key,
                )
            if item_id in draft_ids and item.citation_key and item.citation_key not in used_citations:
                self._add_issue(
                    issues,
                    code="supported_citation_missing_from_text",
                    severity=Severity.MEDIUM,
                    message="Draft support list includes cited evidence, but the citation is absent from text.",
                    suggested_action=f"Use [{item.citation_key}] near the claim supported by this item.",
                    evidence_id=item.id,
                    citation_key=item.citation_key,
                )
            self._check_source_provenance(issues, item)

        for item_id in sorted(pack_ids):
            if item_id not in evidence_by_id:
                self._add_issue(
                    issues,
                    code="active_pack_references_missing_evidence",
                    severity=Severity.HIGH,
                    message="Active evidence pack references a missing evidence item.",
                    suggested_action="Rebuild the evidence pack with existing evidence records.",
                    evidence_id=self._uuid_or_none(item_id),
                )
        return issues

    def _check_source_provenance(
        self,
        issues: list[EvidenceVerificationIssue],
        item: EvidenceItem,
    ) -> None:
        raw_source_id = item.metadata_json.get("source_material_id")
        if item.source_ref is None and raw_source_id is None:
            self._add_issue(
                issues,
                code="missing_source_provenance",
                severity=Severity.MEDIUM,
                message="Evidence item lacks source_ref and source_material provenance.",
                suggested_action="Attach source_ref or source_material_id metadata before relying on this evidence.",
                evidence_id=item.id,
                citation_key=item.citation_key,
            )
            return
        if raw_source_id is None:
            return
        try:
            source_id = uuid.UUID(str(raw_source_id))
        except ValueError:
            self._add_issue(
                issues,
                code="invalid_source_material_reference",
                severity=Severity.HIGH,
                message="Evidence item has an invalid source_material_id.",
                suggested_action="Replace source_material_id metadata with a valid source UUID.",
                evidence_id=item.id,
                citation_key=item.citation_key,
            )
            return
        source = self.session.get(SourceMaterial, source_id)
        if source is None:
            self._add_issue(
                issues,
                code="missing_source_material",
                severity=Severity.HIGH,
                message="Evidence item references a source material record that does not exist.",
                suggested_action="Re-extract the evidence or repair the source_material_id metadata.",
                evidence_id=item.id,
                citation_key=item.citation_key,
            )
            return
        if source.paper_id != item.paper_id:
            self._add_issue(
                issues,
                code="source_material_paper_mismatch",
                severity=Severity.HIGH,
                message="Evidence item references source material from a different paper.",
                suggested_action="Use source material from the same paper as the evidence item.",
                evidence_id=item.id,
                citation_key=item.citation_key,
            )
        if item.citation_key and source.citation_key and item.citation_key != source.citation_key:
            self._add_issue(
                issues,
                code="citation_key_source_mismatch",
                severity=Severity.MEDIUM,
                message="Evidence citation_key differs from its source material citation_key.",
                suggested_action="Align the evidence citation key with the source record or split the source.",
                evidence_id=item.id,
                citation_key=item.citation_key,
            )

    def _current_draft(self, section_id: uuid.UUID) -> DraftUnit | None:
        return self.session.exec(
            select(DraftUnit)
            .where(
                DraftUnit.section_id == section_id,
                DraftUnit.kind == DraftKind.SECTION_DRAFT,
                DraftUnit.status == ArtifactStatus.ACTIVE,
            )
            .order_by(DraftUnit.version.desc(), DraftUnit.created_at.desc())
        ).first()

    def _contract_for(self, section: OutlineNode) -> SectionContract:
        contract = self.session.exec(
            select(SectionContract).where(SectionContract.section_id == section.id)
        ).first()
        if contract is None:
            raise HTTPException(status_code=400, detail="Evidence verification requires a section contract.")
        return contract

    def _active_pack_for(self, section: OutlineNode) -> EvidencePack:
        pack = self.session.exec(
            select(EvidencePack).where(
                EvidencePack.section_id == section.id,
                EvidencePack.status == ArtifactStatus.ACTIVE,
            )
        ).first()
        if pack is None:
            raise HTTPException(status_code=400, detail="Evidence verification requires an active evidence pack.")
        return pack

    def _evidence_items_for_pack(
        self,
        section: OutlineNode,
        pack: EvidencePack,
    ) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        for item_id in pack.evidence_item_ids:
            try:
                parsed_id = uuid.UUID(item_id)
            except ValueError:
                continue
            item = self.session.get(EvidenceItem, parsed_id)
            if item is None:
                continue
            if item.paper_id != section.paper_id:
                raise HTTPException(
                    status_code=400,
                    detail="Evidence pack contains an item from a different paper.",
                )
            items.append(item)
        return items

    def _add_issue(
        self,
        issues: list[EvidenceVerificationIssue],
        *,
        code: str,
        severity: Severity,
        message: str,
        suggested_action: str,
        evidence_id: uuid.UUID | None = None,
        citation_key: str | None = None,
    ) -> None:
        issue = EvidenceVerificationIssue(
            code=code,
            severity=severity,
            message=message,
            suggested_action=suggested_action,
            evidence_id=evidence_id,
            citation_key=citation_key,
        )
        key = (issue.code, issue.evidence_id, issue.citation_key, issue.message)
        if key not in {
            (existing.code, existing.evidence_id, existing.citation_key, existing.message)
            for existing in issues
        }:
            issues.append(issue)

    def _citation_keys(self, content: str) -> set[str]:
        return {match.group(1).strip() for match in re.finditer(r"\[([A-Za-z0-9_.:-]+)\]", content)}

    def _uuid_or_none(self, value: str) -> uuid.UUID | None:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
