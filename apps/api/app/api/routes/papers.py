"""Paper and style guide CRUD routes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.api.deps import get_session
from app.models import OutlineNode, Paper, SourceMaterial, StyleGuide
from app.schemas.drafts import DraftUnitRead
from app.schemas.evidence import SourceMaterialRead
from app.schemas.latex_import import LatexImportRequest, LatexImportResponse
from app.schemas.outlines import OutlineGenerationRequest, OutlineGenerationResponse, OutlineRead
from app.schemas.outlines import OutlineNodeRead
from app.schemas.papers import PaperCreate, PaperRead, PaperTransition, PaperUpdate
from app.schemas.style_guides import StyleGuideForPaperCreate, StyleGuideRead, StyleGuideUpdate
from app.services.crud import create_item, delete_item, get_or_404, update_item
from app.services.latex_import import LatexManuscriptImporter
from app.services.planner import OutlineGenerator
from app.state_machine import InvalidStateTransition, validate_paper_transition

router = APIRouter(prefix="/papers", tags=["papers"])


def _touch_paper(paper: Paper) -> None:
    paper.updated_at = datetime.now(timezone.utc)


def _source_material_read(source: SourceMaterial) -> SourceMaterialRead:
    return SourceMaterialRead(
        id=source.id,
        paper_id=source.paper_id,
        source_type=source.source_type,
        title=source.title,
        source_ref=source.source_ref,
        content=source.content,
        citation_key=source.citation_key,
        metadata=source.metadata_json,
        created_at=source.created_at,
    )


@router.post("", response_model=PaperRead, status_code=status.HTTP_201_CREATED)
def create_paper(payload: PaperCreate, session: Session = Depends(get_session)) -> Paper:
    data = payload.model_dump(exclude={"user_goals"})
    return create_item(session, Paper(**data))


@router.get("", response_model=list[PaperRead])
def list_papers(session: Session = Depends(get_session)) -> list[Paper]:
    return list(session.exec(select(Paper).order_by(Paper.created_at)).all())


@router.post("/import-latex", response_model=LatexImportResponse, status_code=status.HTTP_201_CREATED)
def import_latex_manuscript(
    payload: LatexImportRequest,
    session: Session = Depends(get_session),
) -> LatexImportResponse:
    paper, source, outline, drafts, parsed = LatexManuscriptImporter(session).import_manuscript(
        payload
    )
    return LatexImportResponse(
        paper=PaperRead.model_validate(paper),
        source=_source_material_read(source),
        outline=[OutlineNodeRead.model_validate(node) for node in outline],
        drafts=[DraftUnitRead.model_validate(draft) for draft in drafts],
        abstract=parsed.abstract,
        keywords=parsed.keywords,
        imported_section_ids=[node.id for node in outline],
    )


@router.get("/{paper_id}", response_model=PaperRead)
def get_paper(paper_id: uuid.UUID, session: Session = Depends(get_session)) -> Paper:
    return get_or_404(session, Paper, paper_id, "Paper")


@router.patch("/{paper_id}", response_model=PaperRead)
def update_paper(
    paper_id: uuid.UUID,
    payload: PaperUpdate,
    session: Session = Depends(get_session),
) -> Paper:
    paper = get_or_404(session, Paper, paper_id, "Paper")
    data = payload.model_dump(exclude_unset=True)
    target_status = data.get("status")
    if target_status is not None:
        try:
            validate_paper_transition(paper.status, target_status)
        except InvalidStateTransition as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    _touch_paper(paper)
    return update_item(session, paper, data)


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_paper(paper_id: uuid.UUID, session: Session = Depends(get_session)) -> Response:
    paper = get_or_404(session, Paper, paper_id, "Paper")
    delete_item(session, paper)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{paper_id}/transition", response_model=PaperRead)
def transition_paper(
    paper_id: uuid.UUID,
    payload: PaperTransition,
    session: Session = Depends(get_session),
) -> Paper:
    paper = get_or_404(session, Paper, paper_id, "Paper")
    try:
        validate_paper_transition(paper.status, payload.status)
    except InvalidStateTransition as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _touch_paper(paper)
    return update_item(session, paper, {"status": payload.status})


@router.get("/{paper_id}/outline", response_model=OutlineRead)
def get_paper_outline(paper_id: uuid.UUID, session: Session = Depends(get_session)) -> OutlineRead:
    get_or_404(session, Paper, paper_id, "Paper")
    nodes = session.exec(
        select(OutlineNode)
        .where(OutlineNode.paper_id == paper_id)
        .order_by(OutlineNode.level, OutlineNode.order_index)
    ).all()
    return OutlineRead(paper_id=paper_id, nodes=list(nodes))


@router.post("/{paper_id}/generate-outline", response_model=OutlineGenerationResponse)
def generate_paper_outline(
    paper_id: uuid.UUID,
    payload: OutlineGenerationRequest,
    session: Session = Depends(get_session),
) -> OutlineGenerationResponse:
    paper = get_or_404(session, Paper, paper_id, "Paper")
    nodes = OutlineGenerator(session).generate(paper, payload)
    return OutlineGenerationResponse(paper=paper, outline=nodes)


@router.post("/{paper_id}/style-guide", response_model=StyleGuideRead, status_code=status.HTTP_201_CREATED)
def create_style_guide(
    paper_id: uuid.UUID,
    payload: StyleGuideForPaperCreate,
    session: Session = Depends(get_session),
) -> StyleGuide:
    get_or_404(session, Paper, paper_id, "Paper")
    return create_item(session, StyleGuide(paper_id=paper_id, **payload.model_dump()))


@router.get("/{paper_id}/style-guide", response_model=StyleGuideRead | None)
def get_paper_style_guide(
    paper_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> StyleGuide | None:
    get_or_404(session, Paper, paper_id, "Paper")
    return session.exec(select(StyleGuide).where(StyleGuide.paper_id == paper_id)).first()


@router.patch("/style-guides/{style_guide_id}", response_model=StyleGuideRead)
def update_style_guide(
    style_guide_id: uuid.UUID,
    payload: StyleGuideUpdate,
    session: Session = Depends(get_session),
) -> StyleGuide:
    style_guide = get_or_404(session, StyleGuide, style_guide_id, "Style guide")
    return update_item(session, style_guide, payload.model_dump(exclude_unset=True))


@router.delete("/style-guides/{style_guide_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_style_guide(
    style_guide_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> Response:
    style_guide = get_or_404(session, StyleGuide, style_guide_id, "Style guide")
    delete_item(session, style_guide)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
