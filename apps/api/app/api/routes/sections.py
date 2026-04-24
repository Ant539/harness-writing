"""Outline section and contract CRUD routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.api.deps import get_session
from app.models import EvidencePack, OutlineNode, Paper, SectionContract
from app.models.enums import ArtifactStatus, SectionStatus
from app.schemas.contracts import (
    ContractGenerationRequest,
    ContractGenerationResponse,
    SectionContractForSectionCreate,
    SectionContractRead,
    SectionContractUpdate,
)
from app.schemas.outlines import (
    OutlineNodeCreate,
    OutlineNodeRead,
    OutlineNodeUpdate,
    PaperOutlineNodeCreate,
    SectionTransition,
)
from app.services.crud import create_item, delete_item, get_or_404, update_item
from app.services.planner import ContractGenerator
from app.state_machine import InvalidStateTransition, validate_section_transition

router = APIRouter(tags=["sections"])


def _validate_parent(
    session: Session,
    *,
    paper_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    section_id: uuid.UUID | None = None,
) -> None:
    if parent_id is None:
        return
    if section_id is not None and parent_id == section_id:
        raise HTTPException(status_code=400, detail="A section cannot be its own parent.")
    parent = get_or_404(session, OutlineNode, parent_id, "Parent section")
    if parent.paper_id != paper_id:
        raise HTTPException(status_code=400, detail="Parent section must belong to the same paper.")


def _validate_evidence_ready_guard(session: Session, section: OutlineNode) -> None:
    contract = session.exec(
        select(SectionContract).where(SectionContract.section_id == section.id)
    ).first()
    if contract is None:
        raise HTTPException(
            status_code=400,
            detail="Section must have a contract before moving to evidence_ready.",
        )

    pack = session.exec(
        select(EvidencePack).where(
            EvidencePack.section_id == section.id,
            EvidencePack.status == ArtifactStatus.ACTIVE,
        )
    ).first()
    if pack is None or not pack.evidence_item_ids:
        raise HTTPException(
            status_code=400,
            detail="Section must have an active evidence pack with at least one item.",
        )


@router.post("/sections", response_model=OutlineNodeRead, status_code=status.HTTP_201_CREATED)
def create_section(payload: OutlineNodeCreate, session: Session = Depends(get_session)) -> OutlineNode:
    get_or_404(session, Paper, payload.paper_id, "Paper")
    _validate_parent(session, paper_id=payload.paper_id, parent_id=payload.parent_id)
    return create_item(session, OutlineNode(**payload.model_dump()))


@router.post(
    "/papers/{paper_id}/sections",
    response_model=OutlineNodeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_paper_section(
    paper_id: uuid.UUID,
    payload: PaperOutlineNodeCreate,
    session: Session = Depends(get_session),
) -> OutlineNode:
    get_or_404(session, Paper, paper_id, "Paper")
    _validate_parent(session, paper_id=paper_id, parent_id=payload.parent_id)
    return create_item(session, OutlineNode(paper_id=paper_id, **payload.model_dump()))


@router.get("/papers/{paper_id}/sections", response_model=list[OutlineNodeRead])
def list_paper_sections(paper_id: uuid.UUID, session: Session = Depends(get_session)) -> list[OutlineNode]:
    get_or_404(session, Paper, paper_id, "Paper")
    return list(
        session.exec(
            select(OutlineNode)
            .where(OutlineNode.paper_id == paper_id)
            .order_by(OutlineNode.level, OutlineNode.order_index)
        ).all()
    )


@router.get("/sections/{section_id}", response_model=OutlineNodeRead)
def get_section(section_id: uuid.UUID, session: Session = Depends(get_session)) -> OutlineNode:
    return get_or_404(session, OutlineNode, section_id, "Section")


@router.patch("/sections/{section_id}", response_model=OutlineNodeRead)
def update_section(
    section_id: uuid.UUID,
    payload: OutlineNodeUpdate,
    session: Session = Depends(get_session),
) -> OutlineNode:
    section = get_or_404(session, OutlineNode, section_id, "Section")
    data = payload.model_dump(exclude_unset=True)
    if "parent_id" in data:
        _validate_parent(
            session,
            paper_id=section.paper_id,
            parent_id=data["parent_id"],
            section_id=section.id,
        )
    target_status = data.get("status")
    if target_status is not None:
        if target_status == SectionStatus.EVIDENCE_READY:
            _validate_evidence_ready_guard(session, section)
        try:
            validate_section_transition(section.status, target_status)
        except InvalidStateTransition as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return update_item(session, section, data)


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_section(section_id: uuid.UUID, session: Session = Depends(get_session)) -> Response:
    section = get_or_404(session, OutlineNode, section_id, "Section")
    delete_item(session, section)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sections/{section_id}/transition", response_model=OutlineNodeRead)
def transition_section(
    section_id: uuid.UUID,
    payload: SectionTransition,
    session: Session = Depends(get_session),
) -> OutlineNode:
    section = get_or_404(session, OutlineNode, section_id, "Section")
    if payload.status == SectionStatus.EVIDENCE_READY:
        _validate_evidence_ready_guard(session, section)
    try:
        validate_section_transition(section.status, payload.status)
    except InvalidStateTransition as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return update_item(session, section, {"status": payload.status})


@router.post("/sections/{section_id}/generate-contract", response_model=ContractGenerationResponse)
def generate_section_contract(
    section_id: uuid.UUID,
    payload: ContractGenerationRequest,
    session: Session = Depends(get_session),
) -> ContractGenerationResponse:
    section = get_or_404(session, OutlineNode, section_id, "Section")
    paper = get_or_404(session, Paper, section.paper_id, "Paper")
    contract = ContractGenerator(session).generate(paper, section, payload)
    return ContractGenerationResponse(section=section, contract=contract)


@router.post(
    "/sections/{section_id}/contract",
    response_model=SectionContractRead,
    status_code=status.HTTP_201_CREATED,
)
def create_section_contract(
    section_id: uuid.UUID,
    payload: SectionContractForSectionCreate,
    session: Session = Depends(get_session),
) -> SectionContract:
    section = get_or_404(session, OutlineNode, section_id, "Section")
    existing = session.exec(
        select(SectionContract).where(SectionContract.section_id == section_id)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Section contract already exists.")
    contract = SectionContract(section_id=section_id, **payload.model_dump())
    session.add(contract)
    if section.status == SectionStatus.PLANNED:
        try:
            validate_section_transition(section.status, SectionStatus.CONTRACT_READY)
        except InvalidStateTransition as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        section.status = SectionStatus.CONTRACT_READY
        session.add(section)
    session.commit()
    session.refresh(contract)
    return contract


@router.get("/sections/{section_id}/contract", response_model=SectionContractRead | None)
def get_section_contract(
    section_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> SectionContract | None:
    get_or_404(session, OutlineNode, section_id, "Section")
    return session.exec(
        select(SectionContract).where(SectionContract.section_id == section_id)
    ).first()


@router.get("/contracts/{contract_id}", response_model=SectionContractRead)
def get_contract(contract_id: uuid.UUID, session: Session = Depends(get_session)) -> SectionContract:
    return get_or_404(session, SectionContract, contract_id, "Section contract")


@router.patch("/contracts/{contract_id}", response_model=SectionContractRead)
def update_contract(
    contract_id: uuid.UUID,
    payload: SectionContractUpdate,
    session: Session = Depends(get_session),
) -> SectionContract:
    contract = get_or_404(session, SectionContract, contract_id, "Section contract")
    return update_item(session, contract, payload.model_dump(exclude_unset=True))


@router.delete("/contracts/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contract(contract_id: uuid.UUID, session: Session = Depends(get_session)) -> Response:
    contract = get_or_404(session, SectionContract, contract_id, "Section contract")
    delete_item(session, contract)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
