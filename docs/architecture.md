# Paper Harness v1 Architecture

Paper Harness is a local-first, section-centric backend for producing academic paper drafts through explicit workflow artifacts. The current implementation covers Milestones 1-5 with deterministic placeholder logic. It does not call any real LLM provider.

## Current Shape

The implemented product surface lives in `apps/api`, a FastAPI application backed by SQLModel and SQLite. Routes are thin and delegate workflow rules to service modules. The packages under `packages/*` still mark future reusable library boundaries; the active behavior is currently in the API app.

Implemented backend capabilities:

- Create paper projects.
- Generate deterministic outlines for conceptual, survey, and empirical papers.
- Generate deterministic section contracts.
- Register source material and create/extract evidence items from text.
- Build section evidence packs.
- Generate deterministic section drafts from contracts and evidence packs.
- Review section drafts and persist structured review comments.
- Create revision tasks from review comments.
- Revise section drafts into new versions.
- Assemble current section drafts into versioned manuscript artifacts.
- Run deterministic global manuscript review.
- Persist Markdown and simple LaTeX export artifacts.

## Principles

- Evidence before writing.
- Section before full manuscript.
- Review before revision.
- Versioned artifacts instead of in-place overwrites.
- Explicit lifecycle transitions for papers and sections.
- Deterministic placeholder logic until real model/provider integration is added.

## Implemented Layers

### API And Persistence

Primary modules:

- `apps/api/app/main.py`: app creation and route registration.
- `apps/api/app/db/`: SQLite/SQLModel session and schema creation.
- `apps/api/app/models/`: persisted models and enums.
- `apps/api/app/schemas/`: typed request/response schemas.
- `apps/api/app/api/routes/`: HTTP route handlers.
- `apps/api/app/state_machine/`: paper and section transition maps.

### Planning

Primary modules:

- `apps/api/app/services/planner/outline_generator.py`
- `apps/api/app/services/planner/contract_generator.py`

Current behavior:

- Uses deterministic templates keyed by `PaperType`.
- Creates outline nodes with stable titles, levels, order indexes, goals, expected claims, and word budgets.
- Creates section contracts from section metadata and optional user constraints.

Future replacement point:

- Replace deterministic template methods with planner-backed model calls while preserving persisted `OutlineNode` and `SectionContract` schemas.

### Research And Evidence

Primary modules:

- `apps/api/app/services/research/source_registry.py`
- `apps/api/app/services/research/evidence_extractor.py`
- `apps/api/app/services/research/evidence_pack_builder.py`

Current behavior:

- Registers text source material.
- Splits text into up to five sentence chunks as evidence items.
- Builds evidence packs by deterministic scoring against section and contract terms.

Future replacement point:

- Add real file upload/parsing, citation metadata extraction, provenance validation, and stronger evidence ranking.

### Writer

Primary modules:

- `apps/api/app/services/drafting.py`
- `apps/api/app/services/writer/draft_generator.py`
- `apps/api/app/services/writer/revision_generator.py`

Current behavior:

- Draft generation requires `evidence_ready`, an active contract, and an active non-empty evidence pack.
- Initial draft generation creates one active version and rejects repeated initial generation.
- Revision creates a new active draft version, supersedes the previous active draft, resolves selected comments, and completes selected revision tasks.

Future replacement point:

- Replace deterministic draft/revision text construction with a writer adapter that receives the same contract, evidence, review, and revision-task context.

### Reviewer And Verifier

Primary modules:

- `apps/api/app/services/review.py`
- `apps/api/app/services/reviewer/draft_reviewer.py`
- `apps/api/app/services/reviewer/revision_task_builder.py`
- `apps/api/app/services/verifier/support_checker.py`

Current behavior:

- Reviews only current active section drafts.
- Persists `ReviewComment` records.
- Automatically creates one `RevisionTask` per review comment.
- Checks evidence IDs, missing citations, weak structure, short drafts, missing transitions, redundancy, and overclaiming terms.

Future replacement point:

- Replace heuristic review/verifier checks with model-backed structured review and evidence-alignment verification.

### Editor, Assembly, And Export

Primary modules:

- `apps/api/app/services/assembly.py`
- `apps/api/app/services/editor/manuscript_assembler.py`
- `apps/api/app/services/editor/manuscript_reviewer.py`
- `apps/api/app/services/editor/export_generator.py`

Current behavior:

- Assembles outline nodes in stable tree pre-order.
- Uses current active section drafts by default.
- Includes placeholder blocks and warnings for sections without usable drafts.
- Creates versioned `AssembledManuscript` artifacts.
- Runs deterministic global review and persists `ManuscriptIssue` records.
- Persists Markdown exports and simple LaTeX exports as database artifacts with deterministic `data/exports/...` references.

Future replacement point:

- Add section locking, physical file writing, bibliography generation, DOCX/export adapters, and stronger global coherence review.

## Module Boundaries

`apps/api` is the implemented backend. It owns:

- HTTP routes.
- Database models and sessions.
- Service orchestration.
- Deterministic placeholder agents/services.
- API tests.

`apps/web` and `apps/worker` are scaffolds only.

`packages/*` are package boundaries for future extraction/reuse:

- `packages/core`
- `packages/planner`
- `packages/research`
- `packages/drafting`
- `packages/review`
- `packages/verify`
- `packages/editor`
- `packages/memory`
- `packages/export`

## Data Storage

The local prototype uses SQLite through SQLModel. Export artifacts currently persist their content and path reference in the database; they do not yet write physical files under `data/exports`.

## Runtime And Tests

Run the backend:

```bash
uvicorn app.main:app --app-dir apps/api --reload
```

Run the full test suite:

```bash
pytest
```

Run API tests only:

```bash
pytest apps/api/tests
```
