# Paper Harness v1 Workflow

This document describes the currently implemented workflow and the intended unified writing-agent
workflow direction for Paper Harness.

The current backend is still section-centric and mostly deterministic, but provider-backed planner,
writer, and reviewer calls are now available behind the same service boundaries.

## Implemented End-To-End Loop

1. Create a paper with `POST /papers`.
2. Generate an outline with `POST /papers/{paper_id}/generate-outline`.
3. Generate section contracts with `POST /sections/{section_id}/generate-contract`.
4. Register source text or manually create evidence items.
5. Build section evidence packs with `POST /sections/{section_id}/build-evidence-pack`.
6. Generate a section draft with `POST /sections/{section_id}/draft`.
7. Review the current section draft with `POST /sections/{section_id}/review`.
8. Revise the section draft with `POST /sections/{section_id}/revise`.
9. Assemble the manuscript with `POST /papers/{paper_id}/assemble`.
10. Run global review with `POST /papers/{paper_id}/global-review`.
11. Export Markdown, default LaTeX, or template-aware LaTeX with `POST /papers/{paper_id}/export`.

## Unified Workflow Rule

Paper Harness should not maintain one hard-coded workflow for "writing from scratch" and another
for "revising an existing draft," nor separate top-level workflows for papers, reports, and
theses. There should be one workflow, and discovery plus planning should determine how that
workflow begins.

The planner should decide:

- what document the user actually wants
- who the audience is
- what success looks like
- whether the paper is currently best treated as `new_paper`, `existing_draft`, `mixed`, or `unknown`
- which sections should be preserved, polished, rewritten, repaired, drafted, or blocked
- what evidence, review, and revision loops are required before assembly

That unified workflow direction is now documented in:

- `configs/prompts/planner.md`
- `configs/workflows/v1.json`
- `docs/development-plan.md`

The runtime orchestrator for that discovery-and-plan-driven workflow is not implemented yet, but
the persistence foundation now exists:

- `POST /papers/{paper_id}/discovery` stores the latest discovery snapshot for a paper
- `POST /papers/{paper_id}/plan` produces and persists a structured plan with task profile, entry
  strategy, paper plan, section plans, and prompt-assembly hints
- `POST /papers/{paper_id}/workflow-runs` runs the first unified orchestration pass and persists
  workflow-run plus workflow-step records
- `POST /papers/{paper_id}/prompt-assemblies` assembles and persists stage-specific prompt artifacts
- `GET /papers/{paper_id}/prompt-logs` returns persisted prompt execution logs for assembled prompts
  and model-backed planner calls
- `GET /papers/{paper_id}/discovery` and `GET /papers/{paper_id}/plan` return the latest saved
  records

Current runner behavior:

- creates or reuses discovery
- creates a planning run
- if execution is enabled and the plan says outline work is needed, generates an outline
- replans after outline generation
- assembles reusable prompt artifacts for writer, reviewer, reviser, verifier, and editor stages
- injects the versioned stage prompt pack into assembled prompts and records prompt hash/version
  metadata
- prepares deterministic section contracts for non-blocked sections when safe
- executes planner section actions through the first section-action bridge:
  - `preserve` records a non-destructive preserved decision
  - `draft` aligns evidence when available and creates a deterministic section draft
  - `repair` uses review/revision context when available, otherwise persists a conservative fallback
    revision
  - `rewrite` and `polish` create traceable revised draft versions from existing draft text when a
    full review/revision path is unavailable
  - `blocked` records a skipped blocked step with the planner reason
- records completed, pending, skipped, or failed workflow steps

## Paper Lifecycle

Paper statuses:

```text
idea
-> outline_ready
-> evidence_in_progress
-> drafting_in_progress
-> section_review_in_progress
-> revision_in_progress
-> assembly_ready
-> global_review
-> final_revision
-> submission_ready
```

Implemented notes:

- Paper creation starts at `idea`.
- Outline generation moves `idea -> outline_ready`.
- Assembly advances a paper through the paper state machine to `assembly_ready` when needed.
- Global review advances to `global_review`; if manuscript issues are found, it advances to `final_revision`.
- Earlier paper statuses such as `evidence_in_progress`, `drafting_in_progress`, `section_review_in_progress`, and `revision_in_progress` exist in the state machine but are not always set by section-level operations yet.
- `submission_ready` exists but no final submission workflow is implemented.

