"""Deterministic manuscript assembly for Milestone 5.

TODO(real-editor): add locked-section selection and richer section rendering once
approval and paragraph-level draft workflows exist.
"""

from dataclasses import dataclass

from app.models import DraftUnit, OutlineNode, Paper


@dataclass(frozen=True)
class AssembledContent:
    """Rendered manuscript text and section traceability metadata."""

    content: str
    included_section_ids: list[str]
    missing_section_ids: list[str]
    warnings: list[str]


class ManuscriptAssembler:
    """Renders a full manuscript from outline order and current section drafts."""

    def assemble(
        self,
        *,
        paper: Paper,
        sections: list[OutlineNode],
        active_drafts_by_section: dict[str, DraftUnit],
    ) -> AssembledContent:
        content_blocks = [f"# {paper.title}"]
        included: list[str] = []
        missing: list[str] = []
        warnings: list[str] = []

        for section in sections:
            heading_level = max(2, min(section.level + 1, 6))
            content_blocks.append(f"{'#' * heading_level} {section.title}")
            draft = active_drafts_by_section.get(str(section.id))
            if draft is None:
                missing.append(str(section.id))
                warnings.append(f"Section '{section.title}' has no current active draft.")
                content_blocks.append("_[Missing current draft for this section.]_")
                continue
            included.append(str(section.id))
            content_blocks.append(draft.content.strip())

        return AssembledContent(
            content="\n\n".join(content_blocks).strip() + "\n",
            included_section_ids=included,
            missing_section_ids=missing,
            warnings=warnings,
        )
