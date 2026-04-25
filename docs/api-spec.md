# Paper Harness v1 API Spec

This document describes the implemented FastAPI surface after Milestones 1-5 plus the first
discovery/planning persistence foundation. The default path remains deterministic, but some
generation endpoints can optionally call a configured LLM provider.

## Conventions

- IDs are UUIDs.
- Timestamps are ISO 8601 strings.
- Routes return JSON.
- Route handlers are thin and delegate workflow guards to services.
- Most invalid workflow operations currently return FastAPI `detail` strings rather than the aspirational wrapped error body.

## Health

### `GET /health`

Returns:

- `{"status": "ok"}`

## Papers And Style Guides

### `POST /papers`

Creates a paper.

Initial status:

- `idea`

### `GET /papers`

Lists papers.

### `GET /papers/{paper_id}`

Gets one paper.

### `PATCH /papers/{paper_id}`

Updates paper metadata or status. Status changes pass the paper state machine.

### `DELETE /papers/{paper_id}`

Deletes a paper record.

### `POST /papers/{paper_id}/transition`

Explicit paper status transition.

### `POST /papers/{paper_id}/style-guide`

Creates a style guide record.

### `GET /papers/{paper_id}/style-guide`

Gets a paper style guide if present.

### `PATCH /papers/style-guides/{style_guide_id}`

Updates a style guide.

### `DELETE /papers/style-guides/{style_guide_id}`

Deletes a style guide.

## Discovery And Planning

### `POST /papers/{paper_id}/discovery`

Persists the latest discovery snapshot for a paper.

Behavior:

- Stores user-goal clarification fields such as document type, audience, success criteria,
  constraints, and current document state.
- Supersedes the previous active discovery snapshot for the paper.
- Keeps the route thin by delegating normalization and persistence to the planning service.

### `GET /papers/{paper_id}/discovery`

Returns the latest persisted discovery snapshot for the paper, or `null` if none exists yet.

### `POST /papers/{paper_id}/discovery/clarifications`

Creates persisted clarification requests for the active discovery loop.

Behavior:

- Uses explicit questions when supplied.
- Otherwise uses unanswered `clarifying_questions` from the latest discovery record.
- If no saved questions exist, creates conservative questions for missing goal, audience, success
  criteria, or source-state fields.
- Writes assistant `UserInteraction` records for each clarification question.

### `POST /clarifications/{clarification_id}/answer`

Stores a user answer to a clarification request.

Behavior:

- Creates a user `UserInteraction` record.
- Marks the clarification request as `answered`.
- Copies the question/answer pair into the active discovery record's metadata when the clarification
  is discovery-linked.

### `GET /papers/{paper_id}/clarifications`

Lists clarification requests for a paper. Supports optional `status` filtering.

### `POST /papers/{paper_id}/interactions`

Persists a user, assistant, or system interaction record for a paper.

### `GET /papers/{paper_id}/interactions`

Lists persisted interaction records for a paper in chronological order.

### `POST /papers/{paper_id}/plan`

Builds and persists a structured workflow plan.

Behavior:

- Uses the latest discovery snapshot by default, or an explicit `discovery_id` if supplied.
- Produces structured fields:
  - `task_profile`
  - `entry_strategy`
  - `paper_plan`
  - `section_plans`
  - `prompt_assembly_hints`
- Falls back to deterministic planning when no model provider is configured.
- If a model provider is configured, the service attempts structured planner output and falls back
  conservatively if parsing or provider execution fails.
- Supersedes the previous active plan for the paper.

### `GET /papers/{paper_id}/plan`

Returns the latest persisted planning run for the paper, or `null` if no plan has been generated.

## Workflow Runs

### `POST /papers/{paper_id}/workflow-runs`

Starts a unified workflow run and persists step records.

Behavior:

