"""General writer role for Writing Harness."""

from app.schemas.writing_harness import Draft, Outline, WritingBrief


class Writer:
    """Generate lightweight and structured non-academic drafts."""

    def rewrite_text(self, text: str, tone: str) -> str:
        cleaned = " ".join(text.strip().split())
        if tone.lower() in {"polite", "礼貌", "more polite"}:
            return f"Thank you for your time. {cleaned} I would appreciate your guidance."
        return cleaned

    def draft_from_brief(self, brief: WritingBrief) -> Draft:
        content = (
            f"{brief.topic}\n\n"
            f"This draft is written for {brief.audience}. It aims to {brief.goal}.\n\n"
            "Key point: the current version keeps factual claims conservative and marks anything "
            "that would require external verification before publication."
        )
        return Draft(content=content, known_issues=list(brief.open_questions))

    def draft_from_outline(self, brief: WritingBrief, outline: Outline | None) -> Draft:
        sections: dict[str, str] = {}
        for section in outline.sections if outline is not None else []:
            source_note = " [SOURCE NEEDED]" if section.required_sources else ""
            sections[section.title] = (
                f"{section.title}\n\n{section.section_goal}{source_note}\n"
                f"This section should support the goal: {brief.goal}"
            )
        content = "\n\n".join(sections.values()) or self.draft_from_brief(brief).content
        issues = ["Some factual claims require verification."] if brief.research_required else []
        return Draft(
            content=content,
            sections=sections,
            known_issues=issues,
            created_from_outline_id=outline.outline_id if outline is not None else None,
        )
