# Current Project Status

Last updated after the workflow resume/retry and section approval workflow passes on April 25, 2026.

## Completed Milestones

- Milestone 1: backend skeleton, SQLModel persistence, core models, CRUD routes, and state machine tests.
- Milestone 2: deterministic outline generation, section contract generation, duplicate-generation guards, and manual outline/contract editing.
- Milestone 3: source material registration, deterministic text evidence extraction, manual evidence item management, and evidence pack building.
- Milestone 4: deterministic section drafting, draft versioning, section review, review comments, revision tasks, and revision flow.
- Milestone 5: manuscript assembly, versioned manuscript artifacts, global manuscript review, manuscript issues, and Markdown/simple LaTeX export artifacts.
- Milestone 6: documentation closure, handoff notes, deterministic-extension markers, and end-to-end smoke coverage.

## Current Supported Flows

### Prompt Evaluation

- Run a deterministic academic-paper writing evaluator from the command line against a case JSON
  and generated manuscript.
- Score drafts against a high-standard rubric covering task fit, contribution/novelty framing,
  academic storyline, method fidelity, results fidelity, coherence, calibration, and journal
  readiness.
- Produce structured scorecards with blocking issues, strengths, revision priorities, missing
  required facts, and forbidden-claim hits.

### Planning

- Create papers.
- Generate deterministic outlines for conceptual, survey, and empirical paper types.
- Edit outline nodes.
- Generate or manually create section contracts.
- Persist discovery records, planning runs, prompt assemblies, workflow runs, workflow steps,
  workflow checkpoints, and retry/resume state.

### Evidence

- Register text source material.
- Extract evidence items from text.
- Manually create/edit evidence items.
- Build or manually create evidence packs.
- Verify current section draft citations and evidence provenance against the active evidence pack.

### Section Drafting And Review

- Generate a section draft only when the section is `evidence_ready`.
- Persist draft versions.
- Review current active section drafts.
- Persist structured review comments.
- Automatically create revision tasks from review comments.
- Revise a section into a new draft version.
- Optionally use a configured model provider for outline, contract, draft, review, and revision generation paths.
- Request section approval, approve reviewed/revised sections into `locked`, request changes, and
  unlock sections for another pass.

### Manuscript Assembly And Export

- Assemble current active section drafts in outline tree order.
- Persist versioned manuscript artifacts.
- Include missing-draft placeholders with warnings.
- Run deterministic global manuscript review.
- Persist manuscript-level issues.
- Detect first-pass whole-paper consistency problems around terminology, contribution statements,
  and abstract/conclusion alignment.
- Persist Markdown and simple LaTeX export artifacts.

## Current Deterministic Components

- Evaluator: academic-paper scorecard generation for prompt development and writing-quality
  regression checks.
- Planner: fixed outline templates and contract templates.
- Researcher: sentence-based text extraction and simple evidence ranking.
- Writer: deterministic text construction from contracts and evidence snippets.
- Reviewer: heuristic checks for structure, citations, transitions, redundancy, overclaiming, and evidence support.
- Verifier: evidence ID, citation-support, and source-provenance checks.
- Editor: deterministic assembly, global review heuristics, whole-paper consistency checks, Markdown
  passthrough export, and simple LaTeX conversion.

These components are intentionally easy to replace or augment with real adapters later.

## Current Model-Backed Components

- Planner: outline and section contract generation can call a configured provider.
- Writer: section draft and revision generation can call a configured provider.
- Reviewer: section review can call a configured provider.
- Provider responses expose normalized usage metadata where available; prompt execution logs persist
  token counts and provider-reported USD cost when supplied.
- Deterministic planning, prompt framing, outline templates, and section contracts support
  `report`, `thesis`, `proposal`, and `technical_document` use cases on the existing project model.

Research, verification, and global editor behavior remain deterministic today.

## Current Test And Lint Status

Expected commands from the repository root:

```bash
pytest
ruff check apps/api/app apps/api/tests
```

After the current document generalization pass, both commands are expected to pass.

## Recommended Next Milestone Candidates

1. Add prompt eval fixtures and regression runs for academic paper demo cases.
2. Tighten approval-gated assembly/export policy around locked sections.
3. Add model-backed researcher, verifier, global editor, and academic-writing evaluator layers.
4. Add bibliography/citation-style export support and semantic entailment checks.
5. Rename or alias paper-centric API/model surfaces for broader document projects.
6. Add migrations before the schema is used outside local prototypes.
