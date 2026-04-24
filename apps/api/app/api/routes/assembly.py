"""Manuscript assembly, global review, and export routes."""

import uuid

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.deps import get_session
from app.models import AssembledManuscript, ExportArtifact, ManuscriptIssue, Paper
from app.schemas.assembly import (
    AssembledManuscriptRead,
    ExportArtifactRead,
    GlobalReviewRequest,
    GlobalReviewResponse,
    ManuscriptAssemblyRequest,
    ManuscriptAssemblyResponse,
    ManuscriptExportRequest,
    ManuscriptExportResponse,
    ManuscriptIssueRead,
)
from app.schemas.papers import PaperRead
from app.services.assembly import AssemblyService
from app.services.crud import get_or_404

router = APIRouter(tags=["assembly"])


def _manuscript_read(manuscript: AssembledManuscript) -> AssembledManuscriptRead:
    return AssembledManuscriptRead.model_validate(manuscript)


def _issue_read(issue: ManuscriptIssue) -> ManuscriptIssueRead:
    return ManuscriptIssueRead.model_validate(issue)


def _export_read(export: ExportArtifact) -> ExportArtifactRead:
    return ExportArtifactRead.model_validate(export)


def _paper_read(paper: Paper) -> PaperRead:
    return PaperRead.model_validate(paper)


@router.post("/papers/{paper_id}/assemble", response_model=ManuscriptAssemblyResponse)
def assemble_paper(
    paper_id: uuid.UUID,
    payload: ManuscriptAssemblyRequest,
    session: Session = Depends(get_session),
) -> ManuscriptAssemblyResponse:
    paper = get_or_404(session, Paper, paper_id, "Paper")
    manuscript = AssemblyService(session).assemble_paper(paper, payload)
    return ManuscriptAssemblyResponse(
        paper=_paper_read(paper),
        manuscript=_manuscript_read(manuscript),
    )


@router.get(
    "/papers/{paper_id}/manuscripts/current",
    response_model=AssembledManuscriptRead | None,
)
def get_current_manuscript(
    paper_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> AssembledManuscriptRead | None:
    get_or_404(session, Paper, paper_id, "Paper")
    manuscript = AssemblyService(session).current_manuscript(paper_id)
    return _manuscript_read(manuscript) if manuscript else None


@router.get("/papers/{paper_id}/manuscripts", response_model=list[AssembledManuscriptRead])
def list_manuscripts(
    paper_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[AssembledManuscriptRead]:
    get_or_404(session, Paper, paper_id, "Paper")
    return [_manuscript_read(item) for item in AssemblyService(session).list_manuscripts(paper_id)]


@router.get("/manuscripts/{manuscript_id}", response_model=AssembledManuscriptRead)
def get_manuscript(
    manuscript_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> AssembledManuscriptRead:
    return _manuscript_read(get_or_404(session, AssembledManuscript, manuscript_id, "Manuscript"))


@router.post("/papers/{paper_id}/global-review", response_model=GlobalReviewResponse)
def global_review(
    paper_id: uuid.UUID,
    payload: GlobalReviewRequest,
    session: Session = Depends(get_session),
) -> GlobalReviewResponse:
    paper = get_or_404(session, Paper, paper_id, "Paper")
    manuscript, issues = AssemblyService(session).global_review(paper, payload)
    return GlobalReviewResponse(
        paper=_paper_read(paper),
        manuscript=_manuscript_read(manuscript),
        issues=[_issue_read(issue) for issue in issues],
    )


@router.get("/papers/{paper_id}/manuscript-issues", response_model=list[ManuscriptIssueRead])
def list_manuscript_issues(
    paper_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[ManuscriptIssueRead]:
    get_or_404(session, Paper, paper_id, "Paper")
    return [_issue_read(issue) for issue in AssemblyService(session).list_issues_for_paper(paper_id)]


@router.get(
    "/manuscripts/{manuscript_id}/issues",
    response_model=list[ManuscriptIssueRead],
)
def list_manuscript_issues_for_version(
    manuscript_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[ManuscriptIssueRead]:
    get_or_404(session, AssembledManuscript, manuscript_id, "Manuscript")
    return [
        _issue_read(issue)
        for issue in AssemblyService(session).list_issues_for_manuscript(manuscript_id)
    ]


@router.post("/papers/{paper_id}/export", response_model=ManuscriptExportResponse)
def export_paper(
    paper_id: uuid.UUID,
    payload: ManuscriptExportRequest,
    session: Session = Depends(get_session),
) -> ManuscriptExportResponse:
    paper = get_or_404(session, Paper, paper_id, "Paper")
    manuscript, export = AssemblyService(session).export_current_manuscript(paper, payload)
    return ManuscriptExportResponse(
        paper=_paper_read(paper),
        manuscript=_manuscript_read(manuscript),
        export=_export_read(export),
    )


@router.get("/papers/{paper_id}/exports", response_model=list[ExportArtifactRead])
def list_exports(
    paper_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[ExportArtifactRead]:
    get_or_404(session, Paper, paper_id, "Paper")
    return [_export_read(export) for export in AssemblyService(session).list_exports(paper_id)]


@router.get("/exports/{export_id}", response_model=ExportArtifactRead)
def get_export(
    export_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> ExportArtifactRead:
    return _export_read(get_or_404(session, ExportArtifact, export_id, "Export artifact"))
