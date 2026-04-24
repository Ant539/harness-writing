"""Discovery and planning routes."""

import uuid

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.deps import get_session
from app.schemas.planning import DiscoveryCreate, DiscoveryRead, PlanningRunCreate, PlanningRunRead
from app.services.planner import WorkflowPlanningService

router = APIRouter(prefix="/papers", tags=["planning"])


@router.post("/{paper_id}/discovery", response_model=DiscoveryRead)
def save_discovery(
    paper_id: uuid.UUID,
    payload: DiscoveryCreate,
    session: Session = Depends(get_session),
) -> DiscoveryRead:
    service = WorkflowPlanningService(session)
    discovery = service.save_discovery(paper_id, payload)
    return service.discovery_read(discovery)


@router.get("/{paper_id}/discovery", response_model=DiscoveryRead | None)
def get_latest_discovery(
    paper_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> DiscoveryRead | None:
    service = WorkflowPlanningService(session)
    discovery = service.get_latest_discovery(paper_id)
    if discovery is None:
        return None
    return service.discovery_read(discovery)


@router.post("/{paper_id}/plan", response_model=PlanningRunRead)
def generate_plan(
    paper_id: uuid.UUID,
    payload: PlanningRunCreate,
    session: Session = Depends(get_session),
) -> PlanningRunRead:
    service = WorkflowPlanningService(session)
    plan = service.generate_plan(paper_id, payload)
    return service.planning_run_read(plan)


@router.get("/{paper_id}/plan", response_model=PlanningRunRead | None)
def get_latest_plan(
    paper_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> PlanningRunRead | None:
    service = WorkflowPlanningService(session)
    plan = service.get_latest_plan(paper_id)
    if plan is None:
        return None
    return service.planning_run_read(plan)