## Section Lifecycle

Section statuses:

```text
planned
-> contract_ready
-> evidence_ready
-> drafted
-> reviewed
-> revision_required
-> revised
-> locked
```

Implemented guards:

- `planned -> contract_ready`: requires a section contract or contract generation.
- `contract_ready -> evidence_ready`: requires an active evidence pack with at least one evidence item.
- `evidence_ready -> drafted`: requires an active contract and active non-empty evidence pack.
- `drafted -> reviewed`: requires a current active section draft.
- `reviewed -> revision_required`: occurs when review comments are generated.
- `revision_required -> revised`: requires a current draft plus unresolved review comments or active revision tasks.
- `revised -> reviewed`: supported by the state machine and review endpoint.
- `locked`: exists in the state machine, but a full lock/approval endpoint is not implemented yet.

## Current Behavior

Planning:

- Outlines are generated from fixed templates for conceptual, survey, and empirical papers.
- Contracts are generated from section metadata and optional constraints.
- Discovery records and planning runs now persist the first workflow decisions for task profile,
  source mode, maturity, section actions, and prompt-assembly hints.
- The first workflow runner now consumes persisted planning output to decide whether to prepare an
  outline, assemble prompt artifacts, prepare section contracts, and execute section actions.
- Section action execution now reaches evidence alignment, drafting, review/revision when the
  current deterministic preconditions are satisfied, and records skipped/fallback outcomes when
  they are not.
- Prompt assembly now uses `configs/prompt-packs/v1.json` to inject stage-specific role packs for
  planner, writer, reviewer, reviser, verifier, and editor stages.
- Prompt artifacts persist module contents, prompt hashes, prompt pack versions, and prompt
  execution logs; model-backed planner calls also persist prompt and response logs.
- A future workflow runner should extend that execution path through global assembly, document
  review, final revision, and export.

Evidence:

- Source extraction splits normalized text into sentence chunks.
- Evidence pack selection ranks candidate evidence by section/contract term overlap.

Drafting:

- Drafts use section title, contract purpose, first planned claim, evidence snippets, and citation keys.
- Repeated initial draft generation is rejected once a current draft exists.
- Revision creates a new draft version instead of mutating the old one.

Review:

- Section review uses heuristic checks for evidence IDs, citations, short drafts, weak structure, missing transitions, redundancy, and overclaiming terms.
- Review comments automatically become revision tasks.

Assembly:

- Assembly traverses the outline tree in stable pre-order.
- Sections without current active drafts are included as placeholder blocks with warnings.
- Repeated assembly creates a new manuscript version.

Global review and export:

- Global review checks missing drafted sections, unresolved section reviews, missing introduction/conclusion, transition language, terminology drift, and duplicate sibling order indexes.
- Markdown export returns assembled content.
- LaTeX export can use the default article renderer or a template-aware path. The built-in
  `template_name=jcst` renderer preserves a submission-template structure with placeholders for
  title, author, abstract, body, packages, and bibliography. Callers may also pass
  `template_content` to preserve a specific template skeleton.
- `validate_compile=true` runs a deterministic LaTeX preflight for document environment, unresolved
  template placeholders, brace balance, environment matching, and bibliography-style warnings. It
  blocks export when preflight fails, but it does not shell out to an external TeX compiler yet.

## Current Workflow Gaps

- No multi-turn conversational discovery agent yet.
- No full-document workflow runner yet that reaches evidence, drafting, review, assembly, and export.
- Planner-driven section action execution is first-pass only; it still needs tuned prompt packs,
  richer diagnostics, retry/resume controls, and stronger model-backed revision behavior.
- No real LLM researcher, verifier, or global editor yet.
- No full section locking/approval workflow.
- No unified workflow runner yet that decides when export files should be written automatically.
- No frontend/operator console.
- No advanced citation or bibliography pipeline.
- No paragraph-level draft unit creation beyond the model enum.
