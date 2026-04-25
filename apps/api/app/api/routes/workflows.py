"""Workflow runner routes."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.api.deps import get_session
from app.schemas.workflows import (
    WorkflowRunDetailRead,
    WorkflowRunRead,
    WorkflowRunResumeRequest,
    WorkflowRunResumeResponse,
    WorkflowRunStartRequest,
    WorkflowRunStartResponse,
    WorkflowStepRetryRequest,
    WorkflowStepRetryResponse,
)
from app.services.workflows import WorkflowRunnerService

router = APIRouter(tags=["workflows"])


@router.post(
    "/papers/{paper_id}/workflow-runs",
    response_model=WorkflowRunStartResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_workflow_run(
    paper_id: uuid.UUID,
    payload: WorkflowRunStartRequest,
    session: Session = Depends(get_session),
) -> WorkflowRunStartResponse:
    service = WorkflowRunnerService(session)
    run = service.start_run(paper_id, payload)
    discovery = service.planning_service.get_latest_discovery(paper_id)
    plan = service.planning_service.get_latest_plan(paper_id)
    return WorkflowRunStartResponse(
        workflow_run=service.workflow_run_detail_read(run),
        discovery=service.planning_service.discovery_read(discovery) if discovery is not None else None,
        plan=service.planning_service.planning_run_read(plan) if plan is not None else None,
    )


@router.get("/papers/{paper_id}/workflow-runs", response_model=list[WorkflowRunRead])
def list_workflow_runs(
    paper_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[WorkflowRunRead]:
    service = WorkflowRunnerService(session)
    return [service.workflow_run_read(run) for run in service.list_runs_for_paper(paper_id)]


@router.get("/workflow-runs/{run_id}", response_model=WorkflowRunDetailRead)
def get_workflow_run(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> WorkflowRunDetailRead:
    service = WorkflowRunnerService(session)
    run = service.get_run(run_id)
    return service.workflow_run_detail_read(run)


@router.post("/workflow-runs/{run_id}/resume", response_model=WorkflowRunResumeResponse)
def resume_workflow_run(
    run_id: uuid.UUID,
    payload: WorkflowRunResumeRequest,
    session: Session = Depends(get_session),
) -> WorkflowRunResumeResponse:
    service = WorkflowRunnerService(session)
    run = service.resume_run(run_id, payload)
    discovery = service.planning_service.get_latest_discovery(run.paper_id)
    plan = service.planning_service.get_latest_plan(run.paper_id)
    return WorkflowRunResumeResponse(
        workflow_run=service.workflow_run_detail_read(run),
        discovery=service.planning_service.discovery_read(discovery) if discovery is not None else None,
        plan=service.planning_service.planning_run_read(plan) if plan is not None else None,
    )


@router.post("/workflow-steps/{step_id}/retry", response_model=WorkflowStepRetryResponse)
def retry_workflow_step(
    step_id: uuid.UUID,
    payload: WorkflowStepRetryRequest,
    session: Session = Depends(get_session),
) -> WorkflowStepRetryResponse:
    service = WorkflowRunnerService(session)
    run, retried_step, plan = service.retry_step(step_id, payload)
    return WorkflowStepRetryResponse(
        workflow_run=service.workflow_run_detail_read(run),
        retried_step=service.workflow_step_read(retried_step),
        plan=service.planning_service.planning_run_read(plan) if plan is not None else None,
    )
