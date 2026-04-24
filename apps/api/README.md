# Paper Harness API

FastAPI backend for the Paper Harness local prototype.

The API currently implements Milestones 1-6 with deterministic local behavior by default. It can also call a configured LLM provider for outline, contract, draft, review, and revision generation.

## Setup

From the repository root:

```bash
pip install -e "apps/api[dev]"
```

Alternative workspace tooling may also work if you use `uv`, but the command above is the lowest-friction path for the current scaffold.

## Run

From the repository root:

```bash
uvicorn app.main:app --app-dir apps/api --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

## LLM Providers

By default, `PAPER_HARNESS_LLM_PROVIDER=none` keeps all agent-like behavior deterministic and offline. To call a model, configure one of:

- `openai_compatible`: any OpenAI-compatible `/chat/completions` endpoint.
- `glm` or `zhipu`: GLM general endpoint.
- `glm_coding`: GLM coding-plan endpoint.
- `deepseek`, `qwen`, `openrouter`, `ollama`, `vllm`, `lmstudio`, or `local`: OpenAI-compatible aliases with sensible default base URLs where possible.
- `anthropic`: direct Anthropic Messages API.
- `gemini`: direct Gemini `generateContent` API.

GLM coding-plan example:

```bash
export PAPER_HARNESS_LLM_PROVIDER=glm_coding
export PAPER_HARNESS_LLM_MODEL=glm-5.1
export PAPER_HARNESS_LLM_API_KEY_ENV=ZAI_API_KEY
export ZAI_API_KEY=your_glm_api_key
```

For any other OpenAI-compatible provider:

```bash
export PAPER_HARNESS_LLM_PROVIDER=openai_compatible
export PAPER_HARNESS_LLM_BASE_URL=https://provider.example.com/v1
export PAPER_HARNESS_LLM_MODEL=provider-model-name
export PAPER_HARNESS_LLM_API_KEY_ENV=PROVIDER_API_KEY
export PROVIDER_API_KEY=your_provider_api_key
```

The configured model is used behind the same service boundaries as the deterministic implementation. Tests should normally leave `PAPER_HARNESS_LLM_PROVIDER=none`.

## Test And Lint

API tests:

```bash
pytest apps/api/tests
```

Full workspace tests:

```bash
pytest
```

Lint API code:

```bash
ruff check apps/api/app apps/api/tests
```

## Implemented Milestones

- Milestone 1: core SQLModel models, CRUD routes, lifecycle enums, transition helpers, and database initialization.
- Milestone 2: deterministic outline and section contract generation.
- Milestone 3: text source registration, deterministic evidence extraction, evidence item CRUD, and evidence pack building.
- Milestone 4: deterministic section drafting, structured review comments, revision tasks, and draft versioning.
- Milestone 5: manuscript assembly, global manuscript review, Markdown export, and simple LaTeX export.
- Milestone 6: documentation closure, handoff notes, and workflow smoke coverage.

## Lifecycle Summary

Paper lifecycle:

```text
idea -> outline_ready -> evidence_in_progress -> drafting_in_progress
-> section_review_in_progress -> revision_in_progress -> assembly_ready
-> global_review -> final_revision -> submission_ready
```

Section lifecycle:

```text
planned -> contract_ready -> evidence_ready -> drafted
-> reviewed -> revision_required -> revised -> locked
```

Important current behavior:

- Outline generation moves a paper from `idea` to `outline_ready`.
- Contract generation moves a section from `planned` to `contract_ready`.
- Evidence pack building moves a section from `contract_ready` to `evidence_ready`.
- Draft generation moves a section from `evidence_ready` to `drafted`.
- Review moves a section to `reviewed`, then to `revision_required` when comments exist.
- Revision moves a section to `revised`.
- Assembly advances a paper to `assembly_ready`.
- Global review advances a paper to `global_review`, then `final_revision` if issues exist.

## Key API Groups

- Papers and style guides: `/papers`, `/papers/{paper_id}/style-guide`
- Outline and contracts: `/papers/{paper_id}/generate-outline`, `/sections/{section_id}/generate-contract`
- Evidence: `/papers/{paper_id}/sources`, `/sources/{source_id}/extract-evidence`, `/papers/{paper_id}/evidence`, `/sections/{section_id}/build-evidence-pack`
- Drafting and revision: `/sections/{section_id}/draft`, `/sections/{section_id}/revise`, `/sections/{section_id}/drafts`
- Review and revision tasks: `/sections/{section_id}/review`, `/drafts/{draft_id}/review`, `/sections/{section_id}/revision-tasks`
- Assembly and export: `/papers/{paper_id}/assemble`, `/papers/{paper_id}/global-review`, `/papers/{paper_id}/export`

See `docs/api-spec.md` for the complete implemented surface.

## Deterministic Mode Notes

With `PAPER_HARNESS_LLM_PROVIDER=none`, all agent-like behavior is deterministic and local:

- Planner templates create outlines and contracts.
- Research services split source text into sentence evidence and rank evidence by keyword overlap.
- Writer services build draft/revision prose from contracts, evidence snippets, and review context.
- Reviewer/verifier services use heuristic checks.
- Editor services assemble current active section drafts, run global heuristic review, and generate Markdown/simple LaTeX export content.

When a provider is configured, planner, writer, and reviewer generation calls use the model while preserving the same persisted artifacts and lifecycle guards.

## Current Limitations

- Model-backed generation is available, but provider-specific prompt tuning and cost controls are still minimal.
- No binary file upload/parsing pipeline.
- No full section locking endpoint yet.
- No advanced bibliography generation.
- Export artifacts are persisted in the database, and can also be written to physical files when `write_file=true` is requested. There is not yet a higher-level workflow runner that manages export file writing automatically.
- No frontend behavior is implemented yet.

See `docs/limitations.md` and `docs/roadmap.md` for more detail.
