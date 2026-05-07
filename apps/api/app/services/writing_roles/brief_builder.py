"""Brief-building role for Writing Harness."""

import re

from app.schemas.writing_harness import (
    AcademicBrief,
    TaskRoute,
    WritingBrief,
    WritingHarnessRunRequest,
)


class BriefBuilder:
    """Convert user input into a reusable writing brief."""

    def build(
        self,
        payload: WritingHarnessRunRequest,
        route: TaskRoute,
        *,
        quick: bool = False,
    ) -> WritingBrief:
        topic = self._infer_topic(payload.user_input)
        assumptions = []
        if not payload.audience:
            assumptions.append("Audience inferred from task type because no explicit audience was provided.")
        if not payload.length:
            assumptions.append("Length inferred conservatively from the requested deliverable.")
        return WritingBrief(
            topic=topic,
            goal=payload.user_input.strip(),
            audience=payload.audience or "General reader",
            deliverable_type="rewrite" if quick else route.task_type.value,
            language=payload.language or "English",
            tone=payload.tone or ("polite" if quick else "clear and direct"),
            length=payload.length or ("same length as source" if quick else "medium"),
            must_include=[],
            must_avoid=["unsupported factual certainty"],
            research_required=route.requires_research,
            citation_required=route.requires_citations,
            approval_points=[] if quick else ["Confirm brief assumptions before high-stakes publication."],
            assumptions=assumptions,
            open_questions=[],
        )

    def build_academic(
        self,
        payload: WritingHarnessRunRequest,
        route: TaskRoute,
    ) -> AcademicBrief:
        base = self.build(payload, route)
        text = payload.user_input
        open_questions = list(base.open_questions)
        if not self._mentions_research_question(text):
            open_questions.append("Confirm the exact research question before treating this as final.")
        if not payload.source_text:
            open_questions.append("Provide source material or approved references before citation-heavy drafting.")
        brief_payload = base.model_dump()
        brief_payload.update(
            {
                "deliverable_type": "academic paper",
                "research_required": True,
                "citation_required": True,
                "open_questions": open_questions,
            }
        )
        return AcademicBrief(
            **brief_payload,
            research_area=self._infer_research_area(text),
            research_question=self._extract_research_question(text),
            thesis_or_main_claim=None,
            target_venue=payload.target_venue or self._target_venue(text),
            paper_type=self._paper_type(text),
            expected_contribution=None,
            methodology="user-supplied or TBD",
            related_work_scope=self._related_work_scope(text),
            citation_style="venue-dependent",
            novelty_claims=[],
            limitations=["Evidence and citation coverage are incomplete until sources are provided."],
            ethical_considerations=[],
        )

    def _infer_topic(self, text: str) -> str:
        cleaned = " ".join(text.strip().split())
        return cleaned[:120] or "Untitled writing task"

    def _paper_type(self, text: str) -> str:
        lowered = text.lower()
        if "survey" in lowered or "综述" in lowered:
            return "survey"
        if "experiment" in lowered or "empirical" in lowered or "实验" in lowered:
            return "empirical paper"
        if "system" in lowered:
            return "system paper"
        if "method" in lowered or "方法" in lowered:
            return "method paper"
        return "position paper"

    def _target_venue(self, text: str) -> str | None:
        lowered = text.lower()
        if "workshop" in lowered:
            return "workshop"
        if "conference" in lowered:
            return "conference"
        if "journal" in lowered:
            return "journal"
        return None

    def _mentions_research_question(self, text: str) -> bool:
        lowered = text.lower()
        return "research question" in lowered or "rq" in lowered or "研究问题" in lowered

    def _extract_research_question(self, text: str) -> str | None:
        match = re.search(r"(research question|rq|研究问题)[:：]\s*([^。.!?\n]+)", text, re.IGNORECASE)
        return match.group(2).strip() if match else None

    def _infer_research_area(self, text: str) -> str | None:
        lowered = text.lower()
        if "llm" in lowered or "agent" in lowered:
            return "LLM agents"
        if "evaluation" in lowered:
            return "evaluation"
        return None

    def _related_work_scope(self, text: str) -> list[str]:
        lowered = text.lower()
        scopes = []
        if "agent" in lowered:
            scopes.append("LLM agent systems")
        if "evaluation" in lowered:
            scopes.append("LLM agent evaluation")
        if "writing" in lowered:
            scopes.append("writing agents")
        return scopes