- Creates or reuses discovery.
- Creates a planning run.
- Optionally auto-executes the safest deterministic workflow steps:
  - outline generation when the plan says outline work is needed
  - replanning after outline generation
  - deterministic contract generation for non-blocked sections when the section lifecycle allows it
  - planner-driven section actions:
    - `preserve`: records that the active draft should not be destructively regenerated
    - `draft`: builds an evidence pack when evidence is available and creates a section draft
    - `repair`: runs revision from review context when available, otherwise writes a conservative
      fallback revision artifact
    - `rewrite` and `polish`: create traceable revised draft versions from existing drafts when a
      full review/revision path is not yet available
    - `blocked`: persists an explicit skipped step with the planner reason
- Supports `dry_run=true` to persist pending execution steps without mutating paper artifacts.
- Persists workflow-run status plus step-level status (`pending`, `running`, `completed`, `failed`,
  `skipped`).
- Section action step results include the planner action, reason, skip/fallback reason where
  applicable, and draft/evidence artifact IDs when execution creates or reuses them.

### `GET /papers/{paper_id}/workflow-runs`

Lists persisted workflow runs for a paper.

### `GET /workflow-runs/{run_id}`

Returns one workflow run with its persisted steps.

When the runner encounters an unknown plan, blocked section, or approval-required checkpoint, it
sets the workflow run status to `waiting_for_user`, stores the active checkpoint ID in run metadata,
and stops before further execution.

### `POST /workflow-runs/{run_id}/resume`

Resumes a workflow run that is currently `waiting_for_user`.

Behavior:

- Rejects resume while any checkpoint for the run is still pending.
- Replans by default, carrying an optional `additional_context` note into the planner.
- Supports `auto_execute` and `section_limit` overrides for the resumed pass.
- Appends new workflow-step records to the existing run rather than creating a new run.
- Completes the run when resumed execution finishes, or pauses again with a new checkpoint if the
  plan is still unknown or another section blocks execution.

### `POST /workflow-steps/{step_id}/retry`

Retries a persisted workflow step by appending a new retry step to the same workflow run.

Current supported retry step kinds:

- `plan` / `replan`
- `generate_outline`
- `generate_contract`
- `assemble_prompts`
- `section_action`

Behavior:

- Rejects retry while the workflow run has pending checkpoints.
- Replans before retry by default.
- Returns the workflow run, the newly appended retry step, and the current plan.

### `POST /papers/{paper_id}/workflow-checkpoints`

Creates a workflow checkpoint manually.

### `GET /papers/{paper_id}/workflow-checkpoints`

Lists workflow checkpoints for a paper. Supports optional `status` filtering.

### `POST /workflow-checkpoints/{checkpoint_id}/resolve`

Marks a checkpoint as resolved and persists an optional resolution note.

## Prompt Assemblies

### `POST /papers/{paper_id}/prompt-assemblies`

Builds and persists a stage-specific prompt assembly artifact.

Behavior:

- Uses the latest planning run by default, or an explicit `planning_run_id`.
- Composes prompt modules from planning outputs such as task profile, source mode, stage
  instructions, style guidance, safety rules, and verification emphasis.
- Injects the versioned stage prompt pack from `configs/prompt-packs/v1.json`.
- Persists:
  - module keys
  - module contents
  - assembled system prompt
  - assembled user/runtime prompt
  - prompt hash
  - prompt pack version
- Writes a prompt execution log entry for the assembled prompt.
- Supersedes the previous active artifact for the same paper/stage/section scope and increments
  the artifact version.

### `GET /papers/{paper_id}/prompt-assemblies`

Lists prompt assembly artifacts for a paper. Supports optional `stage` filtering.

### `GET /prompt-assemblies/{artifact_id}`

Returns one persisted prompt assembly artifact.

### `GET /papers/{paper_id}/prompt-logs`

Lists persisted prompt execution logs for a paper. Supports optional `stage` filtering.

Current logged events:

