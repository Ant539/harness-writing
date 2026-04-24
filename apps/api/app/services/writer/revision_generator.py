"""Section revision generation."""

from dataclasses import dataclass

from app.models import EvidenceItem, EvidencePack, OutlineNode, ReviewComment, RevisionTask, SectionContract
from app.services.llm import LLMMessage, LLMProvider, LLMRequest, get_llm_provider
from app.services.llm.json_utils import parse_json_object
from app.services.llm.providers import LLMProviderError


@dataclass(frozen=True)
class GeneratedRevision:
    """Revised draft text plus the evidence IDs it continues to support."""

    content: str
    supported_evidence_ids: list[str]


class RevisionGenerator:
    """Creates revised section drafts, using a configured model when available."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider if llm_provider is not None else get_llm_provider()

    def generate(
        self,
        *,
        section: OutlineNode,
        contract: SectionContract,
        evidence_pack: EvidencePack,
        evidence_items: list[EvidenceItem],
        current_content: str,
        review_comments: list[ReviewComment],
        revision_tasks: list[RevisionTask],
        revision_instructions: str | None = None,
    ) -> GeneratedRevision:
        if self.llm_provider is not None:
            return self._llm_generate(
                section=section,
                contract=contract,
                evidence_pack=evidence_pack,
                evidence_items=evidence_items,
                current_content=current_content,
                review_comments=review_comments,
                revision_tasks=revision_tasks,
                revision_instructions=revision_instructions,
            )
        evidence_ids = [str(item.id) for item in evidence_items if str(item.id) in evidence_pack.evidence_item_ids]
        actions = [comment.suggested_action for comment in review_comments]
        actions.extend(task.task_description for task in revision_tasks)
        unique_actions = self._unique(actions)
        evidence_note = self._citation_note(evidence_items)
        instruction_note = (
            f"\n\nManual revision instruction: {revision_instructions.strip()}"
            if revision_instructions
            else ""
        )

        revision_note = (
            "Revision pass applied to address review feedback: "
            + "; ".join(unique_actions[:5])
            if unique_actions
            else "Revision pass applied using the available review context."
        )
        contract_note = (
            f"The revised version keeps the section aligned with the contract purpose: "
            f"{contract.purpose.rstrip('.')}. {evidence_note}"
        )
        content = (
            f"{current_content.rstrip()}\n\n"
            f"{revision_note}\n\n"
            f"{contract_note}\n\n"
            f"The section now closes with a clearer transition from {section.title} to the next "
            "paper component while preserving the same evidence trace."
            f"{instruction_note}"
        )
        return GeneratedRevision(content=content, supported_evidence_ids=evidence_ids)

    def _llm_generate(
        self,
        *,
        section: OutlineNode,
        contract: SectionContract,
        evidence_pack: EvidencePack,
        evidence_items: list[EvidenceItem],
        current_content: str,
        review_comments: list[ReviewComment],
        revision_tasks: list[RevisionTask],
        revision_instructions: str | None,
    ) -> GeneratedRevision:
        allowed_ids = set(evidence_pack.evidence_item_ids)
        evidence_context = self._evidence_context(evidence_items, allowed_ids)
        review_context = self._review_context(review_comments, revision_tasks)
        system = (
            "You are the revision writer in Paper Harness. Revise the section using "
            "only the current draft, evidence, contract, and review tasks. Preserve "
            "technical meaning and do not invent unsupported facts. Return strict JSON only."
        )
        user = (
            "Revise this section.\n\n"
            f"Section title: {section.title}\n"
            f"Contract purpose: {contract.purpose}\n"
            f"Required claims: {contract.required_claims}\n"
            f"Forbidden patterns: {contract.forbidden_patterns}\n"
            f"Revision instructions: {revision_instructions or 'none'}\n\n"
            "Current draft:\n"
            f"{current_content}\n\n"
            "Review context:\n"
            f"{review_context}\n\n"
            "Evidence items available:\n"
            f"{evidence_context}\n\n"
            "Return JSON with this shape only:\n"
            "{\n"
            '  "content": "Complete revised section prose.",\n'
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
            return GeneratedRevision(content=content, supported_evidence_ids=supported)
        except (LLMProviderError, ValueError, KeyError, TypeError) as exc:
            raise RuntimeError(f"LLM revision generation failed: {exc}") from exc

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

    def _review_context(
        self,
        review_comments: list[ReviewComment],
        revision_tasks: list[RevisionTask],
    ) -> str:
        lines = []
        for comment in review_comments:
            lines.append(
                f"- comment {comment.comment_type}/{comment.severity}: "
                f"{comment.comment} Action: {comment.suggested_action}"
            )
        for task in revision_tasks:
            lines.append(f"- task {task.priority}: {task.task_description}")
        return "\n".join(lines) or "- No review context supplied."

    def _required_text(self, payload: dict, key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Revision JSON missing non-empty '{key}'.")
        return value.strip()

    def _string_list(self, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Revision JSON expected a list of strings.")
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    def _unique(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = " ".join(value.split())
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result

    def _citation_note(self, evidence_items: list[EvidenceItem]) -> str:
        citations = sorted({item.citation_key for item in evidence_items if item.citation_key})
        if not citations:
            return "The section continues to rely on uncited evidence items and author inference markers."
        return "Citations retained: " + ", ".join(citations) + "."
