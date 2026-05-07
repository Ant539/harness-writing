# Writing Harness Architecture Check

## Current Architecture Diagnosis

The repository already implements a local-first academic paper harness rather than a simple chat bot.
The active backend lives in `apps/api` and exposes FastAPI routes backed by SQLModel/SQLite.

Current major modules:

- `models` and `schemas`: persisted paper, outline, evidence, draft, review, revision, assembly,
  workflow, prompt, interaction, and approval artifacts.
- `services/planner`: discovery, workflow planning, outline generation, and section contracts.
- `services/research`: source registration, evidence extraction, and evidence packs.
- `services/writer` and `services/drafting.py`: section draft and revision generation.
- `services/reviewer` and `services/review.py`: structured section review comments and revision tasks.
- `services/verifier`: citation/evidence support checks.
- `services/editor` and `services/assembly.py`: manuscript assembly, global review, and export.
- `services/workflows.py`: an early unified runner that persists workflow runs and step history.
- `state_machine`: paper and section lifecycle transitions.

Existing concepts:

- Agent/role boundaries exist as service modules and lightweight `agents/*` placeholders.
- Workflow, state, artifact versioning, review, revision, evidence, approval, prompt assembly, and
  evaluator concepts already exist.
- The strongest implemented path is still paper/section-centric. It is a deterministic workflow
  runner with optional model-backed planner/writer/reviewer service boundaries, not a fully
  autonomous agentic loop.

## Gap Against Target

- Task classification: partially present through discovery/planning document type, but no generic
  top-level router for quick rewrites, simple drafts, structured writing, research writing, and
  academic papers.
- Different complexity workflows: partially present for document types inside paper workflow, but
  simple tasks still had no lightweight non-paper entry.
- Writing brief: partially represented by `DiscoveryRecord`, but not yet as a reusable generic
  `WritingBrief`.
- Outline checkpoint: present for paper sections; now also exposed through generic harness artifacts.
- Draft versions: present for section drafts; now represented generically by `Draft`.
- Review report: section review comments existed; generic `ReviewReport` now adds structured rubric
  scores and issue schema.
- Revision plan: section `RevisionTask` existed; generic `RevisionPlan` now ties review issues to
  revision intent.
- Fact/citation check: deterministic support checks existed for paper drafts; generic academic flow
  now marks missing sources and unsupported claims before final output.
- Academic paper workflow: implemented section-centric flow existed; generic academic minimum loop
  now adds AcademicBrief, ClaimEvidenceMap, citation check, academic review, revision plan, and
  changelog in one route.
- Artifact/state persistence: existing paper artifacts persist; generic writing harness runs now
  persist route, artifacts, and state history in `writing_harness_runs`.
- Future multi-agent expansion: role boundaries remain logical services. The new service keeps
  TaskRouter, brief builder, planner, writer, reviewer, citation checker, and editor responsibilities
  separable without introducing physical multi-agent orchestration.

## Most Important Architecture Issues

- Public API and persistence are still paper-centric in many mature modules.
- Existing workflow starts from a paper project, so lightweight writing tasks had no natural place to
  run.
- Review was structured at section-comment level, but lacked a single reusable `ReviewReport` and
  rubric contract for non-section workflows.
- Revision was task/comment-oriented, but not represented as an explicit plan-plus-changelog package
  for generic writing.
- Academic safety rules existed in prompts and verifier checks, but the top-level academic writing
  flow did not yet force ClaimEvidenceMap and citation-risk artifacts before final delivery.

## Target Shape Added

The generic entry is now:

`User Input -> Task Router -> Workflow Engine -> Writing State Store -> Artifact Manager -> Role Modules -> Review / Revision Loop -> Final Renderer`

Implemented in the first pass:

- `POST /writing-harness/runs`
- `GET /writing-harness/runs`
- `GET /writing-harness/runs/{run_id}`

The generic runner preserves the existing paper API while adding these route classes:

- `QUICK_REWRITE`
- `SIMPLE_DRAFT`
- `STRUCTURED_WRITING`
- `RESEARCH_WRITING`
- `ACADEMIC_PAPER`
- `LONG_FORM_PROJECT`

Academic paper runs now produce a minimum final paper package containing:

- `AcademicBrief`
- `ClaimEvidenceMap`
- `SourceNote[]`
- `Outline`
- `Draft`
- citation and claim-evidence warnings
- academic `ReviewReport`
- `RevisionPlan`
- `ChangeLog`
- final output

The implementation remains deterministic and conservative. It marks missing evidence rather than
inventing citations, experiments, benchmarks, datasets, or conclusions.

## Role Module Boundary

The generic `WritingHarnessService` is now an orchestrator. It owns state transitions, run
persistence, and workflow selection, but delegates artifact behavior to logical role modules under
`apps/api/app/services/writing_roles`.

Current role modules:

- `TaskRouter`: chooses workflow class from explicit request, academic/research signals, output
  complexity, factual-risk hints, and rewrite intent.
- `BriefBuilder`: builds `WritingBrief` and `AcademicBrief`.
- `Planner`: builds generic outlines, academic outlines, source notes, and `ClaimEvidenceMap`.
- `Writer`: handles quick rewrites and non-academic drafts.
- `AcademicWriter`: drafts academic paper sections from `AcademicBrief`, `Outline`, and source notes.
- `Reviewer`: creates structured non-academic `ReviewReport` artifacts.
- `AcademicReviewer`: reviews research question clarity, contribution, novelty, claim/evidence
  alignment, citation support, method/result risks, limitations, reproducibility, and readiness.
- `CitationChecker`: returns citation and claim-evidence risk warnings without pretending to verify
  missing sources.
- `Editor`: creates `RevisionPlan` and applies conservative traceable revisions with `ChangeLog`.
- `PaperHarnessBridge`: optional bridge that persists academic brief-derived paper, outline, and
  source material into the existing `/papers/...` store.

The paper bridge is opt-in through `persist_to_paper_harness`. By default, a generic academic
writing run does not create or mutate a paper project. When enabled, the bridge either creates a new
`Paper` or attaches to the supplied `paper_id`, persists outline sections as `OutlineNode` rows, and
persists source notes as `SourceMaterial` rows. Existing paper outlines are reused instead of
silently overwritten.

The bridge can now selectively continue into the existing paper pipeline through
`paper_harness_pipeline`:

- `generate_contracts`: calls the existing `ContractGenerator` for draftable sections.
- `extract_evidence`: calls the existing `EvidenceExtractor` for persisted source material.
- `build_evidence_packs`: calls the existing `EvidencePackBuilder`.
- `generate_section_drafts`: calls the existing `DraftingService`.
- `assemble_manuscript`: calls the existing `AssemblyService`.
- `export_formats`: calls the existing export path for the requested formats without writing files
  by default.

Each stage records IDs for created or reused artifacts plus `skipped_steps` and `pipeline_errors`.
This keeps the bridge auditable and avoids pretending a downstream stage succeeded when source
material, evidence, or drafts are missing.
