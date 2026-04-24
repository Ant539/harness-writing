# Current Project Status

Last updated after the configurable provider integration and workflow-planning documentation pass on April 24, 2026.

## Completed Milestones

- Milestone 1: backend skeleton, SQLModel persistence, core models, CRUD routes, and state machine tests.
- Milestone 2: deterministic outline generation, section contract generation, duplicate-generation guards, and manual outline/contract editing.
- Milestone 3: source material registration, deterministic text evidence extraction, manual evidence item management, and evidence pack building.
- Milestone 4: deterministic section drafting, draft versioning, section review, review comments, revision tasks, and revision flow.
- Milestone 5: manuscript assembly, versioned manuscript artifacts, global manuscript review, manuscript issues, and Markdown/simple LaTeX export artifacts.
- Milestone 6: documentation closure, handoff notes, deterministic-extension markers, and end-to-end smoke coverage.

## Current Supported Flows

### Planning

- Create papers.
- Generate deterministic outlines for conceptual, survey, and empirical paper types.
- Edit outline nodes.
- Generate or manually create section contracts.
- Configure a planner prompt and unified workflow definition, though no persisted planning run exists yet.

### Evidence

- Register text source material.
- Extract evidence items from text.
- Manually create/edit evidence items.
- Build or manually create evidence packs.

### Section Drafting And Review

- Generate a section draft only when the section is `evidence_ready`.
- Persist draft versions.
- Review current active section drafts.
- Persist structured review comments.
- Automatically create revision tasks from review comments.
- Revise a section into a new draft version.
- Optionally use a configured model provider for outline, contract, draft, review, and revision generation paths.

### Manuscript Assembly And Export

- Assemble current active section drafts in outline tree order.
- Persist versioned manuscript artifacts.
- Include missing-draft placeholders with warnings.
- Run deterministic global manuscript review.
- Persist manuscript-level issues.
- Persist Markdown and simple LaTeX export artifacts.

## Current Deterministic Components

- Planner: fixed outline templates and contract templates.
- Researcher: sentence-based text extraction and simple evidence ranking.
- Writer: deterministic text construction from contracts and evidence snippets.
- Reviewer: heuristic checks for structure, citations, transitions, redundancy, overclaiming, and evidence support.
- Verifier: evidence ID and citation-support checks.
- Editor: deterministic assembly, global review heuristics, Markdown passthrough export, and simple LaTeX conversion.

These components are intentionally easy to replace or augment with real adapters later.

## Current Model-Backed Components

- Planner: outline and section contract generation can call a configured provider.
- Writer: section draft and revision generation can call a configured provider.
- Reviewer: section review can call a configured provider.

Research, verification, and global editor behavior remain deterministic today.

## Current Test And Lint Status

Expected commands from the repository root:

```bash
pytest
ruff check apps/api/app apps/api/tests
```

At Milestone 6 completion, both commands pass.

## Recommended Next Milestone Candidates

1. Add a persisted planning phase and a unified workflow runner.
2. Add planner-driven section actions for preserve/polish/rewrite/repair/draft/blocked.
3. Add section locking and approval workflows so assembly can default to locked sections.
4. Add model-backed researcher, verifier, and global editor layers.
5. Add template-aware export and compile validation.
6. Add a frontend/operator console.
7. Add migrations before the schema is used outside local prototypes.
