"""Assembly, global review, and export schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.models.enums import ArtifactStatus, ExportFormat, ManuscriptIssueType, Severity
from app.schemas.common import ApiSchema
from app.schemas.papers import PaperRead


class AssembledManuscriptBase(ApiSchema):
    version: int = 1
    content: str
    included_section_ids: list[uuid.UUID] = []
    missing_section_ids: list[uuid.UUID] = []
    warnings: list[str] = []
    status: ArtifactStatus = ArtifactStatus.ACTIVE


class AssembledManuscriptRead(AssembledManuscriptBase):
    id: uuid.UUID
    paper_id: uuid.UUID
    created_at: datetime


class ManuscriptAssemblyRequest(ApiSchema):
    include_unlocked: bool = True


class ManuscriptAssemblyResponse(ApiSchema):
    paper: PaperRead
    manuscript: AssembledManuscriptRead


class ManuscriptIssueBase(ApiSchema):
    issue_type: ManuscriptIssueType
    severity: Severity = Severity.MEDIUM
    message: str
    suggested_action: str
    resolved: bool = False


class ManuscriptIssueRead(ManuscriptIssueBase):
    id: uuid.UUID
    paper_id: uuid.UUID
    manuscript_id: uuid.UUID
    created_at: datetime


class GlobalReviewRequest(ApiSchema):
    review_instructions: str | None = None


class GlobalReviewResponse(ApiSchema):
    paper: PaperRead
    manuscript: AssembledManuscriptRead
    issues: list[ManuscriptIssueRead]


class LatexExportOptions(ApiSchema):
    document_class: str = "article"
    author: str | None = None
    abstract: str | None = None
    include_table_of_contents: bool = False
    citation_command: str = "citep"
    bibliography_style: str | None = "plainnat"
    bibliography_file: str | None = None
    extra_packages: list[str] = Field(default_factory=list)


class ManuscriptExportRequest(ApiSchema):
    export_format: ExportFormat = ExportFormat.MARKDOWN
    latex: LatexExportOptions = Field(default_factory=LatexExportOptions)
    write_file: bool = False


class ExportArtifactRead(ApiSchema):
    id: uuid.UUID
    paper_id: uuid.UUID
    manuscript_id: uuid.UUID
    version: int
    export_format: ExportFormat
    content: str
    artifact_path: str
    status: ArtifactStatus
    created_at: datetime


class ManuscriptExportResponse(ApiSchema):
    paper: PaperRead
    manuscript: AssembledManuscriptRead
    export: ExportArtifactRead
