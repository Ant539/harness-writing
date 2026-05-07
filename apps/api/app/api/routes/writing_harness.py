"""Generic Writing Harness routes."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.api.deps import get_session
from app.schemas.writing_harness import WritingHarnessRunRead, WritingHarnessRunRequest
from app.services.writing_harness import WritingHarnessService

router = APIRouter(prefix="/writing-harness", tags=["writing-harness"])


@router.post(
    "/runs",
    response_model=WritingHarnessRunRead,
    status_code=status.HTTP_201_CREATED,
)
def start_writing_harness_run(
    payload: WritingHarnessRunRequest,
    session: Session = Depends(get_session),
) -> WritingHarnessRunRead:
    service = WritingHarnessService(session)
    run = service.run(payload)
    return service.run_read(run)


@router.get("/runs", response_model=list[WritingHarnessRunRead])
def list_writing_harness_runs(
    session: Session = Depends(get_session),
) -> list[WritingHarnessRunRead]:
    service = WritingHarnessService(session)
    return [service.run_read(run) for run in service.list_runs()]


@router.get("/runs/{run_id}", response_model=WritingHarnessRunRead)
def get_writing_harness_run(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> WritingHarnessRunRead:
    service = WritingHarnessService(session)
    return service.run_read(service.get_run(run_id))