- prompt assembly creation for all stages
- model-backed planner provider calls, including provider/model, prompt hash, response text, and
  failed-provider errors when the planner falls back
- provider usage metadata when exposed by the provider response, normalized into
  `prompt_tokens`, `completion_tokens`, `total_tokens`, `cached_tokens`, `reasoning_tokens`, and
  `cost_usd`; provider-specific raw usage is also kept under `usage.provider_usage`

### `GET /prompt-logs/{log_id}`

Returns one persisted prompt execution log.

## Outline And Section Contracts

### `POST /papers/{paper_id}/generate-outline`

Generates deterministic outline nodes.

Behavior:

- Rejects duplicate outline generation.
- Moves paper from `idea` to `outline_ready`.
- Creates sections as `planned`.
- Accepts optional `document_type` (`academic_paper`, `report`, `thesis`, `proposal`,
  `technical_document`, or `unknown`).
- Uses document-type-specific deterministic templates for reports, theses, proposals, and
  technical documents instead of always using academic paper sections.
- Persists generated section metadata with the selected document type so later contract generation
  can adapt questions, tone, and purpose text.

### `GET /papers/{paper_id}/outline`

Returns the paper outline.

### `POST /sections`

Creates an outline node with `paper_id` in the body.

### `POST /papers/{paper_id}/sections`

Creates an outline node under a paper.

### `GET /papers/{paper_id}/sections`

Lists sections for a paper.

### `GET /sections/{section_id}`

Gets one section.

### `PATCH /sections/{section_id}`

Updates section metadata or status. Status changes pass the section state machine and special guards where implemented.

### `DELETE /sections/{section_id}`

Deletes a section.

### `POST /sections/{section_id}/transition`

Explicit section status transition.

### `POST /sections/{section_id}/approval-request`

Creates a pending approval request for the current active section draft.

Behavior:

- Requires an active section draft.
- May reference a workflow checkpoint that belongs to the same paper and section.
- Persists requested-by, note, metadata, draft ID, and checkpoint linkage.

### `POST /sections/{section_id}/approve`

Approves the current active section draft and locks the section.

Behavior:

- Requires an active section draft.
- Requires section status `reviewed` or `revised`.
- Rejects approval while the current draft has unresolved review comments.
- Supersedes any pending approval requests for the section.
- Moves the section to `locked`.
- If a workflow checkpoint ID is supplied, marks that checkpoint resolved.

### `POST /sections/{section_id}/request-changes`

Records an approval decision that requests further section changes.

Behavior:

- Requires an active section draft.
- Rejects locked sections; unlock first before requesting changes.
- Supersedes pending approval requests for the section.
- If a workflow checkpoint ID is supplied, marks that checkpoint resolved.

### `POST /sections/{section_id}/unlock`

Unlocks a locked section for another editing/review pass.

Behavior:

- Requires section status `locked`.
- Moves the section back to `reviewed`.
- Persists an `unlocked` approval-history record.

### `GET /sections/{section_id}/approvals`

Lists section approval history in creation order.

### `GET /section-approvals/{approval_id}`

Returns one section approval record.

### `POST /sections/{section_id}/generate-contract`

Generates or regenerates a deterministic section contract.

Behavior:

- Creates a contract for `planned` or `contract_ready` sections.
- Moves `planned -> contract_ready`.
- Rejects duplicate generation unless `force=true`.

### `POST /sections/{section_id}/contract`

Manually creates a section contract.

### `GET /sections/{section_id}/contract`

Gets a section contract if present.

### `GET /contracts/{contract_id}`

Gets a contract.

### `PATCH /contracts/{contract_id}`

Updates a contract.

### `DELETE /contracts/{contract_id}`

Deletes a contract.

## Evidence

### `POST /papers/{paper_id}/sources`

Registers text source material.

### `GET /papers/{paper_id}/sources`

Lists source material for a paper.

### `GET /sources/{source_id}`

Gets one source material record.

