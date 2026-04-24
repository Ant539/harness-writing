"""Prompt execution logging utilities."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlmodel import Session, select

from app.models import Paper, PromptExecutionLog
from app.models.enums import PromptStage
from app.schemas.prompts import PromptExecutionLogRead
from app.services.crud import get_or_404


class PromptLoggingService:
    """Persist prompt inputs, outputs, and version metadata for auditability."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_log(
        self,
        *,
        paper_id: uuid.UUID,
        stage: PromptStage,
        system_prompt: str | None,
        user_prompt: str | None,
        status: str = "completed",
        planning_run_id: uuid.UUID | None = None,
        workflow_run_id: uuid.UUID | None = None,
        prompt_assembly_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
        provider: str | None = None,
        model_name: str | None = None,
        prompt_version: int | None = None,
        prompt_pack_version: str | None = None,
        module_keys: list[str] | None = None,
        request_metadata: dict[str, Any] | None = None,
        response_text: str | None = None,
        error_message: str | None = None,
    ) -> PromptExecutionLog:
        log = PromptExecutionLog(
            paper_id=paper_id,
            planning_run_id=planning_run_id,
            workflow_run_id=workflow_run_id,
            prompt_assembly_id=prompt_assembly_id,
            section_id=section_id,
            stage=stage,
            provider=provider,
            model_name=model_name,
            status=status,
            prompt_hash=self.prompt_hash(system_prompt, user_prompt),
            prompt_version=prompt_version,
            prompt_pack_version=prompt_pack_version,
            module_keys=list(module_keys or []),
            request_metadata_json=dict(request_metadata or {}),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_text=response_text,
            error_message=error_message,
        )
        self.session.add(log)
        self.session.commit()
        self.session.refresh(log)
        return log

    def get_log(self, log_id: uuid.UUID) -> PromptExecutionLog:
        return get_or_404(self.session, PromptExecutionLog, log_id, "Prompt execution log")

    def list_logs_for_paper(
        self,
        paper_id: uuid.UUID,
        *,
        stage: PromptStage | None = None,
    ) -> list[PromptExecutionLog]:
        get_or_404(self.session, Paper, paper_id, "Paper")
        query = select(PromptExecutionLog).where(PromptExecutionLog.paper_id == paper_id)
        if stage is not None:
            query = query.where(PromptExecutionLog.stage == stage)
        return list(self.session.exec(query.order_by(PromptExecutionLog.created_at.desc())).all())

    def log_read(self, log: PromptExecutionLog) -> PromptExecutionLogRead:
        return PromptExecutionLogRead(
            id=log.id,
            paper_id=log.paper_id,
            planning_run_id=log.planning_run_id,
            workflow_run_id=log.workflow_run_id,
            prompt_assembly_id=log.prompt_assembly_id,
            section_id=log.section_id,
            stage=log.stage,
            provider=log.provider,
            model_name=log.model_name,
            status=log.status,
            prompt_hash=log.prompt_hash,
            prompt_version=log.prompt_version,
            prompt_pack_version=log.prompt_pack_version,
            module_keys=log.module_keys,
            request_metadata=log.request_metadata_json,
            system_prompt=log.system_prompt,
            user_prompt=log.user_prompt,
            response_text=log.response_text,
            error_message=log.error_message,
            created_at=log.created_at,
        )

    def prompt_hash(self, system_prompt: str | None, user_prompt: str | None) -> str:
        payload = f"{system_prompt or ''}\n---USER---\n{user_prompt or ''}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
