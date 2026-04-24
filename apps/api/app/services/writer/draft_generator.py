"""Section draft generation."""

from dataclasses import dataclass

from app.models import EvidenceItem, EvidencePack, OutlineNode, Paper, SectionContract
from app.services.llm import LLMMessage, LLMProvider, LLMRequest, get_llm_provider
from app.services.llm.json_utils import parse_json_object
from app.services.llm.providers import LLMProviderError


@dataclass(frozen=True)
class GeneratedDraft:
    """Draft text plus the evidence IDs it explicitly used."""

    content: str
    supported_evidence_ids: list[str]


class SectionDraftGenerator:
    """Produces section drafts, using a configured model when available."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider if llm_provider is not None else get_llm_provider()

    def generate(
        self,
        *,
        paper: Paper,
        section: OutlineNode,
        contract: SectionContract,
        evidence_pack: EvidencePack,
        evidence_items: list[EvidenceItem],
        drafting_instructions: str | None = None,
        neighboring_section_context: str | None = None,
    ) -> GeneratedDraft:
        if self.llm_provider is not None:
            return self._llm_generate(
                paper=paper,
                section=section,
                contract=contract,
                evidence_pack=evidence_pack,
                evidence_items=evidence_items,
                drafting_instructions=drafting_instructions,
                neighboring_section_context=neighboring_section_context,
            )
        evidence_by_id = {str(item.id): item for item in evidence_items}
        ordered_items = [
            evidence_by_id[item_id]
            for item_id in evidence_pack.evidence_item_ids
            if item_id in evidence_by_id
        ]
        evidence_ids = [str(item.id) for item in ordered_items]

        claim = self._first_text(
            section.expected_claims,
            contract.required_claims,
            default=f"{section.title} advances the argument of '{paper.title}'.",
        )
        citation_text = self._citation_text(ordered_items)
        evidence_sentence = self._evidence_sentence(ordered_items)
        context_sentence = (
            f" Nearby outline context: {neighboring_section_context.strip()}"
            if neighboring_section_context
            else ""
        )
        instruction_sentence = (
            f" Drafting instruction applied: {drafting_instructions.strip()}"
            if drafting_instructions
            else ""
        )

        content = "\n\n".join(
            [
                (
                    f"{section.title} addresses the section purpose by focusing on "
                    f"{contract.purpose.rstrip('.')}. {claim.rstrip('.')} {citation_text}".strip()
                ),
                (
                    f"The evidence pack supports this move with {len(ordered_items)} item(s). "
                    f"{evidence_sentence}"
                ).strip(),
                (
                    "Together, these points create a traceable section draft that stays within "
                    "the available evidence and leaves broader synthesis for later review."
                    f"{context_sentence}{instruction_sentence}"
                ).strip(),
            ]
        )
        return GeneratedDraft(content=content, supported_evidence_ids=evidence_ids)

    def _llm_generate(
        self,
        *,
        paper: Paper,
        section: OutlineNode,
        contract: SectionContract,
        evidence_pack: EvidencePack,
        evidence_items: list[EvidenceItem],
        drafting_instructions: str | None,
        neighboring_section_context: str | None,
    ) -> GeneratedDraft:
        allowed_ids = set(evidence_pack.evidence_item_ids)
        evidence_context = self._evidence_context(evidence_items, allowed_ids)
        system = (
            "You are the writer in Paper Harness. Draft publication-quality academic "
            "section text. Use only the supplied section contract and evidence. Do not "
            "invent citations, numbers, experiments, datasets, equations, or claims. "
            "Return strict JSON only."
        )
        user = (
            "Draft this section.\n\n"
            f"Paper title: {paper.title}\n"
            f"Target venue: {paper.target_venue or 'unspecified'}\n"
            f"Section title: {section.title}\n"
            f"Section goal: {section.goal or 'advance the paper argument'}\n"
            f"Contract purpose: {contract.purpose}\n"
            f"Questions to answer: {contract.questions_to_answer}\n"
            f"Required claims: {contract.required_claims}\n"
            f"Forbidden patterns: {contract.forbidden_patterns}\n"
            f"Tone: {contract.tone or 'clear academic'}\n"
            f"Length target: {contract.length_min or 'unspecified'}-"
            f"{contract.length_max or 'unspecified'} words\n"
            f"Neighboring context: {neighboring_section_context or 'none'}\n"
            f"Drafting instructions: {drafting_instructions or 'none'}\n\n"
            "Evidence items available:\n"
            f"{evidence_context}\n\n"
            "Return JSON with this shape only:\n"
            "{\n"
            '  "content": "Section prose in paragraphs. Use bracketed citation keys only '
            'when they appear in evidence.",\n'
            '  "supported_evidence_ids": ["evidence uuid used explicitly"]\n'
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
            content = self._required_text(payload, "content")
            supported = [
                item_id
                for item_id in self._string_list(payload.get("supported_evidence_ids"))
                if item_id in allowed_ids
            ]
            if not supported:
                supported = [item_id for item_id in evidence_pack.evidence_item_ids if item_id in allowed_ids]
            return GeneratedDraft(content=content, supported_evidence_ids=supported)
        except (LLMProviderError, ValueError, KeyError, TypeError) as exc:
            raise RuntimeError(f"LLM draft generation failed: {exc}") from exc

    def _evidence_context(self, evidence_items: list[EvidenceItem], allowed_ids: set[str]) -> str:
        lines = []
        for item in evidence_items:
            item_id = str(item.id)
            if item_id not in allowed_ids:
                continue
            content = " ".join(item.content.split())
            citation = f", citation_key={item.citation_key}" if item.citation_key else ""
            lines.append(f"- id={item_id}{citation}: {content[:1200]}")
        return "\n".join(lines) or "- No usable evidence items supplied."

    def _required_text(self, payload: dict, key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Draft JSON missing non-empty '{key}'.")
        return value.strip()

    def _string_list(self, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Draft JSON expected a list of strings.")
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    def _first_text(
        self,
        preferred: list[str],
        fallback: list[str],
        *,
        default: str,
    ) -> str:
        for value in [*preferred, *fallback]:
            if value.strip():
                return value.strip()
        return default

    def _citation_text(self, evidence_items: list[EvidenceItem]) -> str:
        citations = sorted({item.citation_key for item in evidence_items if item.citation_key})
        if not citations:
            return "[author inference from uncited evidence]"
        return " ".join(f"[{citation}]" for citation in citations)

    def _evidence_sentence(self, evidence_items: list[EvidenceItem]) -> str:
        snippets = []
        for item in evidence_items[:3]:
            text = " ".join(item.content.split())
            snippets.append(text[:160].rstrip())
        if not snippets:
            return "No evidence text was available, so drafting should not proceed."
        return " ".join(f"Evidence {index + 1}: {snippet}." for index, snippet in enumerate(snippets))


class WriterService:
    """Boundary object for Milestone 4 writer orchestration."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        from app.services.writer.revision_generator import RevisionGenerator

        self.draft_generator = SectionDraftGenerator(llm_provider=llm_provider)
        self.revision_generator = RevisionGenerator(llm_provider=llm_provider)
