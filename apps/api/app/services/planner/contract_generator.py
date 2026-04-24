"""Section contract generation."""

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import OutlineNode, Paper, SectionContract
from app.models.enums import SectionStatus
from app.schemas.contracts import ContractGenerationRequest
from app.services.llm import LLMMessage, LLMProvider, LLMRequest, get_llm_provider
from app.services.llm.json_utils import parse_json_object
from app.services.llm.providers import LLMProviderError
from app.state_machine import InvalidStateTransition, validate_section_transition


class ContractGenerator:
    """Creates section contracts, using a configured model when available."""

    def __init__(self, session: Session, llm_provider: LLMProvider | None = None) -> None:
        self.session = session
        self.llm_provider = llm_provider if llm_provider is not None else get_llm_provider()

    def generate(
        self,
        paper: Paper,
        section: OutlineNode,
        request: ContractGenerationRequest,
    ) -> SectionContract:
        existing = self.session.exec(
            select(SectionContract).where(SectionContract.section_id == section.id)
        ).first()
        data = self._contract_data(paper, section, request)

        if existing is not None:
            if not request.force:
                raise HTTPException(
                    status_code=409,
                    detail="Section contract already exists. Use force=true to regenerate it.",
                )
            for key, value in data.items():
                setattr(existing, key, value)
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing

        if section.status not in {SectionStatus.PLANNED, SectionStatus.CONTRACT_READY}:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot generate a contract for section status {section.status}.",
            )

        if section.status == SectionStatus.PLANNED:
            try:
                validate_section_transition(section.status, SectionStatus.CONTRACT_READY)
            except InvalidStateTransition as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        contract = SectionContract(section_id=section.id, **data)
        self.session.add(contract)
        section.status = SectionStatus.CONTRACT_READY
        self.session.add(section)
        self.session.commit()
        self.session.refresh(contract)
        self.session.refresh(section)
        return contract

    def _contract_data(
        self,
        paper: Paper,
        section: OutlineNode,
        request: ContractGenerationRequest,
    ) -> dict:
        if self.llm_provider is not None:
            return self._llm_contract_data(paper, section, request)
        expected_claims = section.expected_claims or [
            f"The {section.title.lower()} section advances the paper's central argument."
        ]
        constraints = (
            f" Additional constraints: {request.additional_constraints}"
            if request.additional_constraints
            else ""
        )
        word_budget = section.word_budget or 800
        length_min = max(150, int(word_budget * 0.8))
        length_max = max(length_min + 50, int(word_budget * 1.2))

        return {
            "purpose": (
                f"Write the {section.title} section for '{paper.title}' so it fulfills "
                f"the section goal: {section.goal or 'advance the paper argument'}.{constraints}"
            ),
            "questions_to_answer": self._questions_for(section),
            "required_claims": expected_claims,
            "required_evidence_count": max(1, min(3, len(expected_claims))),
            "required_citations": [],
            "forbidden_patterns": [
                "Do not introduce citations that are absent from the evidence store.",
                "Do not make unsupported empirical claims.",
                "Do not rewrite other manuscript sections.",
            ],
            "tone": "clear academic",
            "length_min": length_min,
            "length_max": length_max,
        }

    def _llm_contract_data(
        self,
        paper: Paper,
        section: OutlineNode,
        request: ContractGenerationRequest,
    ) -> dict:
        system = (
            "You are the planner in Paper Harness. Create strict section contracts "
            "for evidence-grounded academic writing. Return JSON only. Do not invent "
            "citations, experiments, datasets, or claims beyond the paper metadata."
        )
        user = (
            "Create a section contract.\n\n"
            f"Paper title: {paper.title}\n"
            f"Paper type: {paper.paper_type}\n"
            f"Target venue: {paper.target_venue or 'unspecified'}\n"
            f"Section title: {section.title}\n"
            f"Section goal: {section.goal or 'advance the paper argument'}\n"
            f"Expected claims from outline: {section.expected_claims or []}\n"
            f"Word budget: {section.word_budget or 800}\n"
            f"Additional constraints: {request.additional_constraints or 'none'}\n\n"
            "Return JSON with this shape only:\n"
            "{\n"
            '  "purpose": "One precise sentence describing what the section must do.",\n'
            '  "questions_to_answer": ["question"],\n'
            '  "required_claims": ["claim"],\n'
            '  "required_evidence_count": 1,\n'
            '  "required_citations": [],\n'
            '  "forbidden_patterns": ["Do not make unsupported empirical claims."],\n'
            '  "tone": "clear academic",\n'
            '  "length_min": 500,\n'
            '  "length_max": 900\n'
            "}"
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
            return self._validate_contract_payload(payload, section)
        except (LLMProviderError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=502, detail=f"LLM contract generation failed: {exc}") from exc

    def _validate_contract_payload(self, payload: dict, section: OutlineNode) -> dict:
        word_budget = section.word_budget or 800
        length_min = self._optional_positive_int(payload.get("length_min"), max(150, int(word_budget * 0.8)))
        length_max = self._optional_positive_int(payload.get("length_max"), max(length_min + 50, int(word_budget * 1.2)))
        if length_max <= length_min:
            length_max = length_min + 50
        required_claims = self._string_list(payload.get("required_claims")) or section.expected_claims
        return {
            "purpose": self._required_text(payload, "purpose"),
            "questions_to_answer": self._string_list(payload.get("questions_to_answer")),
            "required_claims": required_claims
            or [f"The {section.title.lower()} section advances the paper's central argument."],
            "required_evidence_count": self._optional_positive_int(
                payload.get("required_evidence_count"),
                max(1, min(3, len(required_claims) or 1)),
            ),
            "required_citations": self._string_list(payload.get("required_citations")),
            "forbidden_patterns": self._string_list(payload.get("forbidden_patterns"))
            or [
                "Do not introduce citations that are absent from the evidence store.",
                "Do not make unsupported empirical claims.",
            ],
            "tone": payload.get("tone") if isinstance(payload.get("tone"), str) else "clear academic",
            "length_min": length_min,
            "length_max": length_max,
        }

    def _required_text(self, payload: dict, key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Contract JSON missing non-empty '{key}'.")
        return value.strip()

    def _string_list(self, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Contract JSON expected a list of strings.")
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    def _optional_positive_int(self, value: object, default: int) -> int:
        if isinstance(value, int) and value > 0:
            return value
        return default

    def _questions_for(self, section: OutlineNode) -> list[str]:
        title = section.title.lower()
        if "introduction" in title:
            return [
                "What problem does the paper address?",
                "Why does this problem matter?",
                "What contribution does this section set up?",
            ]
        if "method" in title or "procedure" in title:
            return [
                "What procedure or method is being used?",
                "Why is the method appropriate?",
                "What must be reported for reproducibility?",
            ]
        if "result" in title:
            return [
                "What are the central findings?",
                "How do the findings answer the research questions?",
                "Which evidence supports each finding?",
            ]
        if "review" in title or "background" in title or "related" in title:
            return [
                "What prior work or concepts must the reader understand?",
                "How does this section synthesize rather than list sources?",
                "What gap or motivation emerges?",
            ]
        if "conclusion" in title:
            return [
                "What has the paper established?",
                "What should the reader remember?",
                "What future work or implication remains?",
            ]
        return [
            "What is the section's main claim?",
            "What evidence or reasoning must support the claim?",
            "How does this section connect to the overall paper?",
        ]
