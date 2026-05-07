"""Academic writer role for Writing Harness."""

from app.schemas.writing_harness import AcademicBrief, Draft, Outline, SourceNote


class AcademicWriter:
    """Generate conservative academic paper drafts from academic artifacts."""

    def draft(
        self,
        brief: AcademicBrief,
        outline: Outline,
        source_notes: list[SourceNote],
    ) -> Draft:
        has_sources = bool(source_notes)
        sections: dict[str, str] = {}
        citations = ["user-source-1"] if has_sources else []
        for section in outline.sections:
            if section.title == "References":
                body = (
                    "References\n\n"
                    "[REFERENCE LIST REQUIRED: add only verified bibliographic records. No fabricated citations.]"
                )
            elif section.title == "Title":
                body = f"Title\n\n{brief.topic}"
            else:
                support = "[supported by user-source-1]" if has_sources else "[UNSUPPORTED_CLAIM: source required]"
                body = (
                    f"{section.title}\n\n"
                    f"{section.section_goal}\n"
                    f"{support} Draft content is intentionally conservative. It should be expanded only with "
                    "verified sources, user-confirmed methods, or validated results.\n"
                    "[TODO: align each substantive claim with the ClaimEvidenceMap before final use.]"
                )
            sections[section.title] = body
        return Draft(
            content="\n\n".join(sections.values()),
            sections=sections,
            citations_used=citations,
            known_issues=[
                "No fabricated citations, datasets, benchmarks, experiments, or conclusions were introduced.",
                "Unsupported claims remain explicitly marked.",
            ],
            created_from_outline_id=outline.outline_id,
        )
