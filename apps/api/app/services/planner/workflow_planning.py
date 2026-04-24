"""Discovery persistence and workflow planning."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import false
from sqlmodel import Session, select

from app.models import (
    DiscoveryRecord,
    DraftUnit,
    EvidenceItem,
    OutlineNode,
    Paper,
    PlanningRun,
    ReviewComment,
    SourceMaterial,
)
from app.models.enums import (
    ArtifactStatus,
    DocumentMaturity,
    DocumentType,
    PlanningMode,
    SectionAction,
    SourceMode,
)
from app.schemas.planning import (
    DiscoveryCreate,
    DiscoveryRead,
    EntryStrategy,
    PaperPlan,
    PlanningOutput,
    PlanningRunCreate,
    PlanningRunRead,
    PromptAssemblyHints,
    SectionPlan,
    TaskProfile,
)
from app.services.crud import get_or_404
from app.services.llm import LLMMessage, LLMProvider, LLMRequest, get_llm_provider
from app.services.llm.json_utils import parse_json_object
from app.services.llm.providers import LLMProviderError


@dataclass(frozen=True)
class PlanningContext:
    paper: Paper
    discovery: DiscoveryRecord | None
    sections: list[OutlineNode]
    sources: list[SourceMaterial]
    evidence_items: list[EvidenceItem]
    drafts: list[DraftUnit]
    review_comments: list[ReviewComment]
    additional_context: str | None = None


class WorkflowPlanningService:
    """Persist discovery records and generate structured workflow plans."""

    def __init__(self, session: Session, llm_provider: LLMProvider | None = None) -> None:
        self.session = session
        self.llm_provider = llm_provider if llm_provider is not None else get_llm_provider()

    def get_latest_discovery(self, paper_id: uuid.UUID) -> DiscoveryRecord | None:
        get_or_404(self.session, Paper, paper_id, "Paper")
        return self.session.exec(
            select(DiscoveryRecord)
            .where(DiscoveryRecord.paper_id == paper_id)
            .order_by(DiscoveryRecord.created_at.desc())
        ).first()

    def discovery_read(self, discovery: DiscoveryRecord) -> DiscoveryRead:
        return DiscoveryRead(
            id=discovery.id,
            paper_id=discovery.paper_id,
            document_type=discovery.document_type,
            user_goal=discovery.user_goal,
            audience=discovery.audience,
            success_criteria=discovery.success_criteria,
            constraints=discovery.constraints,
            available_source_materials=discovery.available_source_materials,
            current_document_state=discovery.current_document_state,
            clarifying_questions=discovery.clarifying_questions,
            assumptions=discovery.assumptions,
            notes=discovery.notes,
            metadata=discovery.metadata_json,
            status=discovery.status,
            created_at=discovery.created_at,
            updated_at=discovery.updated_at,
        )

    def save_discovery(self, paper_id: uuid.UUID, payload: DiscoveryCreate) -> DiscoveryRecord:
        paper = get_or_404(self.session, Paper, paper_id, "Paper")
        now = datetime.now(timezone.utc)
        self._supersede_active_discovery_records(paper_id, now)

        discovery = DiscoveryRecord(
            paper_id=paper_id,
            document_type=self._normalize_document_type(payload.document_type, paper),
            user_goal=self._clean_text(payload.user_goal),
            audience=self._clean_text(payload.audience),
            success_criteria=self._clean_string_list(payload.success_criteria),
            constraints=self._clean_string_list(payload.constraints),
            available_source_materials=self._clean_string_list(payload.available_source_materials),
            current_document_state=self._clean_text(payload.current_document_state),
            clarifying_questions=self._clean_string_list(payload.clarifying_questions),
            assumptions=self._clean_string_list(payload.assumptions),
            notes=self._clean_text(payload.notes),
            metadata_json=dict(payload.metadata),
            updated_at=now,
        )
        self.session.add(discovery)
        paper.updated_at = now
        self.session.add(paper)
        self.session.commit()
        self.session.refresh(discovery)
        return discovery

    def get_latest_plan(self, paper_id: uuid.UUID) -> PlanningRun | None:
        get_or_404(self.session, Paper, paper_id, "Paper")
        return self.session.exec(
            select(PlanningRun)
            .where(PlanningRun.paper_id == paper_id)
            .order_by(PlanningRun.created_at.desc())
        ).first()

    def planning_run_read(self, plan: PlanningRun) -> PlanningRunRead:
        return PlanningRunRead(
            id=plan.id,
            paper_id=plan.paper_id,
            discovery_id=plan.discovery_id,
            planner_mode=plan.planner_mode,
            status=plan.status,
            task_profile=TaskProfile.model_validate(plan.task_profile_json),
            entry_strategy=EntryStrategy.model_validate(plan.entry_strategy_json),
            paper_plan=PaperPlan.model_validate(plan.paper_plan_json),
            section_plans=[SectionPlan.model_validate(item) for item in plan.section_plans_json],
            prompt_assembly_hints=PromptAssemblyHints.model_validate(plan.prompt_assembly_hints_json),
            metadata=plan.metadata_json,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )

    def generate_plan(self, paper_id: uuid.UUID, payload: PlanningRunCreate) -> PlanningRun:
        paper = get_or_404(self.session, Paper, paper_id, "Paper")
        discovery = self._resolve_discovery(paper_id, payload.discovery_id)
        context = self._build_context(paper, discovery, payload.additional_context)

        output: PlanningOutput
        planner_mode = PlanningMode.DETERMINISTIC
        metadata: dict[str, Any] = {}
        if self.llm_provider is not None and not payload.force_deterministic:
            try:
                output = self._model_backed_plan(context)
                planner_mode = PlanningMode.MODEL
                metadata = {
                    "provider": self.llm_provider.provider_name,
                    "path": "model",
                }
            except (LLMProviderError, ValueError, TypeError) as exc:
                output = self._deterministic_plan(context)
                planner_mode = PlanningMode.FALLBACK
                metadata = {
                    "provider": self.llm_provider.provider_name,
                    "path": "fallback",
                    "fallback_reason": str(exc),
                }
        else:
            output = self._deterministic_plan(context)
            metadata = {"path": "deterministic"}

        now = datetime.now(timezone.utc)
        self._supersede_active_plans(paper_id, now)
        plan = PlanningRun(
            paper_id=paper_id,
            discovery_id=discovery.id if discovery is not None else None,
            planner_mode=planner_mode,
            task_profile_json=output.task_profile.model_dump(mode="json"),
            entry_strategy_json=output.entry_strategy.model_dump(mode="json"),
            paper_plan_json=output.paper_plan.model_dump(mode="json"),
            section_plans_json=[item.model_dump(mode="json") for item in output.section_plans],
            prompt_assembly_hints_json=output.prompt_assembly_hints.model_dump(mode="json"),
            metadata_json=metadata,
            updated_at=now,
        )
        self.session.add(plan)
        paper.updated_at = now
        self.session.add(paper)
        self.session.commit()
        self.session.refresh(plan)
        return plan

    def _resolve_discovery(
        self,
        paper_id: uuid.UUID,
        discovery_id: uuid.UUID | None,
    ) -> DiscoveryRecord | None:
        if discovery_id is None:
            return self.get_latest_discovery(paper_id)

        discovery = get_or_404(self.session, DiscoveryRecord, discovery_id, "Discovery record")
        if discovery.paper_id != paper_id:
            raise HTTPException(status_code=400, detail="Discovery record does not belong to paper.")
        return discovery

    def _build_context(
        self,
        paper: Paper,
        discovery: DiscoveryRecord | None,
        additional_context: str | None,
    ) -> PlanningContext:
        sections = list(
            self.session.exec(
                select(OutlineNode)
                .where(OutlineNode.paper_id == paper.id)
                .order_by(OutlineNode.level, OutlineNode.order_index)
            ).all()
        )
        sources = list(
            self.session.exec(
                select(SourceMaterial)
                .where(SourceMaterial.paper_id == paper.id)
                .order_by(SourceMaterial.created_at)
            ).all()
        )
        evidence_items = list(
            self.session.exec(
                select(EvidenceItem)
                .where(EvidenceItem.paper_id == paper.id)
                .order_by(EvidenceItem.created_at)
            ).all()
        )
        section_ids = [section.id for section in sections]
        drafts = list(
            self.session.exec(
                select(DraftUnit)
                .where(DraftUnit.section_id.in_(section_ids) if section_ids else false())
                .order_by(DraftUnit.created_at)
            ).all()
        )
        draft_ids = [draft.id for draft in drafts]
        review_comments = list(
            self.session.exec(
                select(ReviewComment)
                .where(ReviewComment.target_draft_id.in_(draft_ids) if draft_ids else false())
                .order_by(ReviewComment.created_at)
            ).all()
        )
        return PlanningContext(
            paper=paper,
            discovery=discovery,
            sections=sections,
            sources=sources,
            evidence_items=evidence_items,
            drafts=drafts,
            review_comments=review_comments,
            additional_context=self._clean_text(additional_context),
        )

    def _deterministic_plan(self, context: PlanningContext) -> PlanningOutput:
        task_profile = self._task_profile(context)
        entry_strategy = self._entry_strategy(context)
        paper_plan = self._paper_plan(context, task_profile, entry_strategy)
        section_plans = self._section_plans(context, entry_strategy)
        prompt_hints = self._prompt_assembly_hints(task_profile, paper_plan, entry_strategy)
        return PlanningOutput(
            task_profile=task_profile,
            entry_strategy=entry_strategy,
            paper_plan=paper_plan,
            section_plans=section_plans,
            prompt_assembly_hints=prompt_hints,
        )

    def _model_backed_plan(self, context: PlanningContext) -> PlanningOutput:
        foundation_prompt = self._load_prompt("foundation.md")
        planner_prompt = self._load_prompt("planner.md")
        system = f"{foundation_prompt}\n\n{planner_prompt}"
        user = (
            "Build a structured workflow plan for the following paper context.\n\n"
            f"{json.dumps(self._planning_context_payload(context), ensure_ascii=True, indent=2)}\n\n"
            "Return JSON with exactly these top-level fields:\n"
            "- task_profile\n"
            "- entry_strategy\n"
            "- paper_plan\n"
            "- section_plans\n"
            "- prompt_assembly_hints\n"
            "Keep values conservative and avoid inventing source support."
        )
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
        return PlanningOutput.model_validate(payload)

    def _planning_context_payload(self, context: PlanningContext) -> dict[str, Any]:
        discovery = context.discovery
        return {
            "paper": {
                "id": str(context.paper.id),
                "title": context.paper.title,
                "paper_type": context.paper.paper_type.value,
                "target_language": context.paper.target_language,
                "target_venue": context.paper.target_venue,
                "status": context.paper.status.value,
            },
            "discovery": (
                self.discovery_read(discovery).model_dump(mode="json")
                if discovery is not None
                else None
            ),
            "sections": [
                {
                    "id": str(section.id),
                    "title": section.title,
                    "goal": section.goal,
                    "expected_claims": section.expected_claims,
                    "status": section.status.value,
                    "word_budget": section.word_budget,
                    "level": section.level,
                }
                for section in context.sections
            ],
            "counts": {
                "sources": len(context.sources),
                "evidence_items": len(context.evidence_items),
                "drafts": len(context.drafts),
                "review_comments": len(context.review_comments),
            },
            "additional_context": context.additional_context,
        }

    def _task_profile(self, context: PlanningContext) -> TaskProfile:
        document_type = self._document_type_for_context(context)
        audience = (
            self._clean_text(context.discovery.audience) if context.discovery is not None else None
        ) or context.paper.target_venue or "General academic or technical reader"
        success_criteria = (
            self._clean_string_list(context.discovery.success_criteria)
            if context.discovery is not None
            else []
        )
        if not success_criteria:
            success_criteria = [
                "Align the document with the user's stated writing objective.",
                "Keep claims grounded in available source material.",
                "Produce a workflow plan that can drive section-level execution.",
            ]

        constraints = []
        if context.paper.target_language:
            constraints.append(f"Target language: {context.paper.target_language}.")
        if context.paper.target_venue:
            constraints.append(f"Target venue/context: {context.paper.target_venue}.")
        if context.discovery is not None:
            constraints.extend(self._clean_string_list(context.discovery.constraints))

        return TaskProfile(
            document_type=document_type,
            audience=audience,
            success_criteria=self._unique_list(success_criteria),
            constraints=self._unique_list(constraints),
        )

    def _entry_strategy(self, context: PlanningContext) -> EntryStrategy:
        section_count = len(context.sections)
        active_drafts = [draft for draft in context.drafts if draft.status == ArtifactStatus.ACTIVE]
        active_draft_count = len(active_drafts)
        unresolved_reviews = [comment for comment in context.review_comments if not comment.resolved]

        if unresolved_reviews and active_draft_count:
            current_maturity = DocumentMaturity.REVISION_CYCLE
        elif active_draft_count and section_count and active_draft_count >= section_count:
            current_maturity = DocumentMaturity.FULL_DRAFT
        elif active_draft_count:
            current_maturity = DocumentMaturity.PARTIAL_DRAFT
        elif context.sections:
            current_maturity = DocumentMaturity.OUTLINE
        else:
            current_maturity = DocumentMaturity.IDEA

        if active_draft_count and section_count and 0 < active_draft_count < section_count:
            source_mode = SourceMode.MIXED
        elif active_draft_count:
            source_mode = SourceMode.EXISTING_DRAFT
        elif current_maturity in {DocumentMaturity.IDEA, DocumentMaturity.OUTLINE}:
            source_mode = SourceMode.NEW_PAPER
        else:
            source_mode = SourceMode.UNKNOWN

        rationale_bits = []
        if context.discovery is not None and context.discovery.current_document_state:
            rationale_bits.append(context.discovery.current_document_state.strip())
        if active_draft_count:
            rationale_bits.append(
                f"{active_draft_count} section draft(s) already exist for {section_count or active_draft_count} section(s)."
            )
        elif section_count:
            rationale_bits.append(f"The paper already has an outline with {section_count} section(s).")
        else:
            rationale_bits.append("No outline or draft exists yet, so the workflow should begin from the goal.")
        if unresolved_reviews:
            rationale_bits.append(
                f"{len(unresolved_reviews)} unresolved review comment(s) indicate an active revision loop."
            )

        return EntryStrategy(
            source_mode=source_mode,
            current_maturity=current_maturity,
            rationale=" ".join(rationale_bits),
        )

    def _paper_plan(
        self,
        context: PlanningContext,
        task_profile: TaskProfile,
        entry_strategy: EntryStrategy,
    ) -> PaperPlan:
        objective = (
            f"Prepare '{context.paper.title}' for execution as a {task_profile.document_type.value} "
            "by clarifying the goal, choosing a safe entry path, and sequencing section work."
        )
        risks: list[str] = []
        if context.discovery is None:
            risks.append("The user goal has not been persisted through a discovery record yet.")
        if not context.sources and not context.evidence_items:
            risks.append("Available source material is thin, so drafting must stay conservative.")
        if not context.sections:
            risks.append("No outline exists yet, so section-level execution cannot start.")
        if entry_strategy.current_maturity == DocumentMaturity.REVISION_CYCLE:
            risks.append("Unresolved review comments indicate the draft needs repair before assembly.")
        if not task_profile.constraints:
            risks.append("Format and venue constraints are still underspecified.")

        workflow_steps = ["discover", "plan", "assemble_prompts"]
        if not context.sections:
            workflow_steps.append("outline_or_outline_reconciliation")
        workflow_steps.append("contract_generation_or_update")
        if not context.sources and not context.evidence_items:
            workflow_steps.append("evidence_gathering_or_alignment")
        workflow_steps.extend(
            [
                "section_write_or_revision",
                "section_review",
                "section_revision_loop",
            ]
        )

        return PaperPlan(
            objective=objective,
            global_risks=self._unique_list(risks),
            workflow_steps=self._unique_list(workflow_steps),
        )

    def _section_plans(
        self,
        context: PlanningContext,
        entry_strategy: EntryStrategy,
    ) -> list[SectionPlan]:
        if not context.sections:
            return []

        drafts_by_section: dict[uuid.UUID, list[DraftUnit]] = {}
        for draft in context.drafts:
            drafts_by_section.setdefault(draft.section_id, []).append(draft)
        evidence_section_ids = {
            item.section_id for item in context.evidence_items if item.section_id is not None
        }
        total_support = len(context.sources) + len(context.evidence_items)
        plans: list[SectionPlan] = []
        for section in context.sections:
            section_drafts = drafts_by_section.get(section.id, [])
            unresolved_section_reviews = self._unresolved_section_reviews(section_drafts, context)
            has_section_evidence = section.id in evidence_section_ids

            if section_drafts:
                action = SectionAction.REPAIR if unresolved_section_reviews else SectionAction.PRESERVE
                reason = (
                    "A section draft exists but unresolved review comments still need to be addressed."
                    if unresolved_section_reviews
                    else "A usable section draft already exists and should be preserved unless later checks fail."
                )
            elif total_support or section.goal or section.expected_claims:
                action = (
                    SectionAction.DRAFT
                    if entry_strategy.source_mode != SourceMode.EXISTING_DRAFT
                    else SectionAction.REWRITE
                )
                reason = (
                    "No usable section draft exists yet, but the current outline and source context are enough "
                    "to draft this unit conservatively."
                )
            else:
                action = SectionAction.BLOCKED
                reason = "The section lacks draft text, outline intent, and supporting material."

            plans.append(
                SectionPlan(
                    section_id=section.id,
                    section_title=section.title,
                    action=action,
                    reason=reason,
                    needs_evidence=not has_section_evidence,
                    needs_review_loop=action
                    in {
                        SectionAction.DRAFT,
                        SectionAction.REWRITE,
                        SectionAction.REPAIR,
                        SectionAction.POLISH,
                    },
                )
            )
        return plans

    def _prompt_assembly_hints(
        self,
        task_profile: TaskProfile,
        paper_plan: PaperPlan,
        entry_strategy: EntryStrategy,
    ) -> PromptAssemblyHints:
        modules = [
            "product_mission",
            "use_case_framing",
            "task_profile",
            "source_mode",
            "stage_instructions",
            "safety_and_non_invention_rules",
            "output_schema",
        ]
        if paper_plan.global_risks:
            modules.append("verification_emphasis")
        style_profile = (
            "default_academic"
            if task_profile.document_type == DocumentType.ACADEMIC_PAPER
            else "default_structured"
        )
        risk_emphasis = list(paper_plan.global_risks)
        if entry_strategy.source_mode == SourceMode.MIXED:
            risk_emphasis.append("Mixed source mode requires preserving strong existing material.")
        return PromptAssemblyHints(
            required_prompt_modules=self._unique_list(modules),
            style_profile=style_profile,
            risk_emphasis=self._unique_list(risk_emphasis),
        )

    def _document_type_for_context(self, context: PlanningContext) -> DocumentType:
        if context.discovery is not None:
            normalized = self._normalize_document_type(context.discovery.document_type, context.paper)
            if normalized != DocumentType.UNKNOWN:
                return normalized
        return self._paper_document_type(context.paper)

    def _normalize_document_type(self, document_type: DocumentType, paper: Paper) -> DocumentType:
        if document_type != DocumentType.UNKNOWN:
            return document_type
        return self._paper_document_type(paper)

    def _paper_document_type(self, _: Paper) -> DocumentType:
        return DocumentType.ACADEMIC_PAPER

    def _unresolved_section_reviews(
        self,
        section_drafts: list[DraftUnit],
        context: PlanningContext,
    ) -> list[ReviewComment]:
        draft_ids = {draft.id for draft in section_drafts}
        return [
            comment
            for comment in context.review_comments
            if comment.target_draft_id in draft_ids and not comment.resolved
        ]

    def _supersede_active_discovery_records(self, paper_id: uuid.UUID, now: datetime) -> None:
        active_records = self.session.exec(
            select(DiscoveryRecord).where(
                DiscoveryRecord.paper_id == paper_id,
                DiscoveryRecord.status == ArtifactStatus.ACTIVE,
            )
        ).all()
        for record in active_records:
            record.status = ArtifactStatus.SUPERSEDED
            record.updated_at = now
            self.session.add(record)

    def _supersede_active_plans(self, paper_id: uuid.UUID, now: datetime) -> None:
        active_plans = self.session.exec(
            select(PlanningRun).where(
                PlanningRun.paper_id == paper_id,
                PlanningRun.status == ArtifactStatus.ACTIVE,
            )
        ).all()
        for plan in active_plans:
            plan.status = ArtifactStatus.SUPERSEDED
            plan.updated_at = now
            self.session.add(plan)

    def _load_prompt(self, filename: str) -> str:
        prompt_path = self._repo_root() / "configs" / "prompts" / filename
        return prompt_path.read_text(encoding="utf-8").strip()

    def _repo_root(self) -> Path:
        for parent in Path(__file__).resolve().parents:
            if (parent / "configs" / "prompts").exists():
                return parent
        raise RuntimeError("Unable to locate repository root for prompt loading.")

    def _clean_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    def _clean_string_list(self, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            if not isinstance(value, str):
                continue
            stripped = value.strip()
            if stripped:
                cleaned.append(stripped)
        return cleaned

    def _unique_list(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                ordered.append(value)
        return ordered
