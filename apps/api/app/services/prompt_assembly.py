"""Prompt assembly foundations."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    DiscoveryRecord,
    OutlineNode,
    Paper,
    PlanningRun,
    PromptAssemblyArtifact,
    StyleGuide,
)
from app.models.enums import ArtifactStatus, DocumentType, PromptStage
from app.schemas.planning import PlanningRunRead, SectionPlan
from app.schemas.prompts import PromptAssemblyRead, PromptAssemblyRequest, PromptModuleRead
from app.services.crud import get_or_404
from app.services.planner import WorkflowPlanningService
from app.services.prompt_logging import PromptLoggingService


class PromptAssemblyService:
    """Compose prompt modules from planning output and persist assembled artifacts."""

    PROMPT_PACK_FILE = "v1.json"

    STAGE_FILES = {
        PromptStage.PLANNER: "planner.md",
        PromptStage.WRITER: "writer.md",
        PromptStage.REVIEWER: "reviewer.md",
        PromptStage.REVISER: "reviser.md",
        PromptStage.VERIFIER: "verifier.md",
        PromptStage.EDITOR: "editor.md",
    }

    def __init__(self, session: Session) -> None:
        self.session = session
        self.planning_service = WorkflowPlanningService(session)
        self.prompt_logging_service = PromptLoggingService(session)

    def assemble(self, paper_id: uuid.UUID, payload: PromptAssemblyRequest) -> PromptAssemblyArtifact:
        paper = get_or_404(self.session, Paper, paper_id, "Paper")
        plan = self._resolve_plan(paper_id, payload.planning_run_id)
        plan_read = self.planning_service.planning_run_read(plan)
        discovery = self._resolve_discovery(paper_id, plan.discovery_id)
        section = self._resolve_section(paper_id, payload.section_id)
        style_guide = self._style_guide_for_paper(paper_id)

        modules = self._assembled_modules(
            paper=paper,
            plan=plan_read,
            discovery=discovery,
            stage=payload.stage,
            style_guide=style_guide,
            section=section,
        )
        system_prompt = "\n\n".join(module.content for module in modules)
        user_prompt = self._user_prompt(
            paper=paper,
            plan=plan_read,
            discovery=discovery,
            stage=payload.stage,
            section=section,
            additional_instructions=payload.additional_instructions,
        )

        self._supersede_active_artifacts(
            paper_id=paper_id,
            stage=payload.stage,
            section_id=payload.section_id,
        )
        artifact = PromptAssemblyArtifact(
            paper_id=paper_id,
            planning_run_id=plan.id,
            workflow_run_id=payload.workflow_run_id,
            section_id=payload.section_id,
            stage=payload.stage,
            version=self._next_version(paper_id, payload.stage, payload.section_id),
            module_keys=[module.key for module in modules],
            modules_json=[module.model_dump(mode="json") for module in modules],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_hash=self.prompt_logging_service.prompt_hash(system_prompt, user_prompt),
            prompt_pack_version=self._prompt_pack_version(),
            metadata_json={
                "style_profile": plan.prompt_assembly_hints_json.get("style_profile"),
                "document_type": plan.task_profile_json.get("document_type"),
                "source_mode": plan.entry_strategy_json.get("source_mode"),
                "prompt_pack": self._prompt_pack_metadata(payload.stage),
            },
        )
        self.session.add(artifact)
        self.session.commit()
        self.session.refresh(artifact)
        self.prompt_logging_service.create_log(
            paper_id=paper_id,
            planning_run_id=plan.id,
            workflow_run_id=payload.workflow_run_id,
            prompt_assembly_id=artifact.id,
            section_id=payload.section_id,
            stage=payload.stage,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_version=artifact.version,
            prompt_pack_version=artifact.prompt_pack_version,
            module_keys=artifact.module_keys,
            request_metadata={
                "event": "prompt_assembly",
                "additional_instructions": bool(payload.additional_instructions),
            },
        )
        return artifact

    def get_artifact(self, artifact_id: uuid.UUID) -> PromptAssemblyArtifact:
        return get_or_404(self.session, PromptAssemblyArtifact, artifact_id, "Prompt assembly artifact")

    def list_artifacts(
        self,
        paper_id: uuid.UUID,
        *,
        stage: PromptStage | None = None,
    ) -> list[PromptAssemblyArtifact]:
        get_or_404(self.session, Paper, paper_id, "Paper")
        query = select(PromptAssemblyArtifact).where(PromptAssemblyArtifact.paper_id == paper_id)
        if stage is not None:
            query = query.where(PromptAssemblyArtifact.stage == stage)
        return list(
            self.session.exec(query.order_by(PromptAssemblyArtifact.created_at.desc())).all()
        )

    def prompt_assembly_read(self, artifact: PromptAssemblyArtifact) -> PromptAssemblyRead:
        return PromptAssemblyRead(
            id=artifact.id,
            paper_id=artifact.paper_id,
            planning_run_id=artifact.planning_run_id,
            workflow_run_id=artifact.workflow_run_id,
            section_id=artifact.section_id,
            stage=artifact.stage,
            version=artifact.version,
            module_keys=artifact.module_keys,
            modules=[PromptModuleRead.model_validate(item) for item in artifact.modules_json],
            system_prompt=artifact.system_prompt,
            user_prompt=artifact.user_prompt,
            prompt_hash=artifact.prompt_hash,
            prompt_pack_version=artifact.prompt_pack_version,
            status=artifact.status,
            metadata=artifact.metadata_json,
            created_at=artifact.created_at,
        )

    def _resolve_plan(self, paper_id: uuid.UUID, planning_run_id: uuid.UUID | None) -> PlanningRun:
        if planning_run_id is None:
            plan = self.planning_service.get_latest_plan(paper_id)
            if plan is None:
                raise HTTPException(status_code=400, detail="Prompt assembly requires a planning run.")
            return plan
        plan = get_or_404(self.session, PlanningRun, planning_run_id, "Planning run")
        if plan.paper_id != paper_id:
            raise HTTPException(status_code=400, detail="Planning run does not belong to this paper.")
        return plan

    def _resolve_discovery(self, paper_id: uuid.UUID, discovery_id: uuid.UUID | None) -> DiscoveryRecord | None:
        if discovery_id is not None:
            discovery = get_or_404(self.session, DiscoveryRecord, discovery_id, "Discovery record")
            if discovery.paper_id != paper_id:
                raise HTTPException(status_code=400, detail="Discovery record does not belong to this paper.")
            return discovery
        return self.planning_service.get_latest_discovery(paper_id)

    def _resolve_section(self, paper_id: uuid.UUID, section_id: uuid.UUID | None) -> OutlineNode | None:
        if section_id is None:
            return None
        section = get_or_404(self.session, OutlineNode, section_id, "Section")
        if section.paper_id != paper_id:
            raise HTTPException(status_code=400, detail="Section does not belong to this paper.")
        return section

    def _style_guide_for_paper(self, paper_id: uuid.UUID) -> StyleGuide | None:
        return self.session.exec(select(StyleGuide).where(StyleGuide.paper_id == paper_id)).first()

    def _assembled_modules(
        self,
        *,
        paper: Paper,
        plan: PlanningRunRead,
        discovery: DiscoveryRecord | None,
        stage: PromptStage,
        style_guide: StyleGuide | None,
        section: OutlineNode | None,
    ) -> list[PromptModuleRead]:
        required = self._required_module_keys(plan.prompt_assembly_hints.required_prompt_modules)
        modules: list[PromptModuleRead] = []
        for key in required:
            module = self._module_for_key(
                key=key,
                paper=paper,
                plan=plan,
                discovery=discovery,
                stage=stage,
                style_guide=style_guide,
                section=section,
            )
            if module is not None:
                modules.append(module)
        return modules

    def _module_for_key(
        self,
        *,
        key: str,
        paper: Paper,
        plan: PlanningRunRead,
        discovery: DiscoveryRecord | None,
        stage: PromptStage,
        style_guide: StyleGuide | None,
        section: OutlineNode | None,
    ) -> PromptModuleRead | None:
        if key == "product_mission":
            return PromptModuleRead(
                key=key,
                title="Product Mission",
                content=self._load_prompt("foundation.md"),
                source="configs/prompts/foundation.md",
            )
        if key == "use_case_framing":
            return PromptModuleRead(
                key=key,
                title="Use Case Framing",
                content=self._use_case_framing(plan.task_profile.document_type),
            )
        if key == "task_profile":
            return PromptModuleRead(
                key=key,
                title="Task Profile",
                content=self._task_profile_module(paper, plan, discovery),
            )
        if key == "source_mode":
            return PromptModuleRead(
                key=key,
                title="Source Mode",
                content=self._source_mode_module(plan),
            )
        if key == "stage_instructions":
            filename = self.STAGE_FILES[stage]
            return PromptModuleRead(
                key=key,
                title="Stage Instructions",
                content=self._load_prompt(filename),
                source=f"configs/prompts/{filename}",
            )
        if key == "stage_prompt_pack":
            return self._stage_prompt_pack_module(stage)
        if key == "style_guidance":
            return PromptModuleRead(
                key=key,
                title="Style Guidance",
                content=self._style_guidance_module(plan, style_guide),
            )
        if key == "safety_and_non_invention_rules":
            return PromptModuleRead(
                key=key,
                title="Safety And Non-Invention Rules",
                content=self._safety_module(plan, discovery, section),
            )
        if key == "output_schema":
            return PromptModuleRead(
                key=key,
                title="Output Schema",
                content=self._output_schema_module(stage, section),
            )
        if key == "verification_emphasis":
            return PromptModuleRead(
                key=key,
                title="Verification Emphasis",
                content=self._verification_module(plan),
            )
        return None

    def _required_module_keys(self, requested: list[str]) -> list[str]:
        keys = list(requested)
        if "stage_prompt_pack" in keys:
            return keys
        try:
            index = keys.index("stage_instructions") + 1
        except ValueError:
            index = len(keys)
        keys.insert(index, "stage_prompt_pack")
        return keys

    def _user_prompt(
        self,
        *,
        paper: Paper,
        plan: PlanningRunRead,
        discovery: DiscoveryRecord | None,
        stage: PromptStage,
        section: OutlineNode | None,
        additional_instructions: str | None,
    ) -> str:
        section_context = self._section_context(plan.section_plans, section)
        discovery_note = discovery.notes if discovery is not None else "No explicit discovery notes saved."
        payload = {
            "paper": {
                "title": paper.title,
                "target_language": paper.target_language,
                "target_venue": paper.target_venue,
            },
            "stage": stage.value,
            "objective": plan.paper_plan.objective,
            "discovery_notes": discovery_note,
            "section_context": section_context,
            "global_risks": plan.paper_plan.global_risks,
            "workflow_steps": plan.paper_plan.workflow_steps,
        }
        prompt = (
            "Use the assembled modules and this runtime context to perform the stage.\n\n"
            f"{json.dumps(payload, ensure_ascii=True, indent=2)}"
        )
        if additional_instructions:
            prompt = f"{prompt}\n\nAdditional instructions:\n{additional_instructions.strip()}"
        return prompt

    def _use_case_framing(self, document_type: DocumentType) -> str:
        if document_type == DocumentType.ACADEMIC_PAPER:
            return (
                "This run is for an academic paper use case. Preserve technical precision, do not invent "
                "support, and prefer structure that reads like a serious submission draft rather than a generic essay."
            )
        if document_type == DocumentType.REPORT:
            return "This run is for a structured report. Optimize for clarity, audience fit, and grounded exposition."
        if document_type == DocumentType.THESIS:
            return "This run is for thesis or dissertation writing. Maintain long-horizon consistency across sections."
        if document_type == DocumentType.PROPOSAL:
            return "This run is for proposal writing. Emphasize motivation, scope, feasibility, and constraints."
        if document_type == DocumentType.TECHNICAL_DOCUMENT:
            return (
                "This run is for technical documentation. Emphasize requirements, architecture, interfaces, "
                "validation, and precise operational guidance."
            )
        return "This run is for structured technical writing. Keep outputs grounded, explicit, and audience-aware."

    def _task_profile_module(
        self,
        paper: Paper,
        plan: PlanningRunRead,
        discovery: DiscoveryRecord | None,
    ) -> str:
        discovery_goal = discovery.user_goal if discovery is not None else None
        lines = [
            f"Paper title: {paper.title}",
            f"Document type: {plan.task_profile.document_type.value}",
            f"Audience: {plan.task_profile.audience}",
            f"Objective: {plan.paper_plan.objective}",
        ]
        if discovery_goal:
            lines.append(f"User goal: {discovery_goal}")
        if plan.task_profile.success_criteria:
            lines.append("Success criteria:")
            lines.extend(f"- {item}" for item in plan.task_profile.success_criteria)
        if plan.task_profile.constraints:
            lines.append("Constraints:")
            lines.extend(f"- {item}" for item in plan.task_profile.constraints)
        return "\n".join(lines)

    def _source_mode_module(self, plan: PlanningRunRead) -> str:
        return (
            f"Source mode: {plan.entry_strategy.source_mode.value}\n"
            f"Current maturity: {plan.entry_strategy.current_maturity.value}\n"
            f"Rationale: {plan.entry_strategy.rationale}\n"
            "Preserve strong existing material when possible, and only draft or rewrite what the plan justifies."
        )

    def _style_guidance_module(self, plan: PlanningRunRead, style_guide: StyleGuide | None) -> str:
        lines = [f"Style profile: {plan.prompt_assembly_hints.style_profile}"]
        if style_guide is not None:
            if style_guide.tone:
                lines.append(f"Tone: {style_guide.tone}")
            if style_guide.voice:
                lines.append(f"Voice: {style_guide.voice}")
            if style_guide.citation_style:
                lines.append(f"Citation style: {style_guide.citation_style}")
            if style_guide.terminology_preferences:
                lines.append("Terminology preferences:")
                lines.extend(f"- {key}: {value}" for key, value in style_guide.terminology_preferences.items())
            if style_guide.forbidden_patterns:
                lines.append("Forbidden patterns:")
                lines.extend(f"- {item}" for item in style_guide.forbidden_patterns)
        else:
            lines.append("No explicit style guide is saved for this paper.")
        return "\n".join(lines)

    def _safety_module(
        self,
        plan: PlanningRunRead,
        discovery: DiscoveryRecord | None,
        section: OutlineNode | None,
    ) -> str:
        lines = [
            "Do not invent claims, citations, datasets, experiments, equations, or results.",
            "Do not overwrite already-strong technical content just to make the prose smoother.",
            "Mark work as blocked or incomplete when the source basis is missing.",
        ]
        if discovery is not None and discovery.constraints:
            lines.append("Discovery-time constraints:")
            lines.extend(f"- {item}" for item in discovery.constraints)
        if section is not None:
            lines.append(f"Current focused section: {section.title}")
        if plan.prompt_assembly_hints.risk_emphasis:
            lines.append("Planning-time risk emphasis:")
            lines.extend(f"- {item}" for item in plan.prompt_assembly_hints.risk_emphasis)
        return "\n".join(lines)

    def _output_schema_module(self, stage: PromptStage, section: OutlineNode | None) -> str:
        section_ref = section.title if section is not None else "the current target scope"
        if stage == PromptStage.WRITER:
            return (
                f"Write content for {section_ref}. Return a grounded draft body plus any explicit unsupported "
                "claim warnings that should be surfaced before persistence."
            )
        if stage == PromptStage.REVIEWER:
            return (
                f"Review {section_ref}. Return structured findings with severity, explanation, and suggested action."
            )
        if stage == PromptStage.REVISER:
            return (
                f"Revise {section_ref}. Return improved text plus a concise account of which issues were addressed."
            )
        if stage == PromptStage.VERIFIER:
            return "Return grounded verification findings about support coverage, overclaim risk, and missing evidence."
        if stage == PromptStage.EDITOR:
            return "Return whole-document editing guidance focused on coherence, structure, and audience fit."
        return "Return structured planning output."

    def _verification_module(self, plan: PlanningRunRead) -> str:
        if not plan.prompt_assembly_hints.risk_emphasis:
            return "No extra verification emphasis is currently required."
        lines = ["Emphasize the following risks during this stage:"]
        lines.extend(f"- {item}" for item in plan.prompt_assembly_hints.risk_emphasis)
        return "\n".join(lines)

    def _stage_prompt_pack_module(self, stage: PromptStage) -> PromptModuleRead:
        pack = self._load_prompt_pack()
        stage_pack = pack.get("stages", {}).get(stage.value)
        if not isinstance(stage_pack, dict):
            raise RuntimeError(f"Prompt pack missing stage '{stage.value}'.")
        lines = [
            f"Prompt pack: {pack.get('pack_name', 'unknown')}",
            f"Prompt pack version: {pack.get('version', 'unknown')}",
            f"Stage role: {stage_pack.get('role', stage.value)}",
            f"Objective: {stage_pack.get('objective', '')}",
        ]
        self._extend_prompt_pack_section(lines, "Shared rules", pack.get("shared_rules", []))
        self._extend_prompt_pack_section(lines, "Required inputs", stage_pack.get("required_inputs", []))
        self._extend_prompt_pack_section(lines, "Action policy", stage_pack.get("action_policy", []))
        self._extend_prompt_pack_section(lines, "Output contract", stage_pack.get("output_contract", []))
        return PromptModuleRead(
            key="stage_prompt_pack",
            title="Stage Prompt Pack",
            content="\n".join(lines),
            source=f"configs/prompt-packs/{self.PROMPT_PACK_FILE}",
        )

    def _extend_prompt_pack_section(
        self,
        lines: list[str],
        title: str,
        values: object,
    ) -> None:
        if not isinstance(values, list) or not values:
            return
        lines.append(f"{title}:")
        lines.extend(f"- {item}" for item in values if isinstance(item, str) and item.strip())

    def _prompt_pack_metadata(self, stage: PromptStage) -> dict[str, str | None]:
        pack = self._load_prompt_pack()
        stages = pack.get("stages", {})
        stage_pack = stages.get(stage.value) if isinstance(stages, dict) else None
        role = stage_pack.get("role") if isinstance(stage_pack, dict) else None
        return {
            "name": pack.get("pack_name") if isinstance(pack.get("pack_name"), str) else None,
            "version": pack.get("version") if isinstance(pack.get("version"), str) else None,
            "stage": stage.value,
            "role": role if isinstance(role, str) else None,
        }

    def _prompt_pack_version(self) -> str | None:
        version = self._load_prompt_pack().get("version")
        return version if isinstance(version, str) else None

    def _section_context(self, section_plans: list[SectionPlan], section: OutlineNode | None) -> dict[str, Any]:
        if section is not None:
            target = next((item for item in section_plans if item.section_id == section.id), None)
            return target.model_dump(mode="json") if target is not None else {"section_title": section.title}
        return {
            "section_count": len(section_plans),
            "sample_section_plans": [item.model_dump(mode="json") for item in section_plans[:5]],
        }

    def _supersede_active_artifacts(
        self,
        *,
        paper_id: uuid.UUID,
        stage: PromptStage,
        section_id: uuid.UUID | None,
    ) -> None:
        artifacts = self.session.exec(
            select(PromptAssemblyArtifact).where(
                PromptAssemblyArtifact.paper_id == paper_id,
                PromptAssemblyArtifact.stage == stage,
                PromptAssemblyArtifact.section_id == section_id,
                PromptAssemblyArtifact.status == ArtifactStatus.ACTIVE,
            )
        ).all()
        for artifact in artifacts:
            artifact.status = ArtifactStatus.SUPERSEDED
            self.session.add(artifact)

    def _next_version(
        self,
        paper_id: uuid.UUID,
        stage: PromptStage,
        section_id: uuid.UUID | None,
    ) -> int:
        latest = self.session.exec(
            select(PromptAssemblyArtifact)
            .where(
                PromptAssemblyArtifact.paper_id == paper_id,
                PromptAssemblyArtifact.stage == stage,
                PromptAssemblyArtifact.section_id == section_id,
            )
            .order_by(PromptAssemblyArtifact.version.desc())
        ).first()
        return 1 if latest is None else latest.version + 1

    def _load_prompt(self, filename: str) -> str:
        path = self._repo_root() / "configs" / "prompts" / filename
        return path.read_text(encoding="utf-8").strip()

    def _load_prompt_pack(self) -> dict[str, Any]:
        path = self._repo_root() / "configs" / "prompt-packs" / self.PROMPT_PACK_FILE
        return json.loads(path.read_text(encoding="utf-8"))

    def _repo_root(self) -> Path:
        for parent in Path(__file__).resolve().parents:
            if (parent / "configs" / "prompts").exists():
                return parent
        raise RuntimeError("Unable to locate repository root for prompt assembly.")
