"""Evidence source, item, and pack routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.api.deps import get_session
from app.models import EvidenceItem, EvidencePack, OutlineNode, Paper, SourceMaterial
from app.models.enums import ArtifactStatus, SectionStatus
from app.schemas.evidence import (
    EvidenceExtractionRequest,
    EvidenceExtractionResponse,
    EvidenceItemForPaperCreate,
    EvidenceItemRead,
    EvidenceItemUpdate,
    EvidencePackBuildRequest,
    EvidencePackBuildResponse,
    EvidencePackForSectionCreate,
    EvidencePackMembershipUpdate,
    EvidencePackRead,
    EvidencePackUpdate,
    EvidenceVerificationResponse,
    SourceMaterialCreate,
    SourceMaterialRead,
    SourceMaterialUpdate,
)
from app.services.crud import create_item, delete_item, get_or_404, update_item
from app.services.research import EvidenceExtractor, EvidencePackBuilder, SourceRegistry
from app.services.verifier import EvidenceVerificationService

router = APIRouter(tags=["evidence"])


def _evidence_item_read(item: EvidenceItem) -> EvidenceItemRead:
    return EvidenceItemRead(
        id=item.id,
        paper_id=item.paper_id,
        section_id=item.section_id,
        source_type=item.source_type,
        source_ref=item.source_ref,
        content=item.content,
        citation_key=item.citation_key,
        confidence=item.confidence,
        metadata=item.metadata_json,
        created_at=item.created_at,
    )


def _evidence_pack_read(pack: EvidencePack) -> EvidencePackRead:
    return EvidencePackRead(
        id=pack.id,
        section_id=pack.section_id,
        evidence_item_ids=[uuid.UUID(value) for value in pack.evidence_item_ids],
        coverage_summary=pack.coverage_summary,
        open_questions=pack.open_questions,
        status=pack.status,
        created_at=pack.created_at,
    )


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


def _pack_items(session: Session, pack: EvidencePack) -> list[EvidenceItemRead]:
    items: list[EvidenceItemRead] = []
    for item_id in pack.evidence_item_ids:
        item = session.get(EvidenceItem, uuid.UUID(item_id))
        if item is not None:
            items.append(_evidence_item_read(item))
    return items


def _validate_evidence_for_section(
    session: Session,
    *,
    section: OutlineNode,
    evidence_item_ids: list[uuid.UUID],
) -> None:
    for item_id in evidence_item_ids:
        item = get_or_404(session, EvidenceItem, item_id, "Evidence item")
        if item.paper_id != section.paper_id:
            raise HTTPException(
                status_code=400,
                detail="Evidence items must belong to the same paper as the section.",
            )


@router.post(
    "/papers/{paper_id}/sources",
    response_model=SourceMaterialRead,
    status_code=status.HTTP_201_CREATED,
)
def register_source_material(
    paper_id: uuid.UUID,
    payload: SourceMaterialCreate,
    session: Session = Depends(get_session),
) -> SourceMaterialRead:
    paper = get_or_404(session, Paper, paper_id, "Paper")
    source = SourceRegistry(session).register(paper, payload)
    return _source_material_read(source)


@router.get("/papers/{paper_id}/sources", response_model=list[SourceMaterialRead])
def list_source_material(
    paper_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[SourceMaterialRead]:
    get_or_404(session, Paper, paper_id, "Paper")
    sources = session.exec(
        select(SourceMaterial)
        .where(SourceMaterial.paper_id == paper_id)
        .order_by(SourceMaterial.created_at)
    ).all()
    return [_source_material_read(source) for source in sources]


@router.get("/sources/{source_id}", response_model=SourceMaterialRead)
def get_source_material(
    source_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> SourceMaterialRead:
    return _source_material_read(get_or_404(session, SourceMaterial, source_id, "Source material"))


@router.patch("/sources/{source_id}", response_model=SourceMaterialRead)
def update_source_material(
    source_id: uuid.UUID,
    payload: SourceMaterialUpdate,
    session: Session = Depends(get_session),
) -> SourceMaterialRead:
    source = get_or_404(session, SourceMaterial, source_id, "Source material")
    data = payload.model_dump(exclude_unset=True)
    if "metadata" in data:
        data["metadata_json"] = data.pop("metadata")
    return _source_material_read(update_item(session, source, data))


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source_material(
    source_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> Response:
    source = get_or_404(session, SourceMaterial, source_id, "Source material")
    delete_item(session, source)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sources/{source_id}/extract-evidence", response_model=EvidenceExtractionResponse)
def extract_source_evidence(
    source_id: uuid.UUID,
    payload: EvidenceExtractionRequest,
    session: Session = Depends(get_session),
) -> EvidenceExtractionResponse:
    source = get_or_404(session, SourceMaterial, source_id, "Source material")
    if payload.section_id is not None:
        section = get_or_404(session, OutlineNode, payload.section_id, "Section")
        if section.paper_id != source.paper_id:
            raise HTTPException(status_code=400, detail="Section must belong to the source paper.")
    items = EvidenceExtractor(session).extract(source, payload.section_id)
    return EvidenceExtractionResponse(
        source=_source_material_read(source),
        items=[_evidence_item_read(item) for item in items],
    )


@router.post(
    "/papers/{paper_id}/evidence/upload",
    response_model=list[EvidenceItemRead],
    status_code=status.HTTP_201_CREATED,
)
def upload_evidence_items(
    paper_id: uuid.UUID,
    payload: list[EvidenceItemForPaperCreate],
    session: Session = Depends(get_session),
) -> list[EvidenceItemRead]:
    get_or_404(session, Paper, paper_id, "Paper")
    created = []
    for item_payload in payload:
        data = item_payload.model_dump()
        metadata = data.pop("metadata", {})
        created.append(
            create_item(session, EvidenceItem(paper_id=paper_id, metadata_json=metadata, **data))
        )
    return [_evidence_item_read(item) for item in created]


@router.post(
    "/papers/{paper_id}/evidence",
    response_model=EvidenceItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_evidence_item(
    paper_id: uuid.UUID,
    payload: EvidenceItemForPaperCreate,
    session: Session = Depends(get_session),
) -> EvidenceItemRead:
    get_or_404(session, Paper, paper_id, "Paper")
    if payload.section_id is not None:
        section = get_or_404(session, OutlineNode, payload.section_id, "Section")
        if section.paper_id != paper_id:
            raise HTTPException(status_code=400, detail="Section must belong to the paper.")
    data = payload.model_dump()
    metadata = data.pop("metadata", {})
    item = create_item(session, EvidenceItem(paper_id=paper_id, metadata_json=metadata, **data))
    return _evidence_item_read(item)


@router.get("/papers/{paper_id}/evidence", response_model=list[EvidenceItemRead])
def list_paper_evidence(
    paper_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[EvidenceItemRead]:
    get_or_404(session, Paper, paper_id, "Paper")
    items = session.exec(
        select(EvidenceItem).where(EvidenceItem.paper_id == paper_id).order_by(EvidenceItem.created_at)
    ).all()
    return [_evidence_item_read(item) for item in items]


@router.get("/evidence/{evidence_id}", response_model=EvidenceItemRead)
def get_evidence_item(
    evidence_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> EvidenceItemRead:
    return _evidence_item_read(get_or_404(session, EvidenceItem, evidence_id, "Evidence item"))


@router.patch("/evidence/{evidence_id}", response_model=EvidenceItemRead)
def update_evidence_item(
    evidence_id: uuid.UUID,
    payload: EvidenceItemUpdate,
    session: Session = Depends(get_session),
) -> EvidenceItemRead:
    item = get_or_404(session, EvidenceItem, evidence_id, "Evidence item")
    data = payload.model_dump(exclude_unset=True)
    if data.get("section_id") is not None:
        section = get_or_404(session, OutlineNode, data["section_id"], "Section")
        if section.paper_id != item.paper_id:
            raise HTTPException(status_code=400, detail="Section must belong to the evidence paper.")
    if "metadata" in data:
        data["metadata_json"] = data.pop("metadata")
    return _evidence_item_read(update_item(session, item, data))


@router.delete("/evidence/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence_item(
    evidence_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> Response:
    item = get_or_404(session, EvidenceItem, evidence_id, "Evidence item")
    delete_item(session, item)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/sections/{section_id}/evidence-packs",
    response_model=EvidencePackRead,
    status_code=status.HTTP_201_CREATED,
)
def create_evidence_pack(
    section_id: uuid.UUID,
    payload: EvidencePackForSectionCreate,
    session: Session = Depends(get_session),
) -> EvidencePackRead:
    section = get_or_404(session, OutlineNode, section_id, "Section")
    _validate_evidence_for_section(
        session,
        section=section,
        evidence_item_ids=payload.evidence_item_ids,
    )
    if not payload.evidence_item_ids:
        raise HTTPException(status_code=400, detail="Evidence pack must contain at least one item.")
    data = payload.model_dump()
    data["evidence_item_ids"] = [str(item_id) for item_id in data["evidence_item_ids"]]
    pack = create_item(session, EvidencePack(section_id=section_id, **data))
    return _evidence_pack_read(pack)


@router.get("/sections/{section_id}/evidence-packs", response_model=list[EvidencePackRead])
def list_section_evidence_packs(
    section_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[EvidencePackRead]:
    get_or_404(session, OutlineNode, section_id, "Section")
    packs = session.exec(
        select(EvidencePack).where(EvidencePack.section_id == section_id).order_by(EvidencePack.created_at)
    ).all()
    return [_evidence_pack_read(pack) for pack in packs]


@router.get("/sections/{section_id}/evidence-pack", response_model=EvidencePackRead | None)
def get_active_section_evidence_pack(
    section_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> EvidencePackRead | None:
    get_or_404(session, OutlineNode, section_id, "Section")
    pack = session.exec(
        select(EvidencePack)
        .where(
            EvidencePack.section_id == section_id,
            EvidencePack.status == ArtifactStatus.ACTIVE,
        )
        .order_by(EvidencePack.created_at)
    ).first()
    return _evidence_pack_read(pack) if pack else None


@router.post("/sections/{section_id}/build-evidence-pack", response_model=EvidencePackBuildResponse)
def build_section_evidence_pack(
    section_id: uuid.UUID,
    payload: EvidencePackBuildRequest,
    session: Session = Depends(get_session),
) -> EvidencePackBuildResponse:
    section = get_or_404(session, OutlineNode, section_id, "Section")
    pack = EvidencePackBuilder(session).build(section, payload)
    return EvidencePackBuildResponse(
        section_id=section_id,
        pack=_evidence_pack_read(pack),
        items=_pack_items(session, pack),
    )


@router.post("/sections/{section_id}/verify-evidence", response_model=EvidenceVerificationResponse)
def verify_section_evidence(
    section_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> EvidenceVerificationResponse:
    section = get_or_404(session, OutlineNode, section_id, "Section")
    return EvidenceVerificationService(session).verify_section(section)


@router.get("/evidence-packs/{pack_id}", response_model=EvidencePackRead)
def get_evidence_pack(pack_id: uuid.UUID, session: Session = Depends(get_session)) -> EvidencePackRead:
    return _evidence_pack_read(get_or_404(session, EvidencePack, pack_id, "Evidence pack"))


@router.patch("/evidence-packs/{pack_id}", response_model=EvidencePackRead)
def update_evidence_pack(
    pack_id: uuid.UUID,
    payload: EvidencePackUpdate,
    session: Session = Depends(get_session),
) -> EvidencePackRead:
    pack = get_or_404(session, EvidencePack, pack_id, "Evidence pack")
    data = payload.model_dump(exclude_unset=True)
    if "evidence_item_ids" in data:
        section = get_or_404(session, OutlineNode, pack.section_id, "Section")
        _validate_evidence_for_section(
            session,
            section=section,
            evidence_item_ids=data["evidence_item_ids"],
        )
        if (
            pack.status == ArtifactStatus.ACTIVE
            and section.status == SectionStatus.EVIDENCE_READY
            and not data["evidence_item_ids"]
        ):
            raise HTTPException(
                status_code=400,
                detail="Cannot empty the active evidence pack for an evidence_ready section.",
            )
        data["evidence_item_ids"] = [str(item_id) for item_id in data["evidence_item_ids"]]
    return _evidence_pack_read(update_item(session, pack, data))


@router.post("/evidence-packs/{pack_id}/items", response_model=EvidencePackRead)
def add_evidence_pack_item(
    pack_id: uuid.UUID,
    payload: EvidencePackMembershipUpdate,
    session: Session = Depends(get_session),
) -> EvidencePackRead:
    pack = get_or_404(session, EvidencePack, pack_id, "Evidence pack")
    section = get_or_404(session, OutlineNode, pack.section_id, "Section")
    _validate_evidence_for_section(
        session,
        section=section,
        evidence_item_ids=[payload.evidence_item_id],
    )
    item_id = str(payload.evidence_item_id)
    if item_id not in pack.evidence_item_ids:
        pack.evidence_item_ids = [*pack.evidence_item_ids, item_id]
    return _evidence_pack_read(update_item(session, pack, {"evidence_item_ids": pack.evidence_item_ids}))


@router.delete("/evidence-packs/{pack_id}/items/{evidence_id}", response_model=EvidencePackRead)
def remove_evidence_pack_item(
    pack_id: uuid.UUID,
    evidence_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> EvidencePackRead:
    pack = get_or_404(session, EvidencePack, pack_id, "Evidence pack")
    section = get_or_404(session, OutlineNode, pack.section_id, "Section")
    item_id = str(evidence_id)
    if item_id not in pack.evidence_item_ids:
        raise HTTPException(status_code=404, detail="Evidence item is not in this pack.")
    if (
        pack.status == ArtifactStatus.ACTIVE
        and section.status == SectionStatus.EVIDENCE_READY
        and len(pack.evidence_item_ids) == 1
    ):
        raise HTTPException(
            status_code=400,
            detail="Cannot remove the last item from an evidence_ready section pack.",
        )
    next_ids = [existing_id for existing_id in pack.evidence_item_ids if existing_id != item_id]
    return _evidence_pack_read(update_item(session, pack, {"evidence_item_ids": next_ids}))


@router.delete("/evidence-packs/{pack_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence_pack(pack_id: uuid.UUID, session: Session = Depends(get_session)) -> Response:
    pack = get_or_404(session, EvidencePack, pack_id, "Evidence pack")
    delete_item(session, pack)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
