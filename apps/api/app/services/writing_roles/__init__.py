"""Logical role modules for the generic Writing Harness."""

from app.services.writing_roles.academic_reviewer import AcademicReviewer
from app.services.writing_roles.academic_writer import AcademicWriter
from app.services.writing_roles.brief_builder import BriefBuilder
from app.services.writing_roles.citation_checker import CitationChecker
from app.services.writing_roles.editor import Editor
from app.services.writing_roles.paper_bridge import PaperHarnessBridge
from app.services.writing_roles.planner import Planner
from app.services.writing_roles.reviewer import Reviewer
from app.services.writing_roles.router import TaskRouter
from app.services.writing_roles.writer import Writer

__all__ = [
    "AcademicReviewer",
    "AcademicWriter",
    "BriefBuilder",
    "CitationChecker",
    "Editor",
    "PaperHarnessBridge",
    "Planner",
    "Reviewer",
    "TaskRouter",
    "Writer",
]
