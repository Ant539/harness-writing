"""Deterministic source-to-evidence extraction for Milestone 3.

TODO(real-llm): replace sentence chunking with parser/retriever-backed evidence
extraction that keeps EvidenceItem provenance fields populated.
"""

import re

from sqlmodel import Session

from app.models import EvidenceItem, SourceMaterial


class EvidenceExtractor:
    """Converts registered source text into stable EvidenceItem records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def extract(self, source: SourceMaterial, section_id=None) -> list[EvidenceItem]:
        chunks = self._chunks(source.content)
        items: list[EvidenceItem] = []
        for index, chunk in enumerate(chunks, start=1):
            item = EvidenceItem(
                paper_id=source.paper_id,
                section_id=section_id,
                source_type=source.source_type,
                source_ref=source.source_ref or str(source.id),
                content=chunk,
                citation_key=source.citation_key,
                confidence=0.8,
                metadata_json={
                    "source_material_id": str(source.id),
                    "source_title": source.title,
                    "chunk_index": index,
                },
            )
            self.session.add(item)
            items.append(item)
        self.session.commit()
        for item in items:
            self.session.refresh(item)
        return items

    def _chunks(self, content: str) -> list[str]:
        normalized = " ".join(content.split())
        if not normalized:
            return []

        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", normalized)
            if sentence.strip()
        ]
        if not sentences:
            return [normalized]
        return sentences[:5]