### `PATCH /sources/{source_id}`

Updates source material.

### `DELETE /sources/{source_id}`

Deletes source material.

### `POST /sources/{source_id}/extract-evidence`

Creates evidence items from source text by deterministic sentence splitting.

### `POST /papers/{paper_id}/evidence/upload`

Bulk creates evidence items.

### `POST /papers/{paper_id}/evidence`

Creates one evidence item.

### `GET /papers/{paper_id}/evidence`

Lists evidence items for a paper.

### `GET /evidence/{evidence_id}`

Gets one evidence item.

### `PATCH /evidence/{evidence_id}`

Updates an evidence item.

### `DELETE /evidence/{evidence_id}`

Deletes an evidence item.

### `POST /sections/{section_id}/build-evidence-pack`

Builds a deterministic section evidence pack.

Behavior:

- Requires a section contract.
- Requires available evidence.
- Moves `contract_ready -> evidence_ready`.
- Rejects duplicate builds unless `force=true`.

### `POST /sections/{section_id}/verify-evidence`

Runs deterministic citation and evidence provenance checks for the current active section draft.

Behavior:

- Requires a current active section draft.
- Requires a section contract.
- Requires an active evidence pack.
- Reports structured issues with `code`, `severity`, `message`, optional `evidence_id`, and
  optional `citation_key`.
- Checks draft support IDs against the active evidence pack.
- Checks required citations, unsupported bracketed citations, and cited evidence missing from
  `supported_evidence_ids`.
- Checks evidence assignment/provenance, including section mismatch, missing `source_ref` and
  `source_material_id`, invalid/missing source material references, source paper mismatch, and
  source/evidence citation-key mismatch.

### `POST /sections/{section_id}/evidence-packs`

Manually creates a section evidence pack.

### `GET /sections/{section_id}/evidence-packs`

Lists evidence packs for a section.

### `GET /sections/{section_id}/evidence-pack`

Gets the active evidence pack if present.

### `GET /evidence-packs/{pack_id}`

Gets one evidence pack.

### `PATCH /evidence-packs/{pack_id}`

Updates an evidence pack.

### `POST /evidence-packs/{pack_id}/items`

Adds an evidence item to a pack.

### `DELETE /evidence-packs/{pack_id}/items/{evidence_id}`

Removes an evidence item from a pack.

### `DELETE /evidence-packs/{pack_id}`

Deletes an evidence pack.

## Drafting And Revision

### `POST /sections/{section_id}/draft`

Generates a deterministic section draft.

Behavior:

- Requires section status `evidence_ready`.
- Requires an active contract.
- Requires an active non-empty evidence pack.
- Creates version 1 as `active`.
- Moves section to `drafted`.
- Rejects repeated initial generation once a current draft exists.

### `GET /sections/{section_id}/drafts/current`

Gets the active section draft if present.

### `POST /sections/{section_id}/revise`

Creates a revised draft version.

Behavior:

- Requires section status `reviewed` or `revision_required`.
- Requires a current draft.
- Requires unresolved review comments or active revision tasks.
- Supersedes the previous active draft.
- Creates a new active draft version.
- Optionally resolves comments.
- Marks selected active revision tasks `approved`.
- Moves section to `revised`.

### `POST /sections/{section_id}/drafts`

Manual draft CRUD creation endpoint.

### `GET /sections/{section_id}/drafts`

Lists draft versions for a section.

### `GET /drafts/{draft_id}`

Gets one draft.

### `PATCH /drafts/{draft_id}`

Updates a draft.

### `DELETE /drafts/{draft_id}`

Deletes a draft.

## Section Review And Revision Tasks

### `POST /sections/{section_id}/review`

Reviews the current active section draft.

Behavior:

- Requires section status `drafted` or `revised`.
- Requires a current active section draft.
- Rejects if the draft already has unresolved review comments.
- Persists `ReviewComment` records.
- Automatically creates one `RevisionTask` per comment.
- Moves section to `reviewed`, then to `revision_required` if comments exist.

