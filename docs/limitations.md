# Current Limitations

The project is usable as a local deterministic backend prototype, not as a production manuscript system.

## Product Limitations

- Model-backed planner/writer/reviewer integration exists, but prompt tuning, workflow orchestration, and broader model-backed roles are still incomplete.
- Broader document types now affect planning, prompts, outlines, and section contracts, but the
  public API and database model names are still paper-centric.
- No frontend/operator console yet.
- Section locking and approval endpoints exist, but approval policy, reviewer assignment, and
  frontend workflow are still basic.
- No final submission workflow.
- No manuscript issue resolution endpoint yet.
- No full paragraph-level drafting workflow despite the `paragraph` draft kind.
- No multi-user collaboration, permissions, or audit users.

## Evidence And Citation Limitations

- No real binary file upload pipeline.
- Source registration currently uses text content plus metadata.
- Evidence extraction is simple sentence splitting, not semantic extraction.
- Evidence pack ranking is keyword/term overlap, not retrieval or citation-aware selection.
- Citation handling is limited to stored `citation_key` values.
- Citation/provenance verification is structural and deterministic; there is still no bibliography
  database, bibliography generation, citation style rendering, or semantic entailment check.

## Drafting And Review Limitations

- Drafting can use a configured model provider, but the prompt system and workflow runner are not mature yet.
- Review can use a configured model provider, but heuristic behavior is still the default baseline for many paths.
- Verifier checks evidence IDs and citations but does not perform factual entailment.
- Revision can use a configured model provider, but the revision loop is not yet driven by a persisted plan or prompt pack.
- Whole-paper consistency review catches deterministic terminology, contribution, and
  abstract/conclusion alignment problems, but it does not yet perform semantic restructuring.

## Assembly And Export Limitations

- Assembly can exclude unlocked sections, but current active drafts remain the default until
  approval-gated assembly policy is tightened.
- Missing sections are included as placeholders; this is intentional but not final editorial behavior.
- Export artifacts are persisted in the database with a deterministic path reference.
- Export artifacts can be written to physical files when requested, but export file handling is not yet part of a higher-level workflow runner.
- LaTeX export is minimal and does not handle bibliography, figures, tables, labels, or cross references.

## Engineering Limitations

- No database migrations yet; schema creation is direct via SQLModel metadata.
- Error responses are FastAPI defaults with `detail` strings, not the aspirational wrapped error object.
- Token accounting depends on provider response metadata, and cost is persisted only when the
  provider explicitly returns USD cost; there is no maintained model pricing table.
- Package folders under `packages/*` are mostly scaffolds; active logic lives in `apps/api`.
- Background worker is not connected to long-running jobs.
- No authentication or environment-specific deployment configuration.
