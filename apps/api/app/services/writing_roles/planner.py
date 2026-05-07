"""Planning role for Writing Harness."""

import re

from app.schemas.writing_harness import (
    AcademicBrief,
    ClaimEvidenceItem,
    ClaimEvidenceMap,
    Outline,
    OutlineSection,
    SourceNote,
    WritingBrief,
    WritingHarnessRunRequest,
    WritingTaskType,
)


class Planner:
    """Produce outlines, source notes, and academic claim maps."""

    def outline_for(self, brief: WritingBrief, task_type: WritingTaskType) -> Outline:
        if task_type == WritingTaskType.LONG_FORM_PROJECT:
            titles = ["Project Frame", "Part I", "Part II", "Synthesis", "Delivery Plan"]
        else:
            titles = ["Introduction", "Main Points", "Details", "Implications", "Conclusion"]
        return Outline(
            sections=[
                OutlineSection(
                    title=title,
                    section_goal=f"Develop {title.lower()} for {brief.topic}.",
                    key_points=[brief.goal],
                    required_sources=["verified source needed"] if brief.citation_required else [],
                    expected_claims=[],
                )
                for title in titles
            ]
        )

    def academic_outline(self, brief: AcademicBrief) -> Outline:
        if brief.paper_type == "survey":
            titles = [
                "Title",
                "Abstract",
                "Introduction",
                "Scope and Taxonomy",
                "Related Work",
                "Synthesis",
                "Limitations",
                "Conclusion",
                "References",
            ]
        elif brief.paper_type == "empirical paper":
            titles = [
                "Title",
                "Abstract",
                "Introduction",
                "Related Work",
                "Method",
                "Experiments / Evaluation",
                "Results",
                "Discussion",
                "Limitations",
                "Conclusion",
                "References",
            ]
        else:
            titles = [
                "Title",
                "Abstract",
                "Introduction",
                "Related Work",
                "Argument / Method",
                "Discussion",
                "Limitations",
                "Conclusion",
                "References",
            ]
        return Outline(
            outline_id="academic-outline-v1",
            sections=[
                OutlineSection(
                    title=title,
                    section_goal=self._academic_section_goal(title, brief),
                    key_points=[],
                    required_sources=["required before finalization"]
                    if title not in {"Title", "References"}
                    else [],
                    expected_claims=[],
                    status="planned",
                )
                for title in titles
            ],
        )

    def source_notes(self, payload: WritingHarnessRunRequest) -> list[SourceNote]:
        if not payload.source_text:
            return []
        sentences = self._sentences(payload.source_text)
        return [
            SourceNote(
                source_id="user-source-1",
                title="User-provided source material",
                key_points=sentences[:5],
                usable_for=["background", "argument support"],
                reliability="user_provided_unverified",
                limitations=["Metadata and citation details were not independently verified."],
                quoted_text=payload.source_text[:500],
                summary="User-provided material available for cautious drafting.",
            )
        ]

    def claim_map(self, brief: AcademicBrief, payload: WritingHarnessRunRequest) -> ClaimEvidenceMap:
        claims: list[ClaimEvidenceItem] = []
        base_claims = [
            ("claim-1", brief.research_question or f"The paper addresses {brief.topic}.", "background"),
            (
                "claim-2",
                brief.expected_contribution or "The expected contribution requires user confirmation.",
                "novelty",
            ),
        ]
        has_source = bool(payload.source_text)
        for claim_id, claim_text, claim_type in base_claims:
            claims.append(
                ClaimEvidenceItem(
                    claim_id=claim_id,
                    claim_text=claim_text,
                    claim_type=claim_type,
                    supporting_sources=["user-source-1"] if has_source else [],
                    supporting_evidence=["user-provided source text"] if has_source else [],
                    unsupported_risk="medium" if has_source else "high",
                    required_validation=[
                        "Confirm claim wording.",
                        "Attach verified source or user-approved evidence.",
                    ],
                    appears_in_sections=["Introduction", "Abstract"],
                    confidence=0.45 if has_source else 0.2,
                )
            )
        return ClaimEvidenceMap(claims=claims)

    def _sentences(self, text: str) -> list[str]:
        return [item.strip() for item in re.split(r"(?<=[.!?。！？])\s+", text) if item.strip()]

    def _academic_section_goal(self, title: str, brief: AcademicBrief) -> str:
        goals = {
            "Abstract": "Summarize the research question, contribution, method, evidence, and limitations without adding unsupported claims.",
            "Introduction": "Motivate the problem, define the gap, and state the research question conservatively.",
            "Related Work": "Position the paper against verified literature only.",
            "Method": "Describe user-confirmed method details with reproducibility in mind.",
            "Experiments / Evaluation": "Report only user-provided or validated experimental setup and results.",
            "Results": "Interpret validated results without overclaiming.",
            "Discussion": "Explain implications and uncertainty.",
            "Limitations": "State known evidence, method, and scope limits.",
            "Conclusion": "Conclude without introducing new unsupported claims.",
            "References": "Render only verified bibliographic records.",
        }
        return goals.get(title, f"Develop {title.lower()} for {brief.topic}.")