### `POST /drafts/{draft_id}/review`

Reviews a selected active section draft.

### `POST /drafts/{draft_id}/reviews`

Manual review comment creation endpoint.

### `GET /drafts/{draft_id}/reviews`

Lists review comments for one draft.

### `GET /sections/{section_id}/reviews`

Lists review comments across section drafts.

### `GET /reviews/{review_id}`

Gets one review comment.

### `PATCH /reviews/{review_id}`

Updates a review comment.

### `POST /reviews/{review_id}/resolve`

Marks a review comment resolved.

### `DELETE /reviews/{review_id}`

Deletes a review comment.

### `POST /sections/{section_id}/revision-tasks`

Manually creates a revision task.

### `GET /sections/{section_id}/revision-tasks`

Lists section revision tasks.

### `GET /revision-tasks/{task_id}`

Gets one revision task.

### `PATCH /revision-tasks/{task_id}`

Updates a revision task.

### `DELETE /revision-tasks/{task_id}`

Deletes a revision task.

## Assembly, Global Review, And Export

### `POST /papers/{paper_id}/assemble`

Creates a versioned assembled manuscript.

Behavior:

- Requires at least one outline node.
- Requires at least one usable current active section draft.
- Traverses the outline tree in stable pre-order.
- Includes placeholder blocks and warnings for sections without current active drafts.
- Uses current active drafts by default.
- If `include_unlocked=false`, only locked sections contribute usable drafts.
- Creates a new active manuscript version and supersedes previous active versions.
- Advances the paper to `assembly_ready` through the state machine.

### `GET /papers/{paper_id}/manuscripts/current`

Gets the active manuscript version if present.

### `GET /papers/{paper_id}/manuscripts`

Lists manuscript versions.

### `GET /manuscripts/{manuscript_id}`

Gets one assembled manuscript.

### `POST /papers/{paper_id}/global-review`

Runs deterministic global review on the current assembled manuscript.

Behavior:

- Requires a current active assembled manuscript.
- Persists `ManuscriptIssue` records.
- Returns existing issues if the current manuscript was already reviewed.
- Checks missing draft placeholders, unresolved section review comments, missing
  introduction/conclusion, missing transitions, terminology drift, contribution alignment,
  abstract/conclusion alignment, and duplicate sibling ordering.
- Advances the paper to `global_review`, then `final_revision` if issues exist.

### `GET /papers/{paper_id}/manuscript-issues`

Lists manuscript issues for a paper.

### `GET /manuscripts/{manuscript_id}/issues`

Lists issues for one manuscript version.

### `POST /papers/{paper_id}/export`

Exports the current assembled manuscript.

LaTeX options:

- `template_name`: currently supports `jcst` for the built-in JCST-style template-aware renderer
- `template_content`: optional caller-provided LaTeX template skeleton; supported placeholders are
  `{{title}}`, `{{author}}`, `{{abstract}}`, `{{body}}`, `{{bibliography}}`, `{{packages}}`, and
  `{{extra_packages}}`
- `validate_compile`: when true, runs deterministic LaTeX preflight validation and blocks export
  if the generated `.tex` has unresolved placeholders, missing document environment, unbalanced
  braces, or unmatched environments

Export artifacts include metadata for template name, whether template content was supplied, whether
compile validation was requested, and the validation result when applicable.

Persists an export artifact for the current assembled manuscript.

Supported formats:

- `markdown`
- `latex`

Behavior:

- Requires a current active assembled manuscript.
- Markdown export returns assembled content.
- LaTeX export is simple and deterministic; no bibliography generation.
- Stores export content and a deterministic `data/exports/...` path reference.

### `GET /papers/{paper_id}/exports`

Lists export artifacts for a paper.

### `GET /exports/{export_id}`

Gets one export artifact.
