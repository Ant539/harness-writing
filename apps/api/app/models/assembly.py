"""Manuscript assembly, global review, and export models."""

import uuid
from datetime import datetime

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from app.models.base import utc_now
from app.models.enums import ArtifactStatus, ExportFormat, ManuscriptIssueType, Severity


class AssembledManuscript(SQLModel, table=True):
    __tablename__ = "assembled_manuscripts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    version: int = 1
    content: str
    included_section_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    missing_section_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    warnings: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: ArtifactStatus = Field(default=ArtifactStatus.ACTIVE, index=True)
    created_at: datetime = Field(default_factory=utc_now)


class ManuscriptIssue(SQLModel, table=True):
    __tablename__ = "manuscript_issues"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    manuscript_id: uuid.UUID = Field(foreign_key="assembled_manuscripts.id", index=True)
    issue_type: ManuscriptIssueType
    severity: Severity = Severity.MEDIUM
    message: str
    suggested_action: str
    resolved: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class ExportArtifact(SQLModel, table=True):
    __tablename__ = "export_artifacts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paper_id: uuid.UUID = Field(foreign_key="papers.id", index=True)
    manuscript_id: uuid.UUID = Field(foreign_key="assembled_manuscripts.id", index=True)
    version: int = 1
    export_format: ExportFormat = Field(index=True)
    content: str
    artifact_path: str
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: ArtifactStatus = Field(default=ArtifactStatus.ACTIVE, index=True)
    created_at: datetime = Field(default_factory=utc_now)
