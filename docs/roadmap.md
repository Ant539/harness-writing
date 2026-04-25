# Roadmap

This roadmap suggests the next useful implementation directions after Milestone 6. It is intentionally practical and ordered around maintainability.

## 1. Stronger Workflow Guards

- Tighten section approval policy and reviewer assignment.
- Make assembly default to locked sections when approval-gated delivery is requested.
- Add manuscript issue resolution.
- Clarify paper-level status transitions during section drafting/review/revision.

## 2. Real Model Integration Boundaries

Replace deterministic logic behind existing service boundaries:

- Planner: outline and section contract generation.
- Researcher: source parsing, evidence extraction, evidence ranking.
- Writer: draft and revision generation.
- Reviewer: structured section review.
- Verifier: claim-to-evidence alignment and citation verification.
- Editor: global manuscript review, whole-paper consistency repair, and style normalization.

Recommended approach:

- Add adapters behind the existing services instead of changing route contracts.
- Keep deterministic implementations available for tests.
- Persist prompts, inputs, outputs, and model metadata when model calls are introduced.

## 3. Evidence And Citation Pipeline

- Add file upload and text extraction.
- Add structured source metadata and citation records.
- Add bibliography export support.
- Extend first-pass provenance validation into semantic claim-to-evidence checks.
- Add citation style handling.

## 4. Export Pipeline

- Write export artifacts to physical files under `data/exports`.
- Add Markdown download/retrieval helpers.
- Add robust LaTeX output with bibliography, labels, and references.
- Consider DOCX only after Markdown/LaTeX paths are stable.

## 5. Frontend Operator Console

- Build a minimal workflow UI.
- Show paper/section statuses.
- Expose outline, contract, evidence pack, draft, review, revision, assembly, and export operations.
- Make missing prerequisites visible before users trigger guarded operations.

## 6. Productionization

- Add migrations.
- Add structured error responses.
- Add logging around service operations.
- Add background jobs for future long-running model calls.
- Add configuration for local/prod database paths.
- Add authentication only if moving beyond single-user local use.

## 7. Package Extraction

Once API behavior stabilizes, move reusable logic from `apps/api/app/services/*` into the matching `packages/*` boundaries:

- planner logic to `packages/planner`
- research logic to `packages/research`
- drafting logic to `packages/drafting`
- review logic to `packages/review`
- verification logic to `packages/verify`
- editor/export logic to `packages/editor` and `packages/export`
