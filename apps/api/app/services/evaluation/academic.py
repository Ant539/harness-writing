"""Deterministic academic-paper writing evaluator.

The evaluator is intentionally conservative. It is not a semantic judge; it provides a stable
baseline scorecard for prompt development before model-backed judging is introduced.
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any


DEFAULT_REQUIRED_SECTIONS = [
    "abstract",
    "introduction",
    "method",
    "results",
    "discussion",
    "conclusion",
]

DIMENSIONS = [
    ("task_and_scope_fit", "Task and Scope Fit", 10),
    ("contribution_and_novelty_framing", "Contribution and Novelty Framing", 15),
    ("academic_storyline", "Academic Storyline", 15),
    ("method_fidelity", "Method Fidelity", 15),
    ("results_fidelity", "Results Fidelity", 15),
    ("structure_and_coherence", "Structure and Coherence", 10),
    ("evidence_calibration_and_limitations", "Evidence Calibration and Limitations", 10),
    ("style_and_journal_readiness", "Style and Journal Readiness", 10),
]

HYPE_TERMS = {
    "groundbreaking",
    "revolutionary",
    "unprecedented",
    "transformative",
    "game-changing",
    "perfect",
    "guarantee",
    "guaranteed",
    "always",
    "never",
}

STORY_TERMS = {
    "challenge",
    "problem",
    "gap",
    "however",
    "therefore",
    "we propose",
    "we present",
    "we demonstrate",
    "contribution",
    "finding",
    "result",
    "implication",
}

LIMITATION_TERMS = {
    "limitation",
    "limitations",
    "threat",
    "threats",
    "validity",
    "future work",
    "scope",
}

METHOD_TERMS = {
    "method",
    "methodology",
    "approach",
    "experiment",
    "experimental",
    "dataset",
    "implementation",
    "protocol",
    "measurement",
}

RESULT_TERMS = {
    "result",
    "results",
    "finding",
    "findings",
    "improved",
    "reduced",
    "increased",
    "outperform",
    "performance",
    "accuracy",
    "latency",
}


@dataclass(frozen=True)
class AcademicEvalCase:
    """Input facts and expectations for one academic paper evaluation case."""

    title: str
    method_summary: str
    result_summary: str
    field: str | None = None
    target_venue: str | None = None
    audience: str | None = None
    expected_contributions: list[str] = dc_field(default_factory=list)
    required_facts: list[str] = dc_field(default_factory=list)
    forbidden_claims: list[str] = dc_field(default_factory=list)
    constraints: list[str] = dc_field(default_factory=list)
    required_sections: list[str] = dc_field(default_factory=lambda: DEFAULT_REQUIRED_SECTIONS.copy())

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AcademicEvalCase":
        return cls(
            title=str(data.get("title") or "Untitled academic paper"),
            field=_optional_str(data.get("field")),
            target_venue=_optional_str(data.get("target_venue")),
            audience=_optional_str(data.get("audience")),
            method_summary=str(data.get("method_summary") or ""),
            result_summary=str(data.get("result_summary") or ""),
            expected_contributions=_string_list(data.get("expected_contributions")),
            required_facts=_string_list(data.get("required_facts")),
            forbidden_claims=_string_list(data.get("forbidden_claims")),
            constraints=_string_list(data.get("constraints")),
            required_sections=_string_list(data.get("required_sections"))
            or DEFAULT_REQUIRED_SECTIONS.copy(),
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "AcademicEvalCase":
        return cls.from_mapping(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass(frozen=True)
class DimensionScore:
    key: str
    name: str
    score: int
    weight: int
    rationale: str
    findings: list[str] = dc_field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "score": self.score,
            "weight": self.weight,
            "rationale": self.rationale,
            "findings": self.findings,
        }


@dataclass(frozen=True)
class AcademicPaperEvaluation:
    overall_score: float
    readiness: str
    dimension_scores: list[DimensionScore]
    blocking_issues: list[str]
    strengths: list[str]
    revision_priorities: list[str]
    missing_required_facts: list[str]
    forbidden_claim_hits: list[str]
    metadata: dict[str, Any] = dc_field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 2),
            "readiness": self.readiness,
            "dimension_scores": [score.as_dict() for score in self.dimension_scores],
            "blocking_issues": self.blocking_issues,
            "strengths": self.strengths,
            "revision_priorities": self.revision_priorities,
            "missing_required_facts": self.missing_required_facts,
            "forbidden_claim_hits": self.forbidden_claim_hits,
            "metadata": self.metadata,
        }


class AcademicPaperEvaluator:
    """Scores academic drafts against a high-standard deterministic rubric."""

    def evaluate(self, case: AcademicEvalCase, manuscript: str) -> AcademicPaperEvaluation:
        text = manuscript.strip()
        lower = _normalize(text)
        sections = _detected_sections(text)
        missing_sections = [
            section for section in case.required_sections if not _section_present(section, sections)
        ]
        method_coverage = _coverage(case.method_summary, lower)
        result_coverage = _coverage(case.result_summary, lower)
        contribution_coverages = [
            _coverage(contribution, lower) for contribution in case.expected_contributions
        ]
        required_fact_coverages = [_coverage(fact, lower) for fact in case.required_facts]
        missing_required_facts = [
            fact
            for fact, coverage in zip(case.required_facts, required_fact_coverages, strict=False)
            if coverage < 0.35
        ]
        forbidden_claim_hits = [
            claim for claim in case.forbidden_claims if _coverage(claim, lower) >= 0.45
        ]
        hype_hits = sorted(term for term in HYPE_TERMS if term in lower)
        has_limitations = any(term in lower for term in LIMITATION_TERMS)
        has_method_language = any(term in lower for term in METHOD_TERMS)
        has_result_language = any(term in lower for term in RESULT_TERMS)
        has_story_language = sum(1 for term in STORY_TERMS if term in lower)
        word_count = len(re.findall(r"\b\w+\b", text))

        dimension_scores = [
            self._task_scope_score(case, word_count, method_coverage, result_coverage),
            self._contribution_score(case, contribution_coverages, lower),
            self._storyline_score(has_story_language, sections),
            self._method_score(method_coverage, has_method_language),
            self._results_score(result_coverage, has_result_language),
            self._structure_score(missing_sections, sections),
            self._calibration_score(
                missing_required_facts,
                forbidden_claim_hits,
                hype_hits,
                has_limitations,
            ),
            self._style_score(word_count, hype_hits, lower),
        ]
        blocking_issues = self._blocking_issues(
            method_coverage=method_coverage,
            result_coverage=result_coverage,
            missing_required_facts=missing_required_facts,
            forbidden_claim_hits=forbidden_claim_hits,
            contribution_coverages=contribution_coverages,
        )
        overall = _weighted_overall(dimension_scores)
        if any("contradicts or includes forbidden claim" in issue for issue in blocking_issues):
            overall = min(overall, 50.0)
        if any("No clear expected contribution" in issue for issue in blocking_issues):
            overall = min(overall, 60.0)
        readiness = _readiness(overall, blocking_issues)

        return AcademicPaperEvaluation(
            overall_score=overall,
            readiness=readiness,
            dimension_scores=dimension_scores,
            blocking_issues=blocking_issues,
            strengths=self._strengths(dimension_scores),
            revision_priorities=self._revision_priorities(dimension_scores, blocking_issues),
            missing_required_facts=missing_required_facts,
            forbidden_claim_hits=forbidden_claim_hits,
            metadata={
                "word_count": word_count,
                "detected_sections": sections,
                "missing_sections": missing_sections,
                "method_coverage": round(method_coverage, 3),
                "result_coverage": round(result_coverage, 3),
                "hype_hits": hype_hits,
            },
        )

    def _task_scope_score(
        self,
        case: AcademicEvalCase,
        word_count: int,
        method_coverage: float,
        result_coverage: float,
    ) -> DimensionScore:
        score = 3
        findings = []
        if method_coverage >= 0.45 and result_coverage >= 0.45:
            score += 1
            findings.append("The draft covers both supplied method and result material.")
        if case.target_venue or case.audience:
            findings.append("Case includes target venue or audience context for scope judgment.")
        if word_count < 600:
            score -= 1
            findings.append("The manuscript is very short for a full academic paper draft.")
        return _dimension(
            "task_and_scope_fit",
            score,
            "Scope fit is based on length and coverage of supplied method/result inputs.",
            findings,
        )

    def _contribution_score(
        self,
        case: AcademicEvalCase,
        contribution_coverages: list[float],
        lower: str,
    ) -> DimensionScore:
        has_contribution_terms = "contribution" in lower or "we propose" in lower
        if not case.expected_contributions:
            score = 2 if has_contribution_terms else 1
            findings = ["No expected contributions were supplied in the eval case."]
        else:
            average = sum(contribution_coverages) / len(contribution_coverages)
            score = _coverage_to_score(average)
            findings = [f"Average expected contribution coverage: {average:.2f}."]
        if has_contribution_terms and score < 5:
            score += 1
            findings.append("The draft explicitly signals contribution framing.")
        return _dimension(
            "contribution_and_novelty_framing",
            score,
            "Contribution score rewards explicit and case-faithful novelty framing.",
            findings,
        )

    def _storyline_score(self, story_term_count: int, sections: list[str]) -> DimensionScore:
        score = 1 + min(4, story_term_count // 2)
        findings = [f"Detected {story_term_count} storyline markers."]
        if _section_present("introduction", sections) and _section_present("conclusion", sections):
            score = min(5, score + 1)
            findings.append("The manuscript has both introduction and conclusion structure.")
        return _dimension(
            "academic_storyline",
            score,
            "Storyline score estimates whether the draft creates a scholarly arc.",
            findings,
        )

    def _method_score(self, method_coverage: float, has_method_language: bool) -> DimensionScore:
        score = _coverage_to_score(method_coverage)
        findings = [f"Method summary lexical coverage: {method_coverage:.2f}."]
        if has_method_language and score < 5:
            score += 1
            findings.append("The draft uses explicit method language.")
        return _dimension(
            "method_fidelity",
            score,
            "Method fidelity is estimated from supplied-method coverage and concrete method cues.",
            findings,
        )

    def _results_score(self, result_coverage: float, has_result_language: bool) -> DimensionScore:
        score = _coverage_to_score(result_coverage)
        findings = [f"Result summary lexical coverage: {result_coverage:.2f}."]
        if has_result_language and score < 5:
            score += 1
            findings.append("The draft uses explicit result language.")
        return _dimension(
            "results_fidelity",
            score,
            "Results fidelity is estimated from supplied-result coverage and result cues.",
            findings,
        )

    def _structure_score(self, missing_sections: list[str], sections: list[str]) -> DimensionScore:
        present = max(0, len(DEFAULT_REQUIRED_SECTIONS) - len(missing_sections))
        score = max(1, min(5, round((present / len(DEFAULT_REQUIRED_SECTIONS)) * 5)))
        findings = [f"Detected sections: {', '.join(sections) or 'none'}."]
        if missing_sections:
            findings.append(f"Missing expected sections: {', '.join(missing_sections)}.")
        return _dimension(
            "structure_and_coherence",
            score,
            "Structure score is based on recognizable academic section coverage.",
            findings,
        )

    def _calibration_score(
        self,
        missing_required_facts: list[str],
        forbidden_claim_hits: list[str],
        hype_hits: list[str],
        has_limitations: bool,
    ) -> DimensionScore:
        score = 5
        findings = []
        if missing_required_facts:
            score -= 2
            findings.append("Some required facts are missing.")
        if forbidden_claim_hits:
            score -= 3
            findings.append("The manuscript appears to include forbidden claims.")
        if hype_hits:
            score -= 1
            findings.append(f"Overconfident or promotional terms detected: {', '.join(hype_hits)}.")
        if has_limitations:
            findings.append("The manuscript includes limitation or validity language.")
        else:
            score -= 1
            findings.append("No limitation or validity language was detected.")
        return _dimension(
            "evidence_calibration_and_limitations",
            score,
            "Calibration score penalizes missing required facts, forbidden claims, and overclaiming.",
            findings,
        )

    def _style_score(self, word_count: int, hype_hits: list[str], lower: str) -> DimensionScore:
        score = 3
        findings = []
        if word_count >= 1200:
            score += 1
            findings.append("The draft has enough length for substantive academic development.")
        if "abstract" in lower and "conclusion" in lower:
            score += 1
            findings.append("The draft includes submission-like framing sections.")
        if hype_hits:
            score -= 1
            findings.append("Promotional language reduces journal readiness.")
        return _dimension(
            "style_and_journal_readiness",
            score,
            "Style score rewards serious academic form and penalizes promotional language.",
            findings,
        )

    def _blocking_issues(
        self,
        *,
        method_coverage: float,
        result_coverage: float,
        missing_required_facts: list[str],
        forbidden_claim_hits: list[str],
        contribution_coverages: list[float],
    ) -> list[str]:
        issues = []
        if method_coverage < 0.25:
            issues.append("Missing or weak coverage of the supplied method.")
        if result_coverage < 0.25:
            issues.append("Missing or weak coverage of the supplied results.")
        if missing_required_facts:
            issues.append("Required facts are missing from the manuscript.")
        if forbidden_claim_hits:
            issues.append("The draft contradicts or includes forbidden claim material.")
        if contribution_coverages and max(contribution_coverages) < 0.25:
            issues.append("No clear expected contribution is represented.")
        return issues

    def _strengths(self, scores: list[DimensionScore]) -> list[str]:
        return [
            f"{score.name}: {score.rationale}"
            for score in scores
            if score.score >= 4
        ][:3]

    def _revision_priorities(
        self,
        scores: list[DimensionScore],
        blocking_issues: list[str],
    ) -> list[str]:
        priorities = list(blocking_issues)
        priorities.extend(
            f"Improve {score.name.lower()}."
            for score in sorted(scores, key=lambda item: item.score)
            if score.score <= 3
        )
        return _dedupe(priorities)[:6]


def _dimension(key: str, score: int, rationale: str, findings: list[str]) -> DimensionScore:
    name, weight = next((name, weight) for dim_key, name, weight in DIMENSIONS if dim_key == key)
    return DimensionScore(
        key=key,
        name=name,
        score=max(1, min(5, score)),
        weight=weight,
        rationale=rationale,
        findings=findings,
    )


def _weighted_overall(scores: list[DimensionScore]) -> float:
    total_weight = sum(score.weight for score in scores)
    weighted = sum((score.score / 5) * score.weight for score in scores)
    return (weighted / total_weight) * 100


def _readiness(overall: float, blocking_issues: list[str]) -> str:
    if blocking_issues:
        return "blocked"
    if overall >= 85:
        return "near_submission_ready"
    if overall >= 75:
        return "strong"
    if overall >= 60:
        return "serviceable"
    return "weak"


def _coverage(source: str, lower_text: str) -> float:
    tokens = _keywords(source)
    if not tokens:
        return 0.0
    matched = sum(1 for token in tokens if token in lower_text)
    return matched / len(tokens)


def _coverage_to_score(coverage: float) -> int:
    if coverage >= 0.75:
        return 5
    if coverage >= 0.55:
        return 4
    if coverage >= 0.35:
        return 3
    if coverage >= 0.2:
        return 2
    return 1


def _detected_sections(text: str) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        stripped = line.strip().strip("#").strip().lower()
        if not stripped or len(stripped) > 80:
            continue
        normalized = re.sub(r"[^a-z0-9 ]+", "", stripped)
        if normalized in {
            "abstract",
            "introduction",
            "related work",
            "background",
            "method",
            "methods",
            "methodology",
            "approach",
            "experimental setup",
            "experiments",
            "results",
            "evaluation",
            "discussion",
            "limitations",
            "conclusion",
            "conclusions",
        }:
            headings.append(normalized)
    return _dedupe(headings)


def _section_present(section: str, detected_sections: list[str]) -> bool:
    aliases = {
        "method": {"method", "methods", "methodology", "approach", "experimental setup"},
        "results": {"results", "evaluation", "experiments"},
        "conclusion": {"conclusion", "conclusions"},
        "discussion": {"discussion", "limitations"},
    }
    wanted = aliases.get(section, {section})
    return any(section_name in wanted for section_name in detected_sections)


def _keywords(text: str) -> set[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "we",
        "with",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,}", text.lower())
        if token not in stopwords
    }


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result
