"""Task routing role for Writing Harness."""

from app.schemas.writing_harness import TaskRoute, WritingHarnessRunRequest, WritingTaskType


class TaskRouter:
    """Route writing tasks by risk, complexity, and requested deliverable."""

    _rewrite_signals = {
        "polish",
        "rewrite",
        "rephrase",
        "shorten",
        "expand",
        "translate",
        "tone",
        "more polite",
        "润色",
        "改写",
        "缩短",
        "扩写",
        "翻译",
        "更礼貌",
    }
    _academic_signals = {
        "academic",
        "paper",
        "论文",
        "学术",
        "投稿",
        "workshop",
        "conference",
        "journal",
        "literature",
        "文献",
        "citation",
        "引用",
        "related work",
        "method section",
        "research question",
    }
    _research_signals = {
        "research",
        "sources",
        "source",
        "references",
        "citations",
        "evidence",
        "fact check",
        "benchmark",
        "dataset",
        "资料",
        "事实核验",
    }
    _structured_signals = {
        "blog",
        "article",
        "technical article",
        "prd",
        "product doc",
        "documentation",
        "proposal",
        "whitepaper",
        "博客",
        "文章",
        "文档",
    }
    _long_form_signals = {"book", "course", "curriculum", "multi-chapter", "书", "课程"}

    def route(self, payload: WritingHarnessRunRequest) -> TaskRoute:
        if payload.requested_task_type is not None:
            requested = payload.requested_task_type
            return TaskRoute(
                task_type=requested,
                complexity_score=self._default_score(requested),
                rationale="User explicitly requested the workflow class.",
                signals=["explicit_request"],
                requires_research=requested
                in {WritingTaskType.RESEARCH_WRITING, WritingTaskType.ACADEMIC_PAPER},
                requires_citations=requested
                in {WritingTaskType.RESEARCH_WRITING, WritingTaskType.ACADEMIC_PAPER},
                requires_review_loop=requested
                not in {WritingTaskType.QUICK_REWRITE, WritingTaskType.SIMPLE_DRAFT},
            )

        text = self._combined_text(payload).lower()
        signals: list[str] = []
        score = 0

        if self._contains_any(text, self._rewrite_signals):
            signals.append("rewrite_intent")
            score += 1
        if self._contains_any(text, self._academic_signals):
            signals.append("academic_or_citation_context")
            score += 5
        if self._contains_any(text, self._research_signals):
            signals.append("research_or_fact_support_required")
            score += 4
        if self._contains_any(text, self._structured_signals):
            signals.append("structured_deliverable")
            score += 3
        if self._contains_any(text, self._long_form_signals):
            signals.append("long_form_project")
            score += 6
        if len(text) > 1200 or "long" in text or "chapter" in text:
            signals.append("long_output_or_multi_section")
            score += 2
        if any(term in text for term in ["medical", "legal", "financial", "clinical", "法律", "医学"]):
            signals.append("high_risk_factual_domain")
            score += 3
        if payload.source_text:
            signals.append("source_text_provided")
            score += 1

        if "long_form_project" in signals:
            task_type = WritingTaskType.LONG_FORM_PROJECT
        elif "academic_or_citation_context" in signals:
            task_type = WritingTaskType.ACADEMIC_PAPER
        elif "research_or_fact_support_required" in signals:
            task_type = WritingTaskType.RESEARCH_WRITING
        elif "structured_deliverable" in signals or score >= 3:
            task_type = WritingTaskType.STRUCTURED_WRITING
        elif "rewrite_intent" in signals and payload.source_text:
            task_type = WritingTaskType.QUICK_REWRITE
        else:
            task_type = WritingTaskType.SIMPLE_DRAFT

        return TaskRoute(
            task_type=task_type,
            complexity_score=score,
            rationale=self._route_rationale(task_type, signals),
            signals=signals or ["low_complexity_default"],
            requires_research=task_type in {WritingTaskType.RESEARCH_WRITING, WritingTaskType.ACADEMIC_PAPER},
            requires_citations=task_type in {WritingTaskType.RESEARCH_WRITING, WritingTaskType.ACADEMIC_PAPER},
            requires_review_loop=task_type
            in {
                WritingTaskType.STRUCTURED_WRITING,
                WritingTaskType.RESEARCH_WRITING,
                WritingTaskType.ACADEMIC_PAPER,
                WritingTaskType.LONG_FORM_PROJECT,
            },
        )

    def _combined_text(self, payload: WritingHarnessRunRequest) -> str:
        return " ".join(
            item
            for item in [
                payload.user_input,
                payload.source_text or "",
                payload.target_venue or "",
                payload.length or "",
            ]
            if item
        )

    def _contains_any(self, text: str, terms: set[str]) -> bool:
        return any(term in text for term in terms)

    def _default_score(self, task_type: WritingTaskType) -> int:
        scores = {
            WritingTaskType.QUICK_REWRITE: 1,
            WritingTaskType.SIMPLE_DRAFT: 2,
            WritingTaskType.STRUCTURED_WRITING: 4,
            WritingTaskType.RESEARCH_WRITING: 6,
            WritingTaskType.ACADEMIC_PAPER: 8,
            WritingTaskType.LONG_FORM_PROJECT: 9,
        }
        return scores[task_type]

    def _route_rationale(self, task_type: WritingTaskType, signals: list[str]) -> str:
        signal_text = ", ".join(signals) if signals else "no high-complexity signal"
        return f"Routed to {task_type.value} based on {signal_text}."
