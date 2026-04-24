"""Research service package."""

from app.services.research.evidence_extractor import EvidenceExtractor
from app.services.research.evidence_pack_builder import EvidencePackBuilder
from app.services.research.source_registry import SourceRegistry


class ResearcherService:
    """Facade for deterministic research behavior used before LLM integration."""

    source_registry = SourceRegistry
    evidence_extractor = EvidenceExtractor
    evidence_pack_builder = EvidencePackBuilder


__all__ = ["EvidenceExtractor", "EvidencePackBuilder", "ResearcherService", "SourceRegistry"]
