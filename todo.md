# Paper Harness Development TODO

This file tracks work on the Paper Harness system itself.

It is intentionally separate from runtime execution state such as papers, drafts, workflow runs,
and export artifacts. Paper execution should persist in the application data model and `data/`
artifacts, not in this file.

## Active

- [x] Add a discovery phase foundation that persists the user's document goal, audience, constraints, and success criteria before planning.
- [x] Implement a persisted planning artifact and/or planning run record.
- [x] Add a unified workflow runner that begins with discovery and planning, then uses planner output to decide actions.
- [x] Add prompt assembly foundations that compose prompts from use case, task profile, source mode, workflow stage, and risk profile.
- [x] Add section/unit action execution for `preserve`, `polish`, `rewrite`, `repair`, `draft`, and `blocked`.
- [x] Add prompt packs for planner, writer, reviewer, reviser, verifier, and global editor.
- [x] Add prompt versioning, prompt logging, and prompt module persistence for model-backed runs.
- [x] Add a template-aware JCST export path that preserves the original submission template structure.
- [x] Add manuscript compile validation for exported LaTeX.

## Near Term

- [ ] Expand discovery from a persisted snapshot endpoint into a true conversational clarification loop.
- [ ] Add workflow run resume/retry support on top of the persisted step status model.
- [ ] Add persistent user interaction and clarification state.
- [ ] Add section locking and approval workflows.
- [ ] Add stronger citation and evidence provenance checks.
- [ ] Add whole-paper consistency review for terminology, contribution statements, and abstract/conclusion alignment.
- [ ] Add provider cost and token accounting where provider responses expose usage metadata.
- [ ] Generalize the system beyond papers into student reports, theses, proposals, and structured technical documents.

## Later

- [ ] Add a frontend/operator console for workflow orchestration.
- [ ] Move stabilized service logic into `packages/*`.
- [ ] Add migrations and production-ready operational logging.

## Done

- [x] Add configurable LLM providers with an OpenAI-compatible path plus Anthropic and Gemini adapters.
- [x] Keep deterministic mode available for tests and offline development.
- [x] Document the unified planning rule: source mode must be decided in the planning phase, not by separate hard-coded workflows.
- [x] Separate development tracking from runtime workflow state with this repository-level `todo.md`.
- [x] Record the broader product target: a general-purpose writing agent with academic paper revision as one current test case.
