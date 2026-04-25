# Agent Development Rules

This repository is a local-first writing-agent backend. Agents working here should treat the
system as a general writing workflow engine, not as a hard-coded academic paper pipeline.

## Product Direction

- Build one unified workflow: discovery -> planning -> prompt assembly -> execution -> review ->
  assembly/export.
- Do not create separate hard-coded runners for "new paper", "existing draft", "student report",
  "thesis", or "proposal". These must be planning outcomes.
- Academic paper writing is the current primary test case, but the architecture should continue to
  support reports, theses, proposals, and structured technical documents.
- Preserve deterministic behavior for local development, tests, and offline demos.
- Model-backed paths are optional enhancements and must keep deterministic fallbacks.

## Architecture Rules

- Keep FastAPI routes thin. Put workflow, validation, and business behavior in services.
- Follow the existing SQLModel persistence style in `apps/api/app/models`.
- Persist important runtime decisions as artifacts or workflow steps. Do not hide execution
  decisions in transient service state.
- Prefer conservative, traceable behavior over fluent but unsafe generation.
- Planner output should drive execution, especially `source_mode`, `document_type`,
  `current_maturity`, and section actions.
- Section actions must remain explicit and auditable:
  - `preserve`
  - `polish`
  - `rewrite`
  - `repair`
  - `draft`
  - `blocked`
- Do not silently overwrite locked or approved content.
- Use approval, checkpoint, and resume semantics when workflow execution needs user input.

## Prompt And Evaluation Rules

- Prompt changes should be versioned through prompt packs or prompt files under `configs/`.
- Prompt optimization should be evaluated against repeatable cases, not only judged by vibe.
- The first evaluation target is academic paper generation from supplied method and result inputs.
- Use `configs/evals/academic-paper-v1.json` as the baseline rubric for academic-writing quality.
- High-quality academic output should be judged on:
  - task and scope fit
  - contribution and novelty framing
  - academic storyline
  - method fidelity
  - results fidelity
  - structure and coherence
  - evidence calibration and limitations
  - style and journal readiness
- Treat invented methods, datasets, metrics, citations, experiments, or results as blockers.

## Coding Rules

- Prefer existing service patterns and schemas before adding abstractions.
- Keep edits tightly scoped to the requested behavior.
- Add tests when adding behavior, persistence fields, routes, or prompt/evaluation machinery.
- Do not refactor unrelated modules while implementing a feature.
- Use structured parsing and typed schemas where practical; avoid brittle ad hoc string handling.
- Keep comments sparse and useful.
- Keep files ASCII unless an existing file or user-facing requirement clearly needs otherwise.

## Test And Validation

From the repository root, run the relevant checks before finalizing backend changes:

```bash
ruff check apps/api/app apps/api/tests scripts/evaluate_academic_paper.py
pytest
git diff --check
```

For evaluator-only changes, at minimum run:

```bash
ruff check apps/api/app/services/evaluation apps/api/tests/test_academic_evaluation.py scripts/evaluate_academic_paper.py
pytest apps/api/tests/test_academic_evaluation.py
```

## Git Rules

- Do not collapse unrelated work into one large commit.
- Split commits by functional boundary: workflow, quality gates, provider/logging, prompt/eval,
  and docs should generally be separate.
- Do not revert user changes unless explicitly asked.
- Avoid destructive git commands such as `git reset --hard` unless the user clearly requests them.
- Prefer feature branches and PRs over committing directly to `main`, unless the user explicitly
  asks to merge to `main`.

## Current Known Gaps

- Public API and persistence names are still paper-centric in places.
- The CLI/operator experience is still early; a frontend is not currently required.
- Researcher, verifier, and global editor roles are still mostly deterministic.
- Prompt packs need serious academic-writing tuning before quality can approach top-tier venues.
- Migrations and production logging are not yet production-ready.
