"""Source material registration for Milestone 3."""

from sqlmodel import Session

from app.models import Paper, SourceMaterial
from app.schemas.evidence import SourceMaterialCreate


class SourceRegistry:
    """Registers text-backed source material without real file upload handling."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def register(self, paper: Paper, payload: SourceMaterialCreate) -> SourceMaterial:
        data = payload.model_dump()
        metadata = data.pop("metadata", {})
        source = SourceMaterial(paper_id=paper.id, metadata_json=metadata, **data)
        self.session.add(source)
        self.session.commit()
        self.session.refresh(source)
        return source
