"""Prompt assembly routes."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from app.api.deps import get_session
from app.models.enums import PromptStage
from app.schemas.prompts import PromptAssemblyRead, PromptAssemblyRequest, PromptExecutionLogRead
from app.services.prompt_logging import PromptLoggingService
from app.services.prompt_assembly import PromptAssemblyService

router = APIRouter(tags=["prompts"])


@router.post(
    "/papers/{paper_id}/prompt-assemblies",
    response_model=PromptAssemblyRead,
    status_code=status.HTTP_201_CREATED,
)
def create_prompt_assembly(
    paper_id: uuid.UUID,
    payload: PromptAssemblyRequest,
    session: Session = Depends(get_session),
) -> PromptAssemblyRead:
    service = PromptAssemblyService(session)
    artifact = service.assemble(paper_id, payload)
    return service.prompt_assembly_read(artifact)


@router.get("/papers/{paper_id}/prompt-assemblies", response_model=list[PromptAssemblyRead])
def list_prompt_assemblies(
    paper_id: uuid.UUID,
    stage: PromptStage | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[PromptAssemblyRead]:
    service = PromptAssemblyService(session)
    return [service.prompt_assembly_read(item) for item in service.list_artifacts(paper_id, stage=stage)]


@router.get("/prompt-assemblies/{artifact_id}", response_model=PromptAssemblyRead)
def get_prompt_assembly(
    artifact_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> PromptAssemblyRead:
    service = PromptAssemblyService(session)
    artifact = service.get_artifact(artifact_id)
    return service.prompt_assembly_read(artifact)


@router.get("/papers/{paper_id}/prompt-logs", response_model=list[PromptExecutionLogRead])
def list_prompt_logs(
    paper_id: uuid.UUID,
    stage: PromptStage | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[PromptExecutionLogRead]:
    service = PromptLoggingService(session)
    return [service.log_read(item) for item in service.list_logs_for_paper(paper_id, stage=stage)]


@router.get("/prompt-logs/{log_id}", response_model=PromptExecutionLogRead)
def get_prompt_log(
    log_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> PromptExecutionLogRead:
    service = PromptLoggingService(session)
    return service.log_read(service.get_log(log_id))
