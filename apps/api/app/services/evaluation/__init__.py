"""Evaluation services for prompt and writing-quality development."""

from app.services.evaluation.academic import (
    AcademicEvalCase,
    AcademicPaperEvaluation,
    AcademicPaperEvaluator,
    DimensionScore,
)

__all__ = [
    "AcademicEvalCase",
    "AcademicPaperEvaluation",
    "AcademicPaperEvaluator",
    "DimensionScore",
]
