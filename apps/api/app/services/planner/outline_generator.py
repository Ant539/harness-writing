"""Outline generation."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import OutlineNode, Paper
from app.models.enums import DocumentType, PaperStatus, PaperType
from app.schemas.outlines import OutlineGenerationRequest
from app.services.llm import LLMMessage, LLMProvider, LLMRequest, get_llm_provider
from app.services.llm.json_utils import parse_json_object
from app.services.llm.providers import LLMProviderError
from app.state_machine import InvalidStateTransition, validate_paper_transition


@dataclass(frozen=True)
class OutlineNodeSpec:
    title: str
    goal: str
    expected_claims: list[str]
    order_index: int
    children: tuple["OutlineNodeSpec", ...] = ()


class OutlineGenerator:
    """Creates outline nodes, using a configured model when available."""

    def __init__(self, session: Session, llm_provider: LLMProvider | None = None) -> None:
        self.session = session
        self.llm_provider = llm_provider if llm_provider is not None else get_llm_provider()

    def generate(self, paper: Paper, request: OutlineGenerationRequest) -> list[OutlineNode]:
        existing_nodes = self.session.exec(
            select(OutlineNode).where(OutlineNode.paper_id == paper.id)
        ).all()
        if existing_nodes:
            raise HTTPException(
                status_code=409,
                detail="Outline already exists. Edit existing outline nodes instead of regenerating.",
            )

        try:
            validate_paper_transition(paper.status, PaperStatus.OUTLINE_READY)
        except InvalidStateTransition as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        document_type = self._document_type_for(paper, request)
        target_word_count = request.target_word_count or self._default_word_count(
            paper.paper_type,
            document_type,
        )
        specs = list(self._outline_specs(paper, request))
        nodes = self._persist_specs(paper, specs, target_word_count, document_type)

        paper.status = PaperStatus.OUTLINE_READY
        paper.updated_at = datetime.now(timezone.utc)
        self.session.add(paper)
        self.session.commit()
        for node in nodes:
            self.session.refresh(node)
        self.session.refresh(paper)
        return nodes

    def _persist_specs(
        self,
        paper: Paper,
        specs: list[OutlineNodeSpec],
        target_word_count: int,
        document_type: DocumentType,
    ) -> list[OutlineNode]:
        created: list[OutlineNode] = []
        top_level_budget = max(target_word_count // max(len(specs), 1), 350)

        for spec in specs:
            parent = OutlineNode(
                paper_id=paper.id,
                title=spec.title,
                level=1,
                goal=spec.goal,
                expected_claims=spec.expected_claims,
                word_budget=top_level_budget,
                order_index=spec.order_index,
                metadata_json={"document_type": document_type.value, "section_role": spec.title.lower()},
            )
            self.session.add(parent)
            self.session.commit()
            self.session.refresh(parent)
            created.append(parent)

            child_budget = max(top_level_budget // max(len(spec.children), 1), 250)
            for child_spec in spec.children:
                child = OutlineNode(
                    paper_id=paper.id,
                    parent_id=parent.id,
                    title=child_spec.title,
                    level=2,
                    goal=child_spec.goal,
                    expected_claims=child_spec.expected_claims,
                    word_budget=child_budget,
                    order_index=child_spec.order_index,
                    metadata_json={
                        "document_type": document_type.value,
                        "section_role": child_spec.title.lower(),
                    },
                )
                self.session.add(child)
                self.session.commit()
                self.session.refresh(child)
                created.append(child)

        return created

    def _outline_specs(
        self,
        paper: Paper,
        request: OutlineGenerationRequest,
    ) -> Iterable[OutlineNodeSpec]:
        if self.llm_provider is not None:
            return self._llm_outline_specs(paper, request)
        topic = paper.title
        context = f" Context: {request.additional_context}" if request.additional_context else ""
        document_type = self._document_type_for(paper, request)
        if document_type == DocumentType.REPORT:
            return self._report_specs(topic, context)
        if document_type == DocumentType.THESIS:
            return self._thesis_specs(topic, context)
        if document_type == DocumentType.PROPOSAL:
            return self._proposal_specs(topic, context)
        if document_type == DocumentType.TECHNICAL_DOCUMENT:
            return self._technical_document_specs(topic, context)
        if paper.paper_type == PaperType.SURVEY:
            return self._survey_specs(topic, context)
        if paper.paper_type == PaperType.EMPIRICAL:
            return self._empirical_specs(topic, context)
        return self._conceptual_specs(topic, context)

    def _conceptual_specs(self, topic: str, context: str) -> list[OutlineNodeSpec]:
        return [
            OutlineNodeSpec(
                "Introduction",
                f"Frame the problem and contribution for {topic}.{context}",
                ["The paper addresses a clear conceptual problem."],
                1,
            ),
            OutlineNodeSpec(
                "Conceptual Background",
                "Define the core concepts and assumptions needed for the argument.",
                ["The paper uses consistent terminology."],
                2,
            ),
            OutlineNodeSpec(
                "Design Principles",
                "State the principles that guide the proposed framework.",
                ["The framework follows explicit design principles."],
                3,
            ),
            OutlineNodeSpec(
                "Proposed Framework",
                "Describe the framework and explain how its parts fit together.",
                ["The proposed framework operationalizes the design principles."],
                4,
                children=(
                    OutlineNodeSpec(
                        "Workflow Components",
                        "Break down the framework into implementable components.",
                        ["Each component has a distinct responsibility."],
                        1,
                    ),
                    OutlineNodeSpec(
                        "Control and Review Points",
                        "Identify where user approval and review enter the workflow.",
                        ["Review checkpoints reduce uncontrolled manuscript changes."],
                        2,
                    ),
                ),
            ),
            OutlineNodeSpec(
                "Implications",
                "Explain implications for academic writing systems and future work.",
                ["The framework suggests implementation and evaluation priorities."],
                5,
            ),
            OutlineNodeSpec(
                "Conclusion",
                "Summarize the contribution and close the argument.",
                ["The paper contributes a reusable conceptual structure."],
                6,
            ),
        ]

    def _llm_outline_specs(
        self,
        paper: Paper,
        request: OutlineGenerationRequest,
    ) -> list[OutlineNodeSpec]:
        document_type = self._document_type_for(paper, request)
        target_words = request.target_word_count or self._default_word_count(
            paper.paper_type,
            document_type,
        )
        system = (
            "You are the planner in Paper Harness. Produce evidence-aware structured document "
            "outlines as strict JSON. Do not invent citations, experiments, datasets, or "
            "results. Keep section titles concise and appropriate to the document type."
        )
        user = (
            "Create a hierarchical outline for this paper.\n\n"
            f"Title: {paper.title}\n"
            f"Document type: {document_type.value}\n"
            f"Paper type: {paper.paper_type}\n"
            f"Target venue: {paper.target_venue or 'unspecified'}\n"
            f"Target language: {paper.target_language}\n"
            f"Target word count: {target_words}\n"
            f"Additional context: {request.additional_context or 'none'}\n\n"
            "Return JSON with this shape only:\n"
            "{\n"
            '  "outline": [\n'
            "    {\n"
            '      "title": "Introduction",\n'
            '      "goal": "What this section must accomplish.",\n'
            '      "expected_claims": ["claim this section may support"],\n'
            '      "order_index": 1,\n'
            '      "children": []\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Use 5-8 top-level sections. Children are optional and should be used only "
            "when they clarify a complex method, literature, or evaluation section."
        )
        try:
            result = self.llm_provider.generate(
                LLMRequest(
                    messages=[
                        LLMMessage(role="system", content=system),
                        LLMMessage(role="user", content=user),
                    ],
                    expect_json=True,
                )
            )
            payload = parse_json_object(result.content)
            return self._outline_specs_from_payload(payload)
        except (LLMProviderError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=502, detail=f"LLM outline generation failed: {exc}") from exc

    def _outline_specs_from_payload(self, payload: dict) -> list[OutlineNodeSpec]:
        raw_outline = payload.get("outline")
        if not isinstance(raw_outline, list) or not raw_outline:
            raise ValueError("JSON field 'outline' must be a non-empty list.")
        specs = [
            self._spec_from_dict(item, fallback_order=index + 1)
            for index, item in enumerate(raw_outline)
        ]
        return specs

    def _document_type_for(self, paper: Paper, request: OutlineGenerationRequest) -> DocumentType:
        if request.document_type and request.document_type != DocumentType.UNKNOWN:
            return request.document_type
        context = " ".join([paper.title, paper.target_venue or "", request.additional_context or ""]).lower()
        if "thesis" in context or "dissertation" in context:
            return DocumentType.THESIS
        if "proposal" in context or "grant" in context:
            return DocumentType.PROPOSAL
        if "report" in context:
            return DocumentType.REPORT
        if "technical document" in context or "specification" in context or "manual" in context:
            return DocumentType.TECHNICAL_DOCUMENT
        return DocumentType.ACADEMIC_PAPER

    def _spec_from_dict(self, item: dict, *, fallback_order: int) -> OutlineNodeSpec:
        if not isinstance(item, dict):
            raise ValueError("Each outline item must be an object.")
        title = self._required_text(item, "title")
        goal = self._required_text(item, "goal")
        expected_claims = self._string_list(item.get("expected_claims"))
        order_index = self._positive_int(item.get("order_index"), fallback_order)
        children_raw = item.get("children") or []
        if not isinstance(children_raw, list):
            raise ValueError("Outline children must be a list.")
        children = tuple(
            self._spec_from_dict(child, fallback_order=index + 1)
            for index, child in enumerate(children_raw)
        )
        return OutlineNodeSpec(
            title=title,
            goal=goal,
            expected_claims=expected_claims,
            order_index=order_index,
            children=children,
        )

    def _required_text(self, item: dict, key: str) -> str:
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Outline item missing non-empty '{key}'.")
        return value.strip()

    def _string_list(self, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Expected a list of strings.")
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    def _positive_int(self, value: object, fallback: int) -> int:
        if isinstance(value, int) and value > 0:
            return value
        return fallback

    def _survey_specs(self, topic: str, context: str) -> list[OutlineNodeSpec]:
        return [
            OutlineNodeSpec(
                "Introduction",
                f"Introduce the survey scope and motivation for {topic}.{context}",
                ["The surveyed area needs structured synthesis."],
                1,
            ),
            OutlineNodeSpec(
                "Background and Scope",
                "Define inclusion boundaries and core terminology.",
                ["The survey scope is explicit and justified."],
                2,
            ),
            OutlineNodeSpec(
                "Literature Review",
                "Organize prior work into coherent themes.",
                ["Existing work can be grouped into meaningful themes."],
                3,
                children=(
                    OutlineNodeSpec(
                        "Theme-Based Synthesis",
                        "Compare major themes across the literature.",
                        ["The themes reveal similarities and contrasts."],
                        1,
                    ),
                    OutlineNodeSpec(
                        "Method and Context Comparison",
                        "Compare methods, contexts, and assumptions across sources.",
                        ["Prior work differs in methods and application settings."],
                        2,
                    ),
                ),
            ),
            OutlineNodeSpec(
                "Synthesis and Taxonomy",
                "Present a taxonomy or organizing framework.",
                ["The taxonomy clarifies relationships among prior studies."],
                4,
            ),
            OutlineNodeSpec(
                "Research Gaps",
                "Identify unresolved questions and opportunities.",
                ["The literature leaves specific gaps unresolved."],
                5,
            ),
            OutlineNodeSpec(
                "Conclusion",
                "Summarize survey findings and implications.",
                ["The survey supports a concise set of takeaways."],
                6,
            ),
        ]

    def _empirical_specs(self, topic: str, context: str) -> list[OutlineNodeSpec]:
        return [
            OutlineNodeSpec(
                "Introduction",
                f"Introduce the empirical problem and research questions for {topic}.{context}",
                ["The study addresses an empirically testable problem."],
                1,
            ),
            OutlineNodeSpec(
                "Related Work",
                "Position the study against prior empirical and theoretical work.",
                ["Prior work motivates the study design."],
                2,
            ),
            OutlineNodeSpec(
                "Methodology",
                "Describe study design, data, measures, and analysis plan.",
                ["The method can answer the research questions."],
                3,
                children=(
                    OutlineNodeSpec(
                        "Data and Materials",
                        "Describe datasets, instruments, or experimental materials.",
                        ["The data source is appropriate for the study."],
                        1,
                    ),
                    OutlineNodeSpec(
                        "Analysis Procedure",
                        "Explain the analysis process and validity checks.",
                        ["The analysis procedure is reproducible."],
                        2,
                    ),
                ),
            ),
            OutlineNodeSpec(
                "Results",
                "Report findings in relation to the research questions.",
                ["The results provide evidence for the central findings."],
                4,
            ),
            OutlineNodeSpec(
                "Discussion",
                "Interpret findings, limitations, and implications.",
                ["The discussion connects results to broader implications."],
                5,
            ),
            OutlineNodeSpec(
                "Conclusion",
                "Summarize findings and future directions.",
                ["The study contributes evidence and practical implications."],
                6,
            ),
        ]

    def _report_specs(self, topic: str, context: str) -> list[OutlineNodeSpec]:
        return [
            OutlineNodeSpec(
                "Executive Summary",
                f"Summarize the purpose, findings, and recommended action for {topic}.{context}",
                ["The report gives a concise decision-oriented summary."],
                1,
            ),
            OutlineNodeSpec(
                "Context and Scope",
                "Define the reporting context, audience needs, and boundaries.",
                ["The report scope is explicit and usable by the target audience."],
                2,
            ),
            OutlineNodeSpec(
                "Findings",
                "Present the main findings in a structured, evidence-grounded order.",
                ["The findings follow from available source material."],
                3,
            ),
            OutlineNodeSpec(
                "Analysis",
                "Interpret the findings and explain their implications.",
                ["The analysis connects findings to the user's objective."],
                4,
            ),
            OutlineNodeSpec(
                "Recommendations",
                "Translate the analysis into practical next steps.",
                ["Recommendations are feasible and traceable to findings."],
                5,
            ),
            OutlineNodeSpec(
                "Appendix",
                "Collect supporting details that should not interrupt the main report.",
                ["Supplementary material remains organized and optional."],
                6,
            ),
        ]

    def _thesis_specs(self, topic: str, context: str) -> list[OutlineNodeSpec]:
        return [
            OutlineNodeSpec(
                "Introduction",
                f"Frame the research problem, contribution, and chapter roadmap for {topic}.{context}",
                ["The thesis establishes a durable research contribution."],
                1,
            ),
            OutlineNodeSpec(
                "Literature Review",
                "Synthesize prior work and identify the research gap.",
                ["Prior work motivates the thesis contribution."],
                2,
            ),
            OutlineNodeSpec(
                "Research Design",
                "Describe the questions, methods, materials, and validity considerations.",
                ["The research design can answer the central questions."],
                3,
                children=(
                    OutlineNodeSpec(
                        "Data and Sources",
                        "Document the primary data, sources, or materials.",
                        ["The source base is sufficient for the thesis argument."],
                        1,
                    ),
                    OutlineNodeSpec(
                        "Analysis Strategy",
                        "Explain the analytical procedure and checks.",
                        ["The analysis strategy is transparent and reproducible."],
                        2,
                    ),
                ),
            ),
            OutlineNodeSpec(
                "Findings and Argument",
                "Develop the central thesis argument from evidence and analysis.",
                ["The findings support the stated contribution."],
                4,
            ),
            OutlineNodeSpec(
                "Discussion",
                "Connect findings to theory, limitations, and implications.",
                ["The discussion situates the thesis contribution."],
                5,
            ),
            OutlineNodeSpec(
                "Conclusion",
                "Close the thesis by restating contributions and future work.",
                ["The conclusion consolidates the long-form argument."],
                6,
            ),
        ]

    def _proposal_specs(self, topic: str, context: str) -> list[OutlineNodeSpec]:
        return [
            OutlineNodeSpec(
                "Overview",
                f"State the opportunity, objective, and requested decision for {topic}.{context}",
                ["The proposal frames a clear ask."],
                1,
            ),
            OutlineNodeSpec(
                "Problem and Need",
                "Explain the problem, stakeholders, and urgency.",
                ["The need is concrete and audience-relevant."],
                2,
            ),
            OutlineNodeSpec(
                "Proposed Approach",
                "Describe the proposed solution and why it fits the need.",
                ["The approach is feasible and aligned with constraints."],
                3,
            ),
            OutlineNodeSpec(
                "Work Plan",
                "Break the proposal into phases, deliverables, and responsibilities.",
                ["The work plan is executable."],
                4,
            ),
            OutlineNodeSpec(
                "Risks and Mitigations",
                "Identify major risks and how the plan will reduce them.",
                ["The proposal handles uncertainty explicitly."],
                5,
            ),
            OutlineNodeSpec(
                "Expected Outcomes",
                "Describe outputs, evaluation criteria, and next steps.",
                ["The expected outcomes are measurable and useful."],
                6,
            ),
        ]

    def _technical_document_specs(self, topic: str, context: str) -> list[OutlineNodeSpec]:
        return [
            OutlineNodeSpec(
                "Overview",
                f"Explain the purpose, users, and operating context for {topic}.{context}",
                ["The document gives readers a clear orientation."],
                1,
            ),
            OutlineNodeSpec(
                "Requirements",
                "List functional, operational, and quality requirements.",
                ["Requirements are explicit and testable."],
                2,
            ),
            OutlineNodeSpec(
                "Architecture",
                "Describe the system structure, interfaces, and key decisions.",
                ["The architecture explains how components fit together."],
                3,
                children=(
                    OutlineNodeSpec(
                        "Components",
                        "Break down major components and responsibilities.",
                        ["Each component has a clear responsibility."],
                        1,
                    ),
                    OutlineNodeSpec(
                        "Interfaces",
                        "Document inputs, outputs, protocols, or contracts.",
                        ["Interfaces are precise enough for implementation."],
                        2,
                    ),
                ),
            ),
            OutlineNodeSpec(
                "Implementation Notes",
                "Capture constraints, setup details, and operational guidance.",
                ["Implementation guidance is practical and scoped."],
                4,
            ),
            OutlineNodeSpec(
                "Validation",
                "Describe checks, tests, acceptance criteria, and known limits.",
                ["Validation criteria make quality inspectable."],
                5,
            ),
        ]

    def _default_word_count(self, paper_type: PaperType, document_type: DocumentType) -> int:
        if document_type == DocumentType.REPORT:
            return 5000
        if document_type == DocumentType.THESIS:
            return 30000
        if document_type == DocumentType.PROPOSAL:
            return 4500
        if document_type == DocumentType.TECHNICAL_DOCUMENT:
            return 6500
        if paper_type == PaperType.SURVEY:
            return 9000
        if paper_type == PaperType.EMPIRICAL:
            return 8000
        return 7000
