"""Optional bridge from generic academic runs into existing paper persistence."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import DraftUnit, EvidenceItem, EvidencePack, OutlineNode, Paper, SectionContract, SourceMaterial
from app.models.enums import EvidenceSourceType, ExportFormat, PaperStatus, PaperType
from app.schemas.assembly import ManuscriptAssemblyRequest, ManuscriptExportRequest
from app.schemas.contracts import ContractGenerationRequest
from app.schemas.drafts import DraftGenerationRequest
from app.schemas.evidence import EvidencePackBuildRequest
from app.schemas.writing_harness import AcademicBrief, Outline, SourceNote, WritingHarnessRunRequest
from app.services.assembly import AssemblyService
from app.services.crud import get_or_404
from app.services.drafting import DraftingService
from app.services.planner import ContractGenerator
from app.services.research import EvidenceExtractor, EvidencePackBuilder


class PaperHarnessBridge:
    """Persist academic artifacts into the existing `/papers/...` data model when requested."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def persist_academic_run(
        self,
        *,
        payload: WritingHarnessRunRequest,
        brief: AcademicBrief,
        outline: Outline,
        source_notes: list[SourceNote],
    ) -> dict[str, Any]:
        paper = self._resolve_or_create_paper(payload, brief)
        outline_nodes = self._persist_outline(paper.id, outline)
        sources = self._persist_sources(paper.id, source_notes)
        pipeline = self._run_optional_pipeline(
            paper=paper,
            sections=outline_nodes,
            sources=sources,
            payload=payload,
        )
        paper.updated_at = datetime.now(timezone.utc)
        self.session.add(paper)
        self.session.commit()
        return {
            "paper_id": str(paper.id),
            "paper_status": paper.status.value,
            "outline_node_ids": [str(node.id) for node in outline_nodes],
            "source_material_ids": [str(source.id) for source in sources],
            **pipeline,
            "bridge": "paper_harness_v1",
        }

    def _run_optional_pipeline(
        self,
        *,
        paper: Paper,
        sections: list[OutlineNode],
        sources: list[SourceMaterial],
        payload: WritingHarnessRunRequest,
    ) -> dict[str, Any]:
        options = payload.paper_harness_pipeline
        result: dict[str, Any] = {
            "contract_ids": [],
            "evidence_item_ids": [],
            "evidence_pack_ids": [],
            "draft_ids": [],
            "manuscript_id": None,
            "export_ids": [],
            "skipped_steps": [],
            "pipeline_errors": [],
        }
        draftable_sections = self._draftable_sections(sections)

        if options.extract_evidence:
            result["evidence_item_ids"] = [
                str(item.id) for item in self._extract_evidence(sources, result)
            ]
        elif any([options.build_evidence_packs, options.generate_section_drafts]):
            result["evidence_item_ids"] = [
                str(item.id) for item in self._existing_evidence_items(paper.id)
            ]

        if options.generate_contracts:
            result["contract_ids"] = [
                str(contract.id)
                for contract in self._generate_contracts(
                    paper=paper,
                    sections=draftable_sections,
                    force=options.force_rebuild,
                    result=result,
                )
            ]
        elif any([options.build_evidence_packs, options.generate_section_drafts]):
            result["contract_ids"] = [
                str(contract.id) for contract in self._existing_contracts(draftable_sections)
            ]

        if options.build_evidence_packs:
            result["evidence_pack_ids"] = [
                str(pack.id)
                for pack in self._build_evidence_packs(
                    sections=draftable_sections,
                    force=options.force_rebuild,
                    result=result,
                )
            ]
        elif options.generate_section_drafts:
            result["evidence_pack_ids"] = [
                str(pack.id) for pack in self._existing_evidence_packs(draftable_sections)
            ]

        if options.generate_section_drafts:
            result["draft_ids"] = [
                str(draft.id)
                for draft in self._generate_section_drafts(
                    sections=draftable_sections,
                    result=result,
                )
            ]

        if options.assemble_manuscript:
            manuscript_id = self._assemble_paper(paper, result)
            result["manuscript_id"] = str(manuscript_id) if manuscript_id is not None else None

        if options.export_formats:
            result["export_ids"] = [
                str(export_id)
                for export_id in self._export_paper(
                    paper=paper,
                    export_formats=options.export_formats,
                    result=result,
                )
            ]

        return result

    def _resolve_or_create_paper(
        self,
        payload: WritingHarnessRunRequest,
        brief: AcademicBrief,
    ) -> Paper:
        if payload.paper_id is not None:
            return get_or_404(self.session, Paper, payload.paper_id, "Paper")
        paper = Paper(
            title=brief.topic,
            paper_type=self._paper_type_for(brief.paper_type),
            target_language=brief.language,
            target_venue=brief.target_venue,
            global_style_guide={
                "created_from": "writing_harness",
                "citation_style": brief.citation_style,
                "paper_type": brief.paper_type,
            },
        )
        self.session.add(paper)
        self.session.commit()
        self.session.refresh(paper)
        return paper

    def _persist_outline(self, paper_id: uuid.UUID, outline: Outline) -> list[OutlineNode]:
        existing = list(
            self.session.exec(
                select(OutlineNode)
                .where(OutlineNode.paper_id == paper_id)
                .order_by(OutlineNode.level, OutlineNode.order_index)
            ).all()
        )
        if existing:
            return existing

        created: list[OutlineNode] = []
        for index, section in enumerate(outline.sections, start=1):
            node = OutlineNode(
                paper_id=paper_id,
                title=section.title,
                level=1,
                goal=section.section_goal,
                expected_claims=section.expected_claims,
                order_index=index,
                metadata_json={
                    "created_from": "writing_harness",
                    "outline_id": outline.outline_id,
                    "required_sources": section.required_sources,
                    "key_points": section.key_points,
                },
            )
            self.session.add(node)
            self.session.commit()
            self.session.refresh(node)
            created.append(node)
        paper = get_or_404(self.session, Paper, paper_id, "Paper")
        paper.status = PaperStatus.OUTLINE_READY
        self.session.add(paper)
        self.session.commit()
        return created

    def _persist_sources(self, paper_id: uuid.UUID, source_notes: list[SourceNote]) -> list[SourceMaterial]:
        created: list[SourceMaterial] = []
        for note in source_notes:
            source = SourceMaterial(
                paper_id=paper_id,
                source_type=EvidenceSourceType.NOTE,
                title=note.title,
                source_ref=note.url_or_doi or note.source_id,
                content=note.quoted_text or note.summary or "\n".join(note.key_points),
                citation_key=note.source_id,
                metadata_json={
                    "created_from": "writing_harness",
                    "authors": note.authors,
                    "year": note.year,
                    "venue": note.venue,
                    "reliability": note.reliability,
                    "limitations": note.limitations,
                    "citation_metadata": note.citation_metadata,
                },
            )
            self.session.add(source)
            self.session.commit()
            self.session.refresh(source)
            created.append(source)
        return created

    def _extract_evidence(
        self,
        sources: list[SourceMaterial],
        result: dict[str, Any],
    ) -> list[EvidenceItem]:
        if not sources:
            result["skipped_steps"].append("extract_evidence:no_source_material")
            return []
        extracted: list[EvidenceItem] = []
        extractor = EvidenceExtractor(self.session)
        for source in sources:
            try:
                extracted.extend(extractor.extract(source))
            except HTTPException as exc:
                result["pipeline_errors"].append(
                    {"step": "extract_evidence", "source_id": str(source.id), "detail": exc.detail}
                )
        return extracted

    def _generate_contracts(
        self,
        *,
        paper: Paper,
        sections: list[OutlineNode],
        force: bool,
        result: dict[str, Any],
    ) -> list[SectionContract]:
        if not sections:
            result["skipped_steps"].append("generate_contracts:no_draftable_sections")
            return []
        generator = ContractGenerator(self.session)
        contracts: list[SectionContract] = []
        for section in sections:
            try:
                contracts.append(
                    generator.generate(
                        paper,
                        section,
                        ContractGenerationRequest(
                            additional_constraints=(
                                "Generated from Writing Harness bridge. Keep claims evidence-grounded."
                            ),
                            force=force,
                        ),
                    )
                )
            except HTTPException as exc:
                existing = self._existing_contract(section)
                if existing is not None:
                    contracts.append(existing)
                    result["skipped_steps"].append(f"generate_contracts:existing:{section.title}")
                else:
                    result["pipeline_errors"].append(
                        {"step": "generate_contracts", "section_id": str(section.id), "detail": exc.detail}
                    )
        return contracts

    def _build_evidence_packs(
        self,
        *,
        sections: list[OutlineNode],
        force: bool,
        result: dict[str, Any],
    ) -> list[EvidencePack]:
        if not self._existing_evidence_items_for_sections(sections):
            result["skipped_steps"].append("build_evidence_packs:no_evidence_items")
            return []
        builder = EvidencePackBuilder(self.session)
        packs: list[EvidencePack] = []
        for section in sections:
            try:
                packs.append(
                    builder.build(
                        section,
                        EvidencePackBuildRequest(
                            notes="Built from Writing Harness bridge.",
                            force=force,
                        ),
                    )
                )
            except HTTPException as exc:
                existing = self._existing_evidence_pack(section)
                if existing is not None:
                    packs.append(existing)
                    result["skipped_steps"].append(f"build_evidence_packs:existing:{section.title}")
                else:
                    result["pipeline_errors"].append(
                        {"step": "build_evidence_packs", "section_id": str(section.id), "detail": exc.detail}
                    )
        return packs

    def _generate_section_drafts(
        self,
        *,
        sections: list[OutlineNode],
        result: dict[str, Any],
    ) -> list[DraftUnit]:
        drafting = DraftingService(self.session)
        drafts: list[DraftUnit] = []
        for section in sections:
            try:
                drafts.append(
                    drafting.generate_section_draft(
                        section,
                        DraftGenerationRequest(
                            drafting_instructions="Generated through the Writing Harness bridge."
                        ),
                    )
                )
            except HTTPException as exc:
                existing = drafting.current_draft(section.id)
                if existing is not None:
                    drafts.append(existing)
                    result["skipped_steps"].append(f"generate_section_drafts:existing:{section.title}")
                else:
                    result["pipeline_errors"].append(
                        {"step": "generate_section_drafts", "section_id": str(section.id), "detail": exc.detail}
                    )
        return drafts

    def _assemble_paper(self, paper: Paper, result: dict[str, Any]) -> uuid.UUID | None:
        try:
            manuscript = AssemblyService(self.session).assemble_paper(
                paper,
                ManuscriptAssemblyRequest(include_unlocked=True),
            )
            return manuscript.id
        except HTTPException as exc:
            result["pipeline_errors"].append({"step": "assemble_manuscript", "detail": exc.detail})
            return None

    def _export_paper(
        self,
        *,
        paper: Paper,
        export_formats: list[ExportFormat],
        result: dict[str, Any],
    ) -> list[uuid.UUID]:
        exported: list[uuid.UUID] = []
        assembly = AssemblyService(self.session)
        for export_format in export_formats:
            try:
                _, export = assembly.export_current_manuscript(
                    paper,
                    ManuscriptExportRequest(export_format=export_format, write_file=False),
                )
                exported.append(export.id)
            except HTTPException as exc:
                result["pipeline_errors"].append(
                    {"step": "export", "format": export_format.value, "detail": exc.detail}
                )
        return exported

    def _draftable_sections(self, sections: list[OutlineNode]) -> list[OutlineNode]:
        excluded = {"title", "references"}
        return [section for section in sections if section.title.strip().lower() not in excluded]

    def _existing_contract(self, section: OutlineNode) -> SectionContract | None:
        return self.session.exec(
            select(SectionContract).where(SectionContract.section_id == section.id)
        ).first()

    def _existing_contracts(self, sections: list[OutlineNode]) -> list[SectionContract]:
        contracts = []
        for section in sections:
            contract = self._existing_contract(section)
            if contract is not None:
                contracts.append(contract)
        return contracts

    def _existing_evidence_items(self, paper_id: uuid.UUID) -> list[EvidenceItem]:
        return list(
            self.session.exec(
                select(EvidenceItem).where(EvidenceItem.paper_id == paper_id).order_by(EvidenceItem.created_at)
            ).all()
        )

    def _existing_evidence_items_for_sections(self, sections: list[OutlineNode]) -> list[EvidenceItem]:
        paper_ids = {section.paper_id for section in sections}
        items: list[EvidenceItem] = []
        for paper_id in paper_ids:
            items.extend(self._existing_evidence_items(paper_id))
        return items

    def _existing_evidence_pack(self, section: OutlineNode) -> EvidencePack | None:
        return self.session.exec(
            select(EvidencePack).where(EvidencePack.section_id == section.id)
        ).first()

    def _existing_evidence_packs(self, sections: list[OutlineNode]) -> list[EvidencePack]:
        packs = []
        for section in sections:
            pack = self._existing_evidence_pack(section)
            if pack is not None:
                packs.append(pack)
        return packs

    def _paper_type_for(self, paper_type: str) -> PaperType:
        normalized = paper_type.lower()
        if normalized == "survey":
            return PaperType.SURVEY
        if normalized == "empirical paper":
            return PaperType.EMPIRICAL
        return PaperType.CONCEPTUAL
