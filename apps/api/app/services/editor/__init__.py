"""Editor service boundary for manuscript assembly, review, and export."""

from app.services.editor.export_generator import ExportGenerator
from app.services.editor.manuscript_assembler import ManuscriptAssembler
from app.services.editor.manuscript_reviewer import ManuscriptReviewer


class EditorService:
    """Boundary object for Milestone 5 editor orchestration."""

    def __init__(self) -> None:
        self.assembler = ManuscriptAssembler()
        self.reviewer = ManuscriptReviewer()
        self.export_generator = ExportGenerator()


__all__ = ["EditorService", "ExportGenerator", "ManuscriptAssembler", "ManuscriptReviewer"]
