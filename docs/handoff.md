# Handoff Notes

Use this as the quick-start context for a future Codex thread.

## What This Repo Is

Paper Harness is a FastAPI/SQLModel local backend for controlled academic paper drafting. It persists every major workflow artifact and uses deterministic placeholder services instead of real LLM calls.

## Start Here

Read these first:

- `docs/status.md`
- `docs/limitations.md`
- `docs/roadmap.md`
- `apps/api/README.md`
- `apps/api/tests/test_end_to_end_smoke.py`

## Most Important Backend Files

- `apps/api/app/models/`: persisted schema.
- `apps/api/app/schemas/`: API request/response types.
- `apps/api/app/api/routes/`: route surface.
- `apps/api/app/services/`: workflow logic.
- `apps/api/app/state_machine/transitions.py`: lifecycle maps.
- `apps/api/tests/`: behavior documentation through tests.

## Current Happy Path

1. `POST /papers`
2. `POST /papers/{paper_id}/generate-outline`
3. `POST /sections/{section_id}/generate-contract`
4. `POST /papers/{paper_id}/evidence`
5. `POST /sections/{section_id}/build-evidence-pack`
6. `POST /sections/{section_id}/draft`
7. `POST /sections/{section_id}/review`
8. `POST /sections/{section_id}/revise`
9. `POST /papers/{paper_id}/assemble`
10. `POST /papers/{paper_id}/export`

## Keep In Mind

- Do not add real model calls without preserving deterministic test doubles.
- Keep routes thin; put workflow rules in services.
- Add typed schemas for every new request/response.
- Prefer versioned artifacts over mutation.
- Update docs and tests together when workflow behavior changes.
