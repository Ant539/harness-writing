"""Unified workflow runner orchestration."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models import OutlineNode, Paper, SectionContract, WorkflowRun, WorkflowStepRun
from app.models.enums import (
    DocumentType,
    PromptStage,
    SectionAction,
    WorkflowRunStatus,
    WorkflowStepKind,
    WorkflowStepStatus,
)
from app.schemas.contracts import ContractGenerationRequest
from app.schemas.planning import DiscoveryCreate, PlanningRunRead
from app.schemas.prompts import PromptAssemblyRequest
from app.schemas.workflows import (
    WorkflowRunDetailRead,
    WorkflowRunRead,
    WorkflowRunStartRequest,
    WorkflowStepRunRead,
)
from app.services.crud import get_or_404
from app.services.planner import ContractGenerator, OutlineGenerator, WorkflowPlanningService
from app.services.prompt_assembly import PromptAssemblyService
from app.services.section_actions import SectionActionExecutor


class WorkflowRunnerService:
    """Run the unified workflow entry path and persist step history."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.planning_service = WorkflowPlanningService(session)
        self.prompt_assembly_service = PromptAssemblyService(session)
        self.outline_generator = OutlineGenerator(session)
        self.contract_generator = ContractGenerator(session)
        self.section_action_executor = SectionActionExecutor(session)

    def start_run(self, paper_id: uuid.UUID, payload: WorkflowRunStartRequest) -> WorkflowRun:
        paper = get_or_404(self.session, Paper, paper_id, "Paper")
        now = datetime.now(timezone.utc)
        run = WorkflowRun(
            paper_id=paper_id,
            status=WorkflowRunStatus.RUNNING,
            dry_run=payload.dry_run,
            auto_execute=payload.auto_execute,
            requested_section_limit=payload.section_limit,
            metadata_json={"path": "unified_workflow_runner"},
            updated_at=now,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        try:
            discovery = self._run_discovery(run, paper, payload)
            plan = self._run_plan(run, paper_id, discovery.id if discovery is not None else None, payload)
            if payload.auto_execute:
                plan = self._run_execution(run, paper, plan, discovery.id if discovery is not None else None, payload)
            plan = self._run_prompt_assembly(
                run,
                paper.id,
                plan,
                discovery.id if discovery is not None else None,
                payload,
            )
            self._complete_run(run, discovery_id=discovery.id if discovery is not None else None, planning_run_id=plan.id)
            return run
        except Exception as exc:
            self._fail_run(run, str(exc))
            raise

    def list_runs_for_paper(self, paper_id: uuid.UUID) -> list[WorkflowRun]:
        get_or_404(self.session, Paper, paper_id, "Paper")
        return list(
            self.session.exec(
                select(WorkflowRun)
                .where(WorkflowRun.paper_id == paper_id)
                .order_by(WorkflowRun.created_at.desc())
            ).all()
        )

    def get_run(self, run_id: uuid.UUID) -> WorkflowRun:
        return get_or_404(self.session, WorkflowRun, run_id, "Workflow run")

    def list_steps(self, workflow_run_id: uuid.UUID) -> list[WorkflowStepRun]:
        return list(
            self.session.exec(
                select(WorkflowStepRun)
                .where(WorkflowStepRun.workflow_run_id == workflow_run_id)
                .order_by(WorkflowStepRun.sequence_index, WorkflowStepRun.created_at)
            ).all()
        )

    def workflow_run_read(self, run: WorkflowRun) -> WorkflowRunRead:
        return WorkflowRunRead(
            id=run.id,
            paper_id=run.paper_id,
            discovery_id=run.discovery_id,
            planning_run_id=run.planning_run_id,
            status=run.status,
            dry_run=run.dry_run,
            auto_execute=run.auto_execute,
            requested_section_limit=run.requested_section_limit,
            current_step_key=run.current_step_key,
            metadata=run.metadata_json,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    def workflow_step_read(self, step: WorkflowStepRun) -> WorkflowStepRunRead:
        return WorkflowStepRunRead(
            id=step.id,
            workflow_run_id=step.workflow_run_id,
            paper_id=step.paper_id,
            discovery_id=step.discovery_id,
            planning_run_id=step.planning_run_id,
            section_id=step.section_id,
            sequence_index=step.sequence_index,
            step_key=step.step_key,
            step_type=step.step_type,
            title=step.title,
            status=step.status,
            result=step.result_json,
            error_message=step.error_message,
            started_at=step.started_at,
            completed_at=step.completed_at,
            created_at=step.created_at,
            updated_at=step.updated_at,
        )

    def workflow_run_detail_read(self, run: WorkflowRun) -> WorkflowRunDetailRead:
        return WorkflowRunDetailRead(
            **self.workflow_run_read(run).model_dump(),
            steps=[self.workflow_step_read(step) for step in self.list_steps(run.id)],
        )

    def _run_discovery(
        self,
        run: WorkflowRun,
        paper: Paper,
        payload: WorkflowRunStartRequest,
    ):
        step = self._start_step(
            run,
            step_type=WorkflowStepKind.DISCOVER,
            step_key="discover",
            title="Persist discovery context",
        )
        if payload.discovery is not None:
            discovery = self.planning_service.save_discovery(paper.id, payload.discovery)
            self._complete_step(
                run,
                step,
                result={
                    "mode": "provided",
                    "discovery_id": str(discovery.id),
                    "document_type": discovery.document_type.value,
                },
                discovery_id=discovery.id,
            )
            return discovery

        existing = self.planning_service.get_latest_discovery(paper.id)
        if existing is not None:
            self._complete_step(
                run,
                step,
                result={
                    "mode": "reused",
                    "discovery_id": str(existing.id),
                    "document_type": existing.document_type.value,
                },
                discovery_id=existing.id,
            )
            return existing

        inferred = self._inferred_discovery(paper)
        discovery = self.planning_service.save_discovery(paper.id, inferred)
        self._complete_step(
            run,
            step,
            result={
                "mode": "inferred",
                "discovery_id": str(discovery.id),
                "document_type": discovery.document_type.value,
            },
            discovery_id=discovery.id,
        )
        return discovery

    def _run_plan(
        self,
        run: WorkflowRun,
        paper_id: uuid.UUID,
        discovery_id: uuid.UUID | None,
        payload: WorkflowRunStartRequest,
        *,
        replan: bool = False,
    ):
        step = self._start_step(
            run,
            step_type=WorkflowStepKind.REPLAN if replan else WorkflowStepKind.PLAN,
            step_key="replan" if replan else "plan",
            title="Refresh workflow plan" if replan else "Generate workflow plan",
            discovery_id=discovery_id,
        )
        plan_request = payload.planning.model_copy(update={"discovery_id": discovery_id})
        plan = self.planning_service.generate_plan(paper_id, plan_request)
        self._complete_step(
            run,
            step,
            result={
                "planning_run_id": str(plan.id),
                "planner_mode": plan.planner_mode.value,
                "workflow_steps": plan.paper_plan_json.get("workflow_steps", []),
            },
            discovery_id=discovery_id,
            planning_run_id=plan.id,
        )
        return plan

    def _run_execution(
        self,
        run: WorkflowRun,
        paper: Paper,
        plan,
        discovery_id: uuid.UUID | None,
        payload: WorkflowRunStartRequest,
    ):
        if "outline_or_outline_reconciliation" in plan.paper_plan_json.get("workflow_steps", []):
            if payload.dry_run:
                self._pending_step(
                    run,
                    step_type=WorkflowStepKind.GENERATE_OUTLINE,
                    step_key="generate_outline",
                    title="Generate outline from workflow plan",
                    result={"reason": "dry_run"},
                    discovery_id=discovery_id,
                    planning_run_id=plan.id,
                )
            else:
                step = self._start_step(
                    run,
                    step_type=WorkflowStepKind.GENERATE_OUTLINE,
                    step_key="generate_outline",
                    title="Generate outline from workflow plan",
                    discovery_id=discovery_id,
                    planning_run_id=plan.id,
                )
                outline = self.outline_generator.generate(paper, payload.outline)
                self._complete_step(
                    run,
                    step,
                    result={"created_section_count": len(outline)},
                    discovery_id=discovery_id,
                    planning_run_id=plan.id,
                )
                plan = self._run_plan(run, paper.id, discovery_id, payload, replan=True)

        plan_read = self.planning_service.planning_run_read(plan)
        section_plans = self._limited_section_plans(plan_read, payload.section_limit)
        sections_by_id = {
            section.id: section
            for section in self.session.exec(
                select(OutlineNode).where(OutlineNode.paper_id == paper.id)
            ).all()
        }

        for index, section_plan in enumerate(section_plans, start=1):
            action_step_key = f"section_action:{index}"
            action_result = {
                "section_title": section_plan.section_title,
                "action": section_plan.action.value,
                "needs_evidence": section_plan.needs_evidence,
                "needs_review_loop": section_plan.needs_review_loop,
            }
            if section_plan.action == SectionAction.BLOCKED:
                self._skipped_step(
                    run,
                    step_type=WorkflowStepKind.SECTION_ACTION,
                    step_key=action_step_key,
                    title=f"Section action for {section_plan.section_title}",
                    result={**action_result, "reason": section_plan.reason},
                    discovery_id=discovery_id,
                    planning_run_id=plan.id,
                    section_id=section_plan.section_id,
                )
                continue

            if payload.dry_run:
                self._pending_step(
                    run,
                    step_type=WorkflowStepKind.SECTION_ACTION,
                    step_key=action_step_key,
                    title=f"Section action for {section_plan.section_title}",
                    result={**action_result, "reason": section_plan.reason},
                    discovery_id=discovery_id,
                    planning_run_id=plan.id,
                    section_id=section_plan.section_id,
                )
                continue

            section = sections_by_id.get(section_plan.section_id) if section_plan.section_id is not None else None
            if section is None:
                self._skipped_step(
                    run,
                    step_type=WorkflowStepKind.SECTION_ACTION,
                    step_key=action_step_key,
                    title=f"Section action for {section_plan.section_title}",
                    result={**action_result, "reason": "Section not found after planning."},
                    discovery_id=discovery_id,
                    planning_run_id=plan.id,
                    section_id=section_plan.section_id,
                )
                continue

            contract = self.session.exec(
                select(SectionContract).where(SectionContract.section_id == section.id)
            ).first()
            if contract is None and section.status.value in {"planned", "contract_ready"}:
                contract_step = self._start_step(
                    run,
                    step_type=WorkflowStepKind.GENERATE_CONTRACT,
                    step_key=f"generate_contract:{section.id}",
                    title=f"Generate contract for {section.title}",
                    discovery_id=discovery_id,
                    planning_run_id=plan.id,
                    section_id=section.id,
                )
                contract = self.contract_generator.generate(
                    paper,
                    section,
                    ContractGenerationRequest(
                        additional_constraints=section_plan.reason,
                        force=False,
                    ),
                )
                self._complete_step(
                    run,
                    contract_step,
                    result={"contract_id": str(contract.id), "section_title": section.title},
                    discovery_id=discovery_id,
                    planning_run_id=plan.id,
                    section_id=section.id,
                )
            elif contract is None:
                self._skipped_step(
                    run,
                    step_type=WorkflowStepKind.GENERATE_CONTRACT,
                    step_key=f"generate_contract:{section.id}",
                    title=f"Generate contract for {section.title}",
                    result={
                        "reason": f"Section status {section.status.value} does not support deterministic contract backfill yet."
                    },
                    discovery_id=discovery_id,
                    planning_run_id=plan.id,
                    section_id=section.id,
                )

            action_step = self._start_step(
                run,
                step_type=WorkflowStepKind.SECTION_ACTION,
                step_key=action_step_key,
                title=f"Section action for {section.title}",
                discovery_id=discovery_id,
                planning_run_id=plan.id,
                section_id=section.id,
            )
            execution = self.section_action_executor.execute(
                paper=paper,
                section=section,
                section_plan=section_plan,
            )
            self._finish_step(
                run,
                action_step,
                status=execution.status,
                result={**execution.result, "contract_ready": contract is not None},
                discovery_id=discovery_id,
                planning_run_id=plan.id,
                section_id=section.id,
            )

        return plan

    def _run_prompt_assembly(
        self,
        run: WorkflowRun,
        paper_id: uuid.UUID,
        plan,
        discovery_id: uuid.UUID | None,
        payload: WorkflowRunStartRequest,
    ):
        step = self._start_step(
            run,
            step_type=WorkflowStepKind.ASSEMBLE_PROMPTS,
            step_key="assemble_prompts",
            title="Assemble reusable prompt artifacts",
            discovery_id=discovery_id,
            planning_run_id=plan.id,
        )
        stages = self._default_prompt_stages()
        artifacts = []
        for stage in stages:
            artifact = self.prompt_assembly_service.assemble(
                paper_id,
                PromptAssemblyRequest(
                    stage=stage,
                    planning_run_id=plan.id,
                    workflow_run_id=run.id,
                ),
            )
            artifacts.append({"stage": artifact.stage.value, "artifact_id": str(artifact.id)})
        self._complete_step(
            run,
            step,
            result={"artifacts": artifacts},
            discovery_id=discovery_id,
            planning_run_id=plan.id,
        )
        return plan

    def _limited_section_plans(
        self,
        plan: PlanningRunRead,
        section_limit: int | None,
    ):
        if section_limit is None or section_limit <= 0:
            return plan.section_plans
        return plan.section_plans[:section_limit]

    def _inferred_discovery(self, paper: Paper) -> DiscoveryCreate:
        constraints = []
        if paper.target_language:
            constraints.append(f"Target language: {paper.target_language}.")
        if paper.target_venue:
            constraints.append(f"Target venue/context: {paper.target_venue}.")
        return DiscoveryCreate(
            document_type=DocumentType.ACADEMIC_PAPER,
            user_goal=f"Develop '{paper.title}' into a usable structured manuscript.",
            audience=paper.target_venue or "General academic or technical reader",
            success_criteria=[
                "Clarify the document objective before execution.",
                "Produce a reusable workflow plan for downstream section work.",
            ],
            constraints=constraints,
            current_document_state="No explicit discovery payload was provided; inferred from persisted paper metadata.",
            assumptions=["Academic paper handling remains the current default test case."],
            notes="Auto-inferred by the workflow runner so execution can begin conservatively.",
        )

    def _default_prompt_stages(self) -> list[PromptStage]:
        return [
            PromptStage.WRITER,
            PromptStage.REVIEWER,
            PromptStage.REVISER,
            PromptStage.VERIFIER,
            PromptStage.EDITOR,
        ]

    def _start_step(
        self,
        run: WorkflowRun,
        *,
        step_type: WorkflowStepKind,
        step_key: str,
        title: str,
        discovery_id: uuid.UUID | None = None,
        planning_run_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
    ) -> WorkflowStepRun:
        now = datetime.now(timezone.utc)
        step = WorkflowStepRun(
            workflow_run_id=run.id,
            paper_id=run.paper_id,
            discovery_id=discovery_id,
            planning_run_id=planning_run_id,
            section_id=section_id,
            sequence_index=self._next_sequence(run.id),
            step_key=step_key,
            step_type=step_type,
            title=title,
            status=WorkflowStepStatus.RUNNING,
            started_at=now,
            updated_at=now,
        )
        run.current_step_key = step_key
        run.updated_at = now
        self.session.add(step)
        self.session.add(run)
        self.session.commit()
        self.session.refresh(step)
        self.session.refresh(run)
        return step

    def _complete_step(
        self,
        run: WorkflowRun,
        step: WorkflowStepRun,
        *,
        result: dict[str, Any],
        discovery_id: uuid.UUID | None = None,
        planning_run_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
    ) -> None:
        self._finish_step(
            run,
            step,
            status=WorkflowStepStatus.COMPLETED,
            result=result,
            discovery_id=discovery_id,
            planning_run_id=planning_run_id,
            section_id=section_id,
        )

    def _finish_step(
        self,
        run: WorkflowRun,
        step: WorkflowStepRun,
        *,
        status: WorkflowStepStatus,
        result: dict[str, Any],
        discovery_id: uuid.UUID | None = None,
        planning_run_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        step.status = status
        step.result_json = result
        step.discovery_id = discovery_id if discovery_id is not None else step.discovery_id
        step.planning_run_id = planning_run_id if planning_run_id is not None else step.planning_run_id
        step.section_id = section_id if section_id is not None else step.section_id
        step.completed_at = now if status != WorkflowStepStatus.PENDING else None
        step.updated_at = now
        run.discovery_id = discovery_id if discovery_id is not None else run.discovery_id
        run.planning_run_id = planning_run_id if planning_run_id is not None else run.planning_run_id
        run.updated_at = now
        self.session.add(step)
        self.session.add(run)
        self.session.commit()

    def _complete_instant_step(
        self,
        run: WorkflowRun,
        *,
        step_type: WorkflowStepKind,
        step_key: str,
        title: str,
        result: dict[str, Any],
        discovery_id: uuid.UUID | None = None,
        planning_run_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
    ) -> None:
        step = self._start_step(
            run,
            step_type=step_type,
            step_key=step_key,
            title=title,
            discovery_id=discovery_id,
            planning_run_id=planning_run_id,
            section_id=section_id,
        )
        self._complete_step(
            run,
            step,
            result=result,
            discovery_id=discovery_id,
            planning_run_id=planning_run_id,
            section_id=section_id,
        )

    def _pending_step(
        self,
        run: WorkflowRun,
        *,
        step_type: WorkflowStepKind,
        step_key: str,
        title: str,
        result: dict[str, Any],
        discovery_id: uuid.UUID | None = None,
        planning_run_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
    ) -> None:
        self._terminal_step(
            run,
            status=WorkflowStepStatus.PENDING,
            step_type=step_type,
            step_key=step_key,
            title=title,
            result=result,
            discovery_id=discovery_id,
            planning_run_id=planning_run_id,
            section_id=section_id,
        )

    def _skipped_step(
        self,
        run: WorkflowRun,
        *,
        step_type: WorkflowStepKind,
        step_key: str,
        title: str,
        result: dict[str, Any],
        discovery_id: uuid.UUID | None = None,
        planning_run_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
    ) -> None:
        self._terminal_step(
            run,
            status=WorkflowStepStatus.SKIPPED,
            step_type=step_type,
            step_key=step_key,
            title=title,
            result=result,
            discovery_id=discovery_id,
            planning_run_id=planning_run_id,
            section_id=section_id,
        )

    def _terminal_step(
        self,
        run: WorkflowRun,
        *,
        status: WorkflowStepStatus,
        step_type: WorkflowStepKind,
        step_key: str,
        title: str,
        result: dict[str, Any],
        discovery_id: uuid.UUID | None = None,
        planning_run_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        step = WorkflowStepRun(
            workflow_run_id=run.id,
            paper_id=run.paper_id,
            discovery_id=discovery_id,
            planning_run_id=planning_run_id,
            section_id=section_id,
            sequence_index=self._next_sequence(run.id),
            step_key=step_key,
            step_type=step_type,
            title=title,
            status=status,
            result_json=result,
            completed_at=now if status != WorkflowStepStatus.PENDING else None,
            updated_at=now,
        )
        self.session.add(step)
        self.session.commit()

    def _complete_run(
        self,
        run: WorkflowRun,
        *,
        discovery_id: uuid.UUID | None,
        planning_run_id: uuid.UUID | None,
    ) -> None:
        now = datetime.now(timezone.utc)
        run.discovery_id = discovery_id
        run.planning_run_id = planning_run_id
        run.status = WorkflowRunStatus.COMPLETED
        run.current_step_key = None
        run.updated_at = now
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

    def _fail_run(self, run: WorkflowRun, error_message: str) -> None:
        now = datetime.now(timezone.utc)
        current_step = self.session.exec(
            select(WorkflowStepRun)
            .where(
                WorkflowStepRun.workflow_run_id == run.id,
                WorkflowStepRun.status == WorkflowStepStatus.RUNNING,
            )
            .order_by(WorkflowStepRun.sequence_index.desc())
        ).first()
        if current_step is not None:
            current_step.status = WorkflowStepStatus.FAILED
            current_step.error_message = error_message
            current_step.completed_at = now
            current_step.updated_at = now
            self.session.add(current_step)
        run.status = WorkflowRunStatus.FAILED
        run.updated_at = now
        run.current_step_key = None
        run.metadata_json = {**run.metadata_json, "error": error_message}
        self.session.add(run)
        self.session.commit()

    def _next_sequence(self, workflow_run_id: uuid.UUID) -> int:
        existing = self.session.exec(
            select(WorkflowStepRun)
            .where(WorkflowStepRun.workflow_run_id == workflow_run_id)
            .order_by(WorkflowStepRun.sequence_index.desc())
        ).first()
        return 1 if existing is None else existing.sequence_index + 1
