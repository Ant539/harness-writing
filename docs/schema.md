# Paper Harness v1 Schema

This document summarizes the persisted SQLModel schema currently implemented in `apps/api/app/models`. The schema is intentionally artifact-heavy so later model-backed behavior can replace deterministic services without changing the workflow records.

## Enums

Implemented enums live in `apps/api/app/models/enums.py`.

### PaperType

- `survey`
- `empirical`
- `conceptual`

### PaperStatus

- `idea`
- `outline_ready`
- `evidence_in_progress`
- `drafting_in_progress`
- `section_review_in_progress`
- `revision_in_progress`
- `assembly_ready`
- `global_review`
- `final_revision`
- `submission_ready`

### SectionStatus

- `planned`
- `contract_ready`
- `evidence_ready`
- `drafted`
- `reviewed`
- `revision_required`
- `revised`
- `locked`

### EvidenceSourceType

- `paper_quote`
- `paper_summary`
- `note`
- `experiment_result`
- `table`
- `figure`
- `author_claim`

### DraftKind

- `section_draft`
- `paragraph`

### ReviewCommentType

- `missing_citation`
- `logic_gap`
- `redundancy`
- `style_issue`
- `overclaim`
- `hallucination_risk`

### Severity

- `low`
- `medium`
- `high`
- `blocker`

### ArtifactStatus

- `draft`
- `active`
- `superseded`
- `approved`
- `rejected`

### ManuscriptIssueType

- `missing_section_draft`
- `unresolved_section_review`
- `terminology_drift`
- `missing_transition`
- `missing_introduction`
- `missing_conclusion`
- `section_ordering_problem`
- `style_issue`

### ExportFormat

- `markdown`
- `latex`

### DocumentType

- `academic_paper`
- `report`
- `thesis`
- `proposal`
- `technical_document`
- `unknown`

### SourceMode

- `new_paper`
- `existing_draft`
- `mixed`
- `unknown`

### DocumentMaturity

- `idea`
- `outline`
- `partial_draft`
- `full_draft`
- `revision_cycle`

### SectionAction

- `preserve`
- `polish`
- `rewrite`
- `repair`
- `draft`
- `blocked`

### PlanningMode

- `deterministic`
- `model`
- `fallback`

### WorkflowRunStatus

- `pending`
- `running`
- `completed`
- `failed`

### WorkflowStepStatus

- `pending`
- `running`
- `completed`
- `failed`
- `skipped`

### WorkflowStepKind

- `discover`
- `plan`
- `assemble_prompts`
- `generate_outline`
- `replan`
- `generate_contract`
- `section_action`

### PromptStage

- `planner`
- `writer`
- `reviewer`
- `reviser`
- `verifier`
- `editor`

## Persisted Models

### Paper

File: `apps/api/app/models/paper.py`

Represents one paper project.

Key fields:

- `id`
- `title`
- `paper_type`
- `target_language`
- `target_venue`
- `status`
- `global_style_guide`
- `created_at`
- `updated_at`

### DiscoveryRecord

File: `apps/api/app/models/planning.py`

Represents the persisted discovery snapshot that captures clarified user intent before execution.

Key fields:

- `id`
- `paper_id`
- `document_type`
- `user_goal`
- `audience`
- `success_criteria`
- `constraints`
- `available_source_materials`
- `current_document_state`
- `clarifying_questions`
- `assumptions`
- `notes`
- `status`
- `metadata_json`
- `created_at`
- `updated_at`

### PlanningRun

File: `apps/api/app/models/planning.py`

Represents one persisted planner output for the unified workflow entry phase.

Key fields:

- `id`
- `paper_id`
- `discovery_id`
- `planner_mode`
- `status`
- `task_profile_json`
- `entry_strategy_json`
- `paper_plan_json`
- `section_plans_json`
- `prompt_assembly_hints_json`
- `metadata_json`
- `created_at`
- `updated_at`

### WorkflowRun

File: `apps/api/app/models/workflow.py`

Represents one persisted orchestration attempt across discovery, planning, and early execution.

Key fields:

- `id`
- `paper_id`
- `discovery_id`
- `planning_run_id`
- `status`
- `dry_run`
- `auto_execute`
- `requested_section_limit`
- `current_step_key`
- `metadata_json`
- `created_at`
- `updated_at`

### WorkflowStepRun

File: `apps/api/app/models/workflow.py`

Represents one persisted step inside a workflow run.

Key fields:

- `id`
- `workflow_run_id`
- `paper_id`
- `discovery_id`
- `planning_run_id`
- `section_id`
- `sequence_index`
- `step_key`
- `step_type`
- `title`
- `status`
- `result_json`
- `error_message`
- `started_at`
- `completed_at`
- `created_at`
- `updated_at`

Current section-action result behavior:

- `step_type=section_action` records the planner action, section title, planner reason, evidence and
  review-loop needs, and the action outcome.
- Completed action steps may include draft IDs, previous draft IDs, evidence-pack IDs, resolved
  review comment IDs, completed revision task IDs, and fallback metadata.
- Skipped action steps include a `skip_reason`; blocked sections are represented as skipped
  section-action steps with `outcome=blocked`.

### PromptAssemblyArtifact

File: `apps/api/app/models/prompts.py`

Represents one persisted prompt assembly for a workflow stage.

Key fields:

- `id`
- `paper_id`
- `planning_run_id`
- `workflow_run_id`
- `section_id`
- `stage`
- `version`
- `module_keys`
- `modules_json`
- `system_prompt`
- `user_prompt`
- `prompt_hash`
- `prompt_pack_version`
- `status`
- `metadata_json`
- `created_at`

