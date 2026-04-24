"""Schemas for importing existing LaTeX manuscripts."""

import uuid

from app.models.enums import PaperType
from app.schemas.common import ApiSchema
from app.schemas.drafts import DraftUnitRead
from app.schemas.evidence import SourceMaterialRead
from app.schemas.outlines import OutlineNodeRead
from app.schemas.papers import PaperRead


class LatexImportRequest(ApiSchema):
    latex_content: str
    source_path: str | None = None
    paper_type: PaperType = PaperType.CONCEPTUAL
    target_language: str = "English"
    target_venue: str | None = None


class LatexImportResponse(ApiSchema):
    paper: PaperRead
    source: SourceMaterialRead
    outline: list[OutlineNodeRead]
    drafts: list[DraftUnitRead]
    abstract: str | None = None
    keywords: list[str] = []
    imported_section_ids: list[uuid.UUID] = []
