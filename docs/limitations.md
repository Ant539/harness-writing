# Current Limitations

The project is usable as a local deterministic backend prototype, not as a production manuscript system.

## Product Limitations

- Model-backed planner/writer/reviewer integration exists, but prompt tuning, workflow orchestration, and broader model-backed roles are still incomplete.
- No frontend/operator console yet.
- No full section locking or approval endpoint yet.
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
- No bibliography database or bibliography generation.

## Drafting And Review Limitations

- Drafting can use a configured model provider, but the prompt system and workflow runner are not mature yet.
- Review can use a configured model provider, but heuristic behavior is still the default baseline for many paths.
- Verifier checks evidence IDs and citations but does not perform factual entailment.
- Revision can use a configured model provider, but the revision loop is not yet driven by a persisted plan or prompt pack.

## Assembly And Export Limitations

- Assembly uses current active drafts by default because section locking is not fully implemented.
- Missing sections are included as placeholders; this is intentional but not final editorial behavior.
- Export artifacts are persisted in the database with a deterministic path reference.
- Export artifacts can be written to physical files when requested, but export file handling is not yet part of a higher-level workflow runner.
- LaTeX export is minimal and does not handle bibliography, figures, tables, labels, or cross references.

## Engineering Limitations

- No database migrations yet; schema creation is direct via SQLModel metadata.
- Error responses are FastAPI defaults with `detail` strings, not the aspirational wrapped error object.
- Package folders under `packages/*` are mostly scaffolds; active logic lives in `apps/api`.
- Background worker is not connected to long-running jobs.
- No authentication or environment-specific deployment configuration.