### PromptExecutionLog

File: `apps/api/app/models/prompts.py`

Represents an audit log for assembled prompts and model-backed prompt calls.

Key fields:

- `id`
- `paper_id`
- `planning_run_id`
- `workflow_run_id`
- `prompt_assembly_id`
- `section_id`
- `stage`
- `provider`
- `model_name`
- `status`
- `prompt_hash`
- `prompt_version`
- `prompt_pack_version`
- `module_keys`
- `request_metadata_json`
- `system_prompt`
- `user_prompt`
- `response_text`
- `error_message`
- `created_at`

### OutlineNode

File: `apps/api/app/models/outline.py`

Represents a section or subsection in the outline tree.

Key fields:

- `id`
- `paper_id`
- `parent_id`
- `title`
- `level`
- `goal`
- `expected_claims`
- `word_budget`
- `status`
- `order_index`
- `metadata_json`

### SectionContract

File: `apps/api/app/models/contract.py`

Represents writing requirements for one section.

Key fields:

- `id`
- `section_id`
- `purpose`
- `questions_to_answer`
- `required_claims`
- `required_evidence_count`
- `required_citations`
- `forbidden_patterns`
- `tone`
- `length_min`
- `length_max`
- `created_at`

### SourceMaterial

File: `apps/api/app/models/evidence.py`

Represents registered text source material.

Key fields:

- `id`
- `paper_id`
- `source_type`
- `title`
- `source_ref`
- `content`
- `citation_key`
- `metadata_json`
- `created_at`

### EvidenceItem

File: `apps/api/app/models/evidence.py`

Represents one evidence unit.

Key fields:

- `id`
- `paper_id`
- `section_id`
- `source_type`
- `source_ref`
- `content`
- `citation_key`
- `confidence`
- `metadata_json`
- `created_at`

### EvidencePack

File: `apps/api/app/models/evidence.py`

Represents evidence selected for one section.

Key fields:

- `id`
- `section_id`
- `evidence_item_ids`
- `coverage_summary`
- `open_questions`
- `status`
- `created_at`

### DraftUnit

File: `apps/api/app/models/draft.py`

Represents a section draft or future paragraph draft.

Key fields:

- `id`
- `section_id`
- `kind`
- `version`
- `content`
- `supported_evidence_ids`
- `status`
- `created_at`

Current behavior:

- Section drafting creates `kind=section_draft`.
- The active current draft has `status=active`.
- Revision supersedes the previous active version and creates a new active version.

### ReviewComment

File: `apps/api/app/models/review.py`

Represents structured section-level review feedback.

Key fields:

- `id`
- `target_draft_id`
- `comment_type`
- `severity`
- `comment`
- `suggested_action`
- `resolved`
- `created_at`

### RevisionTask

File: `apps/api/app/models/revision.py`

Represents a concrete revision action.

Key fields:

- `id`
- `section_id`
- `draft_id`
- `task_description`
- `priority`
- `status`
- `created_at`

Current behavior:

- Review automatically creates one active revision task per review comment.
- Revision marks selected active tasks as `approved`.

### StyleGuide

File: `apps/api/app/models/style.py`

Represents manuscript-wide style preferences.

Key fields:

- `id`
- `paper_id`
- `tone`
- `voice`
- `citation_style`
- `terminology_preferences`
- `forbidden_patterns`
- `format_rules`
- `created_at`

### AssembledManuscript

File: `apps/api/app/models/assembly.py`

Represents a versioned full-manuscript artifact.

Key fields:

- `id`
- `paper_id`
- `version`
- `content`
- `included_section_ids`
- `missing_section_ids`
- `warnings`
- `status`
- `created_at`

Current behavior:

- Repeated assembly creates a new version.
- Previous active manuscript versions are marked `superseded`.

### ManuscriptIssue

File: `apps/api/app/models/assembly.py`

Represents a global manuscript review issue.

Key fields:

- `id`
- `paper_id`
- `manuscript_id`
- `issue_type`
- `severity`
- `message`
- `suggested_action`
- `resolved`
- `created_at`

### ExportArtifact

File: `apps/api/app/models/assembly.py`

Represents persisted export output.

Key fields:

- `id`
- `paper_id`
- `manuscript_id`
- `version`
- `export_format`
- `content`
- `artifact_path`
- `metadata_json`
- `status`
- `created_at`

Current behavior:

- Markdown export stores assembled manuscript content.
- LaTeX export stores simple converted content.
- `artifact_path` is a deterministic reference; physical file writing is deferred.

## Key Relationships

- A `Paper` has many `OutlineNode` records.
- An `OutlineNode` can have a parent `OutlineNode`.
- An `OutlineNode` has one generated/manual `SectionContract` in the current flow.
- A `Paper` has many `SourceMaterial` and `EvidenceItem` records.
- An `OutlineNode` has many `EvidencePack` records, with one active pack used by drafting.
- An `OutlineNode` has many `DraftUnit` records.
- A `DraftUnit` has many `ReviewComment` records.
- A `ReviewComment` can lead to a `RevisionTask`.
- A `Paper` has many `AssembledManuscript` records.
- An `AssembledManuscript` has many `ManuscriptIssue` and `ExportArtifact` records.

## Traceability Notes

- Evidence IDs are stored as JSON string lists on `EvidencePack.evidence_item_ids` and `DraftUnit.supported_evidence_ids`.
- Review comments target a specific draft version.
- Revision tasks reference both section and draft.
- Manuscript assembly records the section IDs that contributed draft content and the section IDs that only contributed placeholders.
