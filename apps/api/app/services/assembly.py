"""Manuscript assembly, global review, and export orchestration."""

import uuid
from collections import defaultdict

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    AssembledManuscript,
    DraftUnit,
    ExportArtifact,
    ManuscriptIssue,
    OutlineNode,
    Paper,
    ReviewComment,
)
from app.models.enums import ArtifactStatus, DraftKind, ExportFormat, PaperStatus
from app.schemas.assembly import (
    GlobalReviewRequest,
    ManuscriptAssemblyRequest,
    ManuscriptExportRequest,
)
from app.services.editor import ExportGenerator, ManuscriptAssembler, ManuscriptReviewer
from app.state_machine.transitions import PAPER_TRANSITIONS, InvalidStateTransition, validate_paper_transition


class AssemblyService:
    """Coordinates assembly artifacts, manuscript review, and export persistence."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.assembler = ManuscriptAssembler()
        self.reviewer = ManuscriptReviewer()
        self.export_generator = ExportGenerator()

    def assemble_paper(
        self,
        paper: Paper,
        request: ManuscriptAssemblyRequest,
    ) -> AssembledManuscript:
        sections = self._ordered_sections(paper.id)
        if not sections:
            raise HTTPException(status_code=400, detail="Paper must have an outline before assembly.")

        drafts_by_section = self._active_drafts_by_section(sections)
        if not request.include_unlocked:
            locked_section_ids = {str(section.id) for section in sections if section.status == "locked"}
            drafts_by_section = {
                section_id: draft
                for section_id, draft in drafts_by_section.items()
                if section_id in locked_section_ids
            }
        if not drafts_by_section:
            raise HTTPException(
                status_code=400,
                detail="Assembly requires at least one usable current section draft.",
            )

        assembled = self.assembler.assemble(
            paper=paper,
            sections=sections,
            active_drafts_by_section=drafts_by_section,
        )
        for current in self._active_manuscripts(paper.id):
            current.status = ArtifactStatus.SUPERSEDED
            self.session.add(current)
        manuscript = AssembledManuscript(
            paper_id=paper.id,
            version=self._next_manuscript_version(paper.id),
            content=assembled.content,
            included_section_ids=assembled.included_section_ids,
            missing_section_ids=assembled.missing_section_ids,
            warnings=assembled.warnings,
            status=ArtifactStatus.ACTIVE,
        )
        self._advance_paper_to(paper, PaperStatus.ASSEMBLY_READY)
        self.session.add(manuscript)
        self.session.add(paper)
        self.session.commit()
        self.session.refresh(manuscript)
        self.session.refresh(paper)
        return manuscript

    def current_manuscript(self, paper_id: uuid.UUID) -> AssembledManuscript | None:
        return self.session.exec(
            select(AssembledManuscript)
            .where(
                AssembledManuscript.paper_id == paper_id,
                AssembledManuscript.status == ArtifactStatus.ACTIVE,
            )
            .order_by(AssembledManuscript.version.desc(), AssembledManuscript.created_at.desc())
        ).first()

    def list_manuscripts(self, paper_id: uuid.UUID) -> list[AssembledManuscript]:
        return list(
            self.session.exec(
                select(AssembledManuscript)
                .where(AssembledManuscript.paper_id == paper_id)
                .order_by(AssembledManuscript.version)
            ).all()
        )

    def global_review(
        self,
        paper: Paper,
        request: GlobalReviewRequest,
    ) -> tuple[AssembledManuscript, list[ManuscriptIssue]]:
        manuscript = self.current_manuscript(paper.id)
        if manuscript is None:
            raise HTTPException(
                status_code=400,
                detail="Global review requires a current assembled manuscript.",
            )

        existing = self.list_issues_for_manuscript(manuscript.id)
        if existing:
            return manuscript, existing

        sections = self._ordered_sections(paper.id)
        active_drafts = self._active_drafts_by_section(sections)
        unresolved_comments = self._unresolved_comments_by_section(active_drafts)
        findings = self.reviewer.review(
            manuscript=manuscript,
            sections=sections,
            unresolved_comments_by_section=unresolved_comments,
            duplicate_sibling_orders=self._duplicate_sibling_order_messages(sections),
            review_instructions=request.review_instructions,
        )
        issues = [
            ManuscriptIssue(
                paper_id=paper.id,
                manuscript_id=manuscript.id,
                issue_type=finding.issue_type,
                severity=finding.severity,
                message=finding.message,
                suggested_action=finding.suggested_action,
                resolved=False,
            )
            for finding in findings
        ]
        for issue in issues:
            self.session.add(issue)

        self._advance_paper_to(paper, PaperStatus.GLOBAL_REVIEW)
        if issues:
            self._advance_paper_to(paper, PaperStatus.FINAL_REVISION)
        self.session.add(paper)
        self.session.commit()
        self.session.refresh(manuscript)
        self.session.refresh(paper)
        for issue in issues:
            self.session.refresh(issue)
        return manuscript, issues

    def list_issues_for_paper(self, paper_id: uuid.UUID) -> list[ManuscriptIssue]:
        return list(
            self.session.exec(
                select(ManuscriptIssue)
                .where(ManuscriptIssue.paper_id == paper_id)
                .order_by(ManuscriptIssue.created_at)
            ).all()
        )

    def list_issues_for_manuscript(self, manuscript_id: uuid.UUID) -> list[ManuscriptIssue]:
        return list(
            self.session.exec(
                select(ManuscriptIssue)
                .where(ManuscriptIssue.manuscript_id == manuscript_id)
                .order_by(ManuscriptIssue.created_at)
            ).all()
        )

    def export_current_manuscript(
        self,
        paper: Paper,
        request: ManuscriptExportRequest,
    ) -> tuple[AssembledManuscript, ExportArtifact]:
        manuscript = self.current_manuscript(paper.id)
        if manuscript is None:
            raise HTTPException(status_code=400, detail="Export requires a current assembled manuscript.")

        export_format = request.export_format
        content = self.export_generator.generate(
            paper=paper,
            manuscript=manuscript,
            export_format=export_format,
            latex_options=request.latex,
        )
        metadata = self._export_metadata(export_format, request, content)
        validation = metadata.get("compile_validation")
        if request.latex.validate_compile and validation and validation.get("status") != "passed":
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "LaTeX compile validation failed.",
                    "validation": validation,
                },
            )
        version = self._next_export_version(paper.id, export_format)
        extension = self.export_generator.extension_for(export_format)
        artifact_path = (
            f"data/exports/{paper.id}/manuscript-v{manuscript.version}-"
            f"export-v{version}.{extension}"
        )
        if request.write_file:
            self.export_generator.write_file(content=content, artifact_path=artifact_path)
        export = ExportArtifact(
            paper_id=paper.id,
            manuscript_id=manuscript.id,
            version=version,
            export_format=export_format,
            content=content,
            artifact_path=artifact_path,
            metadata_json=metadata,
            status=ArtifactStatus.ACTIVE,
        )
        self.session.add(export)
        self.session.commit()
        self.session.refresh(export)
        return manuscript, export

    def _export_metadata(
        self,
        export_format: ExportFormat,
        request: ManuscriptExportRequest,
        content: str,
    ) -> dict:
        if export_format != ExportFormat.LATEX:
            return {}
        template_name = request.latex.template_name
        if template_name:
            template_name = "".join(char for char in template_name.lower() if char.isalnum() or char in "_-")
        metadata = {
            "template_name": template_name,
            "template_content_provided": bool(request.latex.template_content),
            "compile_validation_requested": request.latex.validate_compile,
        }
        if request.latex.validate_compile:
            metadata["compile_validation"] = self.export_generator.validate_latex_compile(content)
        return metadata

    def list_exports(self, paper_id: uuid.UUID) -> list[ExportArtifact]:
        return list(
            self.session.exec(
                select(ExportArtifact)
                .where(ExportArtifact.paper_id == paper_id)
                .order_by(ExportArtifact.created_at)
            ).all()
        )

    def _ordered_sections(self, paper_id: uuid.UUID) -> list[OutlineNode]:
        sections = list(
            self.session.exec(
                select(OutlineNode).where(OutlineNode.paper_id == paper_id)
            ).all()
        )
        children: dict[str | None, list[OutlineNode]] = defaultdict(list)
        by_id = {str(section.id): section for section in sections}
        for section in sections:
            parent_key = str(section.parent_id) if section.parent_id else None
            if parent_key is not None and parent_key not in by_id:
                parent_key = None
            children[parent_key].append(section)
        for siblings in children.values():
            siblings.sort(key=lambda item: (item.order_index, item.title.lower(), str(item.id)))

        ordered: list[OutlineNode] = []

        def visit(section: OutlineNode) -> None:
            ordered.append(section)
            for child in children.get(str(section.id), []):
                visit(child)

        for root in children.get(None, []):
            visit(root)
        return ordered

    def _active_drafts_by_section(
        self,
        sections: list[OutlineNode],
    ) -> dict[str, DraftUnit]:
        section_ids = [section.id for section in sections]
        if not section_ids:
            return {}
        drafts = list(
            self.session.exec(
                select(DraftUnit)
                .where(
                    DraftUnit.section_id.in_(section_ids),
                    DraftUnit.kind == DraftKind.SECTION_DRAFT,
                    DraftUnit.status == ArtifactStatus.ACTIVE,
                )
                .order_by(DraftUnit.version.desc(), DraftUnit.created_at.desc())
            ).all()
        )
        by_section: dict[str, DraftUnit] = {}
        for draft in drafts:
            by_section.setdefault(str(draft.section_id), draft)
        return by_section

    def _unresolved_comments_by_section(
        self,
        active_drafts_by_section: dict[str, DraftUnit],
    ) -> dict[str, list[ReviewComment]]:
        comments_by_section: dict[str, list[ReviewComment]] = {}
        for section_id, draft in active_drafts_by_section.items():
            comments = list(
                self.session.exec(
                    select(ReviewComment)
                    .where(
                        ReviewComment.target_draft_id == draft.id,
                        ReviewComment.resolved == False,  # noqa: E712
                    )
                    .order_by(ReviewComment.created_at)
                ).all()
            )
            if comments:
                comments_by_section[section_id] = comments
        return comments_by_section

    def _duplicate_sibling_order_messages(self, sections: list[OutlineNode]) -> list[str]:
        grouped: dict[str | None, dict[int, list[OutlineNode]]] = defaultdict(lambda: defaultdict(list))
        for section in sections:
            parent_key = str(section.parent_id) if section.parent_id else None
            grouped[parent_key][section.order_index].append(section)

        messages: list[str] = []
        for sibling_orders in grouped.values():
            for order_index, siblings in sibling_orders.items():
                if len(siblings) > 1:
                    names = ", ".join(sorted(section.title for section in siblings))
                    messages.append(f"Sibling sections share order_index {order_index}: {names}.")
        return messages

    def _active_manuscripts(self, paper_id: uuid.UUID) -> list[AssembledManuscript]:
        return list(
            self.session.exec(
                select(AssembledManuscript).where(
                    AssembledManuscript.paper_id == paper_id,
                    AssembledManuscript.status == ArtifactStatus.ACTIVE,
                )
            ).all()
        )

    def _next_manuscript_version(self, paper_id: uuid.UUID) -> int:
        latest = self.session.exec(
            select(AssembledManuscript)
            .where(AssembledManuscript.paper_id == paper_id)
            .order_by(AssembledManuscript.version.desc())
        ).first()
        return 1 if latest is None else latest.version + 1

    def _next_export_version(self, paper_id: uuid.UUID, export_format: ExportFormat) -> int:
        latest = self.session.exec(
            select(ExportArtifact)
            .where(
                ExportArtifact.paper_id == paper_id,
                ExportArtifact.export_format == export_format,
            )
            .order_by(ExportArtifact.version.desc())
        ).first()
        return 1 if latest is None else latest.version + 1

    def _advance_paper_to(self, paper: Paper, target: PaperStatus) -> None:
        if paper.status == target:
            return
        path = self._paper_transition_path(paper.status, target)
        if not path:
            return
        for next_status in path:
            try:
                validate_paper_transition(paper.status, next_status)
            except InvalidStateTransition as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            paper.status = next_status

    def _paper_transition_path(
        self,
        current: PaperStatus,
        target: PaperStatus,
    ) -> list[PaperStatus]:
        queue: list[tuple[PaperStatus, list[PaperStatus]]] = [(current, [])]
        visited = {current}
        while queue:
            status, path = queue.pop(0)
            for next_status in sorted(PAPER_TRANSITIONS[status], key=lambda value: value.value):
                if next_status in visited:
                    continue
                next_path = [*path, next_status]
                if next_status == target:
                    return next_path
                visited.add(next_status)
                queue.append((next_status, next_path))
        return []
