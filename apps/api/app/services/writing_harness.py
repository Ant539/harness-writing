"""Generic Writing Harness orchestration."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import WritingHarnessRun
from app.schemas.writing_harness import (
    TaskRoute,
    WritingArtifacts,
    WritingHarnessRunRead,
    WritingHarnessRunRequest,
    WritingStateSnapshot,
    WritingTaskType,
    WritingWorkflowState,
)
from app.services.crud import get_or_404
from app.services.writing_roles import (
    AcademicReviewer,
    AcademicWriter,
    BriefBuilder,
    CitationChecker,
    Editor,
    PaperHarnessBridge,
    Planner,
    Reviewer,
    TaskRouter,
    Writer,
)


@dataclass
class _RunContext:
    payload: WritingHarnessRunRequest
    route: TaskRoute
    artifacts: WritingArtifacts = field(default_factory=WritingArtifacts)
    state_history: list[WritingStateSnapshot] = field(default_factory=list)
    state: WritingWorkflowState = WritingWorkflowState.NEW_TASK
    version: int = 1


class WritingHarnessService:
    """Execute minimal writing workflows and persist artifact snapshots."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.router = TaskRouter()
        self.brief_builder = BriefBuilder()
        self.planner = Planner()
        self.writer = Writer()
        self.academic_writer = AcademicWriter()
        self.reviewer = Reviewer()
        self.academic_reviewer = AcademicReviewer()
        self.citation_checker = CitationChecker()
        self.editor = Editor()
        self.paper_bridge = PaperHarnessBridge(session)

    def run(self, payload: WritingHarnessRunRequest) -> WritingHarnessRun:
        route = self.router.route(payload)
        context = _RunContext(payload=payload, route=route)
        self._advance(context, WritingWorkflowState.ROUTED, ["route"])

        if route.task_type == WritingTaskType.QUICK_REWRITE:
            self._run_quick_rewrite(context)
        elif route.task_type == WritingTaskType.SIMPLE_DRAFT:
            self._run_simple_draft(context)
        elif route.task_type == WritingTaskType.ACADEMIC_PAPER:
            self._run_academic_paper(context)
        else:
            self._run_structured_or_research(context)

        return self._persist(context)

    def get_run(self, run_id: uuid.UUID) -> WritingHarnessRun:
        return get_or_404(self.session, WritingHarnessRun, run_id, "Writing harness run")

    def list_runs(self) -> list[WritingHarnessRun]:
        return list(
            self.session.exec(
                select(WritingHarnessRun).order_by(WritingHarnessRun.created_at.desc())
            ).all()
        )

    def run_read(self, run: WritingHarnessRun) -> WritingHarnessRunRead:
        return WritingHarnessRunRead(
            id=run.id,
            task_type=run.task_type,
            state=run.state,
            route=TaskRoute.model_validate(run.route_json),
            artifacts=WritingArtifacts.model_validate(run.artifacts_json),
            state_history=[
                WritingStateSnapshot.model_validate(item) for item in run.state_history_json
            ],
            metadata=run.metadata_json,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    def _run_quick_rewrite(self, context: _RunContext) -> None:
        self._advance(context, WritingWorkflowState.BRIEFING, [])
        intent = self.brief_builder.build(context.payload, context.route, quick=True)
        context.artifacts.writing_brief = intent
        self._advance(context, WritingWorkflowState.BRIEF_READY, ["writing_brief"])

        self._advance(context, WritingWorkflowState.DRAFTING, ["writing_brief"])
        source = context.payload.source_text or context.payload.user_input
        rewritten = self.writer.rewrite_text(source, context.payload.tone or intent.tone)
        context.artifacts.draft = self.writer.draft_from_brief(intent)
        context.artifacts.draft.content = rewritten
        context.artifacts.draft.known_issues = []
        context.artifacts.draft.created_from_outline_id = None
        context.artifacts.final_output = rewritten
        self._advance(context, WritingWorkflowState.FINAL_READY, ["writing_brief", "draft"])

    def _run_simple_draft(self, context: _RunContext) -> None:
        self._advance(context, WritingWorkflowState.BRIEFING, [])
        context.artifacts.writing_brief = self.brief_builder.build(context.payload, context.route)
        self._advance(context, WritingWorkflowState.BRIEF_READY, ["writing_brief"])

        self._advance(context, WritingWorkflowState.DRAFTING, ["writing_brief"])
        draft = self.writer.draft_from_brief(context.artifacts.writing_brief)
        context.artifacts.draft = draft
        self._advance(context, WritingWorkflowState.DRAFT_READY, ["writing_brief", "draft"])

        context.artifacts.review_report = self.reviewer.review(draft)
        self._advance(context, WritingWorkflowState.REVIEW_READY, ["draft", "review_report"])
        context.artifacts.final_output = draft.content
        self._advance(context, WritingWorkflowState.FINAL_READY, ["draft", "review_report"])

    def _run_structured_or_research(self, context: _RunContext) -> None:
        self._advance(context, WritingWorkflowState.BRIEFING, [])
        brief = self.brief_builder.build(context.payload, context.route)
        brief.research_required = context.route.requires_research
        brief.citation_required = context.route.requires_citations
        if brief.research_required and not context.payload.source_text:
            brief.open_questions.append("What sources should be used or verified?")
        context.artifacts.writing_brief = brief
        self._advance(context, WritingWorkflowState.BRIEF_READY, ["writing_brief"])

        self._advance(context, WritingWorkflowState.PLANNING, ["writing_brief"])
        if context.route.task_type == WritingTaskType.RESEARCH_WRITING:
            context.artifacts.source_notes = self.planner.source_notes(context.payload)
            self._advance(context, WritingWorkflowState.SOURCE_NOTES_READY, ["source_notes"])
        context.artifacts.outline = self.planner.outline_for(brief, context.route.task_type)
        self._advance(context, WritingWorkflowState.OUTLINE_READY, ["writing_brief", "outline"])

        self._advance(context, WritingWorkflowState.DRAFTING, ["outline"])
        context.artifacts.draft = self.writer.draft_from_outline(brief, context.artifacts.outline)
        self._advance(context, WritingWorkflowState.DRAFT_READY, ["outline", "draft"])

        self._advance(context, WritingWorkflowState.REVIEWING, ["draft"])
        context.artifacts.review_report = self.reviewer.review(
            context.artifacts.draft,
            citation_required=brief.citation_required,
            has_sources=bool(context.artifacts.source_notes),
        )
        self._advance(context, WritingWorkflowState.REVIEW_READY, ["draft", "review_report"])

        context.artifacts.revision_plan = self.editor.revision_plan(
            context.artifacts.review_report,
            1,
        )
        self._advance(context, WritingWorkflowState.REVISION_PLANNED, ["revision_plan"])
        self._revise(context)
        self._advance(context, WritingWorkflowState.FINAL_READY, ["draft", "changelog"])

    def _run_academic_paper(self, context: _RunContext) -> None:
        self._advance(context, WritingWorkflowState.ACADEMIC_BRIEFING, [])
        academic_brief = self.brief_builder.build_academic(context.payload, context.route)
        context.artifacts.academic_brief = academic_brief
        context.artifacts.writing_brief = academic_brief
        self._advance(context, WritingWorkflowState.RESEARCH_QUESTION_READY, ["academic_brief"])

        context.artifacts.claim_evidence_map = self.planner.claim_map(academic_brief, context.payload)
        self._advance(
            context,
            WritingWorkflowState.CLAIM_MAP_READY,
            ["academic_brief", "claim_evidence_map"],
        )

        context.artifacts.source_notes = self.planner.source_notes(context.payload)
        context.artifacts.warnings.extend(
            self.citation_checker.academic_source_warnings(context.artifacts.source_notes)
        )
        self._advance(context, WritingWorkflowState.SOURCE_NOTES_READY, ["source_notes"])

        context.artifacts.outline = self.planner.academic_outline(academic_brief)
        self._advance(
            context,
            WritingWorkflowState.PAPER_OUTLINE_READY,
            ["academic_brief", "claim_evidence_map", "outline"],
        )

        if context.payload.persist_to_paper_harness:
            self._persist_academic_paper_artifacts(context)

        self._advance(context, WritingWorkflowState.SECTION_DRAFTING, ["outline"])
        context.artifacts.draft = self.academic_writer.draft(
            academic_brief,
            context.artifacts.outline,
            context.artifacts.source_notes,
        )
        self._advance(context, WritingWorkflowState.PAPER_DRAFT_READY, ["draft"])

        self._advance(context, WritingWorkflowState.CITATION_CHECKING, ["draft", "source_notes"])
        context.artifacts.warnings.extend(
            self.citation_checker.citation_warnings(
                context.artifacts.draft,
                context.artifacts.source_notes,
            )
        )
        self._advance(
            context,
            WritingWorkflowState.CLAIM_EVIDENCE_CHECKING,
            ["draft", "claim_evidence_map"],
        )
        context.artifacts.warnings.extend(
            self.citation_checker.claim_evidence_warnings(context.artifacts.claim_evidence_map)
        )

        self._advance(context, WritingWorkflowState.ACADEMIC_REVIEWING, ["draft"])
        context.artifacts.review_report = self.academic_reviewer.review(
            brief=academic_brief,
            claim_map=context.artifacts.claim_evidence_map,
            source_notes=context.artifacts.source_notes,
        )
        self._advance(context, WritingWorkflowState.REVIEW_READY, ["review_report"])

        context.artifacts.revision_plan = self.editor.revision_plan(
            context.artifacts.review_report,
            context.artifacts.draft.version,
        )
        self._advance(context, WritingWorkflowState.REVISION_PLANNED, ["revision_plan"])
        self._revise(context)
        self._advance(context, WritingWorkflowState.FINAL_PAPER_READY, ["draft", "changelog"])

    def _persist_academic_paper_artifacts(self, context: _RunContext) -> None:
        if (
            context.artifacts.academic_brief is None
            or context.artifacts.outline is None
            or context.route.task_type != WritingTaskType.ACADEMIC_PAPER
        ):
            return
        bridge_result = self.paper_bridge.persist_academic_run(
            payload=context.payload,
            brief=context.artifacts.academic_brief,
            outline=context.artifacts.outline,
            source_notes=context.artifacts.source_notes,
        )
        context.artifacts.warnings.append(
            "Academic artifacts were also persisted to the existing paper harness store."
        )
        context.payload.metadata["paper_harness"] = bridge_result

    def _revise(self, context: _RunContext) -> None:
        if context.artifacts.draft is None or context.artifacts.revision_plan is None:
            raise ValueError("Revision requires a draft and revision plan.")
        self._advance(context, WritingWorkflowState.REVISING, ["draft", "revision_plan"])
        draft, changelog = self.editor.revise(
            context.artifacts.draft,
            context.artifacts.revision_plan,
        )
        context.artifacts.draft = draft
        context.artifacts.changelog = changelog
        context.artifacts.final_output = draft.content
        context.version = draft.version

    def _persist(self, context: _RunContext) -> WritingHarnessRun:
        now = datetime.now(timezone.utc)
        run = WritingHarnessRun(
            task_type=context.route.task_type,
            state=context.state,
            user_input=context.payload.user_input,
            route_json=context.route.model_dump(mode="json"),
            artifacts_json=context.artifacts.model_dump(mode="json"),
            state_history_json=[snapshot.model_dump(mode="json") for snapshot in context.state_history],
            metadata_json={
                **context.payload.metadata,
                "max_revision_loops": context.payload.max_revision_loops,
                "workflow_engine": "deterministic_writing_harness_v1",
                "role_modules": [
                    "TaskRouter",
                    "BriefBuilder",
                    "Planner",
                    "Writer",
                    "AcademicWriter",
                    "Reviewer",
                    "AcademicReviewer",
                    "CitationChecker",
                    "Editor",
                    "PaperHarnessBridge",
                ],
            },
            updated_at=now,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def _advance(
        self,
        context: _RunContext,
        state: WritingWorkflowState,
        artifact_keys: list[str],
    ) -> None:
        context.state = state
        needs_confirmation = state in {
            WritingWorkflowState.RESEARCH_QUESTION_READY,
            WritingWorkflowState.REVIEW_READY,
            WritingWorkflowState.REVISION_PLANNED,
        } and bool(self._blocking_messages(context))
        context.state_history.append(
            WritingStateSnapshot(
                state=state,
                artifact_keys=artifact_keys,
                version=context.version,
                can_continue=True,
                needs_user_confirmation=needs_confirmation,
                blocking_issues=self._blocking_messages(context),
                rollback_to=context.state_history[-1].state if context.state_history else None,
                regeneratable_stages=[
                    WritingWorkflowState.BRIEFING,
                    WritingWorkflowState.PLANNING,
                    WritingWorkflowState.DRAFTING,
                    WritingWorkflowState.REVIEWING,
                ],
            )
        )

    def _blocking_messages(self, context: _RunContext) -> list[str]:
        report = context.artifacts.review_report
        if report is None:
            return []
        return [issue.problem for issue in report.blocking_issues]
