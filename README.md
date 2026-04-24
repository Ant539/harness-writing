# Paper Harness

Paper Harness is evolving from an academic-paper prototype into a plan-driven writing agent for
structured long-form documents.

This repository contains the local-first backend scaffold for a writing-agent system. Academic paper
workflows are currently the strongest test case, but the longer-term target is broader: reports,
theses, proposals, and other structured long-form writing. The current backend implements
deterministic workflow behavior plus configurable model-backed planner/writer/reviewer calls, while
still leaving discovery, prompt assembly, the full unified agent workflow runner, and final
delivery pipelines to be completed.

## Workspace Layout

- `apps/api`: FastAPI backend scaffold.
- `apps/web`: Next.js frontend scaffold.
- `apps/worker`: background worker scaffold.
- `packages/core`: shared schemas, enums, and interface types.
- `packages/planner`: planning package boundary.
- `packages/research`: evidence package boundary.
- `packages/drafting`: drafting package boundary.
- `packages/review`: review package boundary.
- `packages/verify`: verification package boundary.
- `packages/editor`: editing package boundary.
- `packages/memory`: structured memory package boundary.
- `packages/export`: export package boundary.
- `configs`: prompt, style, and workflow configuration placeholders.
- `data`: local artifact directories.
- `docs`: architecture and implementation documentation.
- `todo.md`: repository-level development tracking for the system itself, kept separate from runtime paper execution.

## Current Status

Implemented backend milestones:

- Milestone 1: core data models, CRUD routes, and lifecycle state machines.
- Milestone 2: deterministic outline and section contract generation.
- Milestone 3: deterministic source/evidence extraction and evidence pack building.
- Milestone 4: deterministic section draft generation, structured review comments, revision tasks, and draft versioning.
- Milestone 5: deterministic manuscript assembly, persisted manuscript versions, global manuscript issues, and Markdown/simple LaTeX exports.
- Milestone 6: current-state docs, limitations, roadmap, handoff notes, and end-to-end smoke coverage.
- Post-Milestone 6 extension: configurable model providers for OpenAI-compatible endpoints, GLM coding-plan defaults, Anthropic, and Gemini.

Milestone 5 behavior:

- `POST /papers/{paper_id}/assemble` creates a new active `AssembledManuscript` version and supersedes the previous active version.
- Assembly traverses the outline tree in stable pre-order and uses current active section drafts.
- Sections without usable drafts are included as placeholder blocks with persisted warnings.
- `POST /papers/{paper_id}/global-review` persists manuscript-level issues for missing drafts, unresolved section reviews, missing introduction/conclusion sections, transition gaps, terminology drift, and duplicate sibling ordering.
- `POST /papers/{paper_id}/export` persists deterministic Markdown or simple LaTeX export content with a `data/exports/...` artifact reference.

Run the API:

```bash
cd apps/api
uvicorn app.main:app --reload
```

Run tests from the repository root:

```bash
pytest
```

For a concise continuation guide, start with `docs/handoff.md`. For the current implementation
target and remaining work, read `docs/development-plan.md`. For product direction, see
`docs/use-cases.md` and `configs/prompts/foundation.md`.
