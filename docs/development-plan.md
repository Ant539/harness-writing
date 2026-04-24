# Development Plan

This document tracks the current implementation state, the intended target state, and the major
work remaining to reach a usable end-to-end writing-agent system.

## Why This Plan Exists

Paper Harness now has enough building blocks that ad hoc iteration is no longer enough. The next
phase needs one clear development plan so workflow design, prompt work, user interaction, state
management, persistence, and export behavior all converge on the same target.

This document is about developing the system. It is separate from runtime paper execution.

## Current State

As of April 24, 2026, the repository already has:

### Implemented Runtime Capabilities

- FastAPI + SQLModel backend with persisted paper, outline, contract, evidence, draft, review,
  manuscript, and export artifacts
- persisted discovery records and planning runs for the first unified writing-agent entry phase
- persisted workflow runs and workflow-step records for orchestration
- LaTeX import that converts an existing manuscript into Paper Harness paper/outline/draft records
- deterministic outline generation
- deterministic section contract generation
- deterministic workflow planning with optional model-backed structured planner output when an LLM
  provider is configured
- a first unified workflow runner that can auto-infer discovery, generate a plan, prepare an
  outline, and prepare section contracts while recording step status
- persisted prompt-assembly artifacts that compose reusable modules from planning output, workflow
  stage, source mode, and risk emphasis
- versioned prompt packs for planner, writer, reviewer, reviser, verifier, and editor stages
- prompt hashes, prompt pack versions, persisted prompt modules, and prompt execution logs for
  assembled prompts plus model-backed planner calls
- planner-driven section action execution for preserve, polish, rewrite, repair, draft, and blocked,
  with conservative deterministic fallbacks when full automation is not yet safe
- template-aware LaTeX export for JCST-style submissions, including caller-supplied template
  content with placeholder replacement
- deterministic LaTeX compile preflight validation for exported manuscripts
- deterministic evidence extraction and evidence-pack construction
- deterministic section draft generation, review, revision, and manuscript assembly
- Markdown and simple LaTeX export
- configurable model providers:
  - OpenAI-compatible provider family
  - GLM / GLM coding-plan defaults
  - Anthropic provider
  - Gemini provider
- test coverage for the current backend and provider layer

### What Is Missing Despite Those Building Blocks

- no multi-turn discovery phase that actively talks with the user to clarify the writing objective
- no unified workflow runner that executes the whole document lifecycle automatically
- no prompt-assembly layer that composes prompts from task profile and workflow state
- prompt logging currently covers prompt assembly and model-backed planner calls; writer/reviewer
  model-call logging still needs to be wired into those lower-level generators
- no fully tuned model-backed section/unit action engine beyond the first deterministic execution
  bridge
- no robust prompt pack tuned across multiple writing domains
- no robust global editor/verifier loop
- no external LaTeX compiler integration yet; current validation is a deterministic preflight gate

## Target State

The target is not just "model calls work." The target is:

> Given a writing goal, Paper Harness can converse with the user, understand what they want,
> create a plan, assemble the right prompts, execute a stateful workflow, revise and verify the
> document, and produce a high-quality result appropriate to the use case.

## Product Scope

Academic-paper handling is a current test case, not the full product target.

The system should eventually support:

- academic papers
- student reports
- thesis and dissertation writing
- proposals
- structured technical long-form writing

The target is a Claude Code-level writing agent: serious, stateful, plan-driven, and able to
handle complex document work over multiple turns and workflow steps.

### Unified Workflow Target

There should be one workflow for all writing tasks. The workflow should begin with discovery and
planning. The planner should decide:

- what kind of document the user wants
- who the audience is
- what success looks like
- whether the current document is a new draft, an existing draft, or a mixed case
- whether each section or unit should be preserved, polished, rewritten, repaired, newly drafted,
  or blocked
- what evidence and review loops are required before assembly or export

That means the system should not maintain separate hard-coded workflows for:

- "write from scratch"
- "revise existing manuscript"
- "student report"
- "thesis chapter"

Instead, those are planning outcomes within one shared pipeline.

### Quality Target

The target system should produce:

- factually grounded document revisions
- section-by-section or unit-by-unit traceability
- conservative handling of unsupported or incomplete source material
- reproducible workflow records
- prompt assembly that reflects task type, user goal, and workflow stage
- export suitable for manual final inspection and delivery

## Major Gaps To Close

### 1. Planning Layer

Needed:

- discovery-first interaction model
- persisted planning artifact or planning run model
- explicit planner output schema
- planner prompt pack
- runtime planner service that inspects user conversation, imported manuscripts, outlines, drafts,
  and evidence
- planner-driven action selection
- current state classification for the document and workflow

Expected result:

- every workflow run starts with discovery plus a stable plan
- task type and source mode are decided in planning rather than encoded in separate workflows

### 2. Workflow Runner

Needed:

- orchestrator endpoint or script to run the workflow end to end
- step persistence and resumability
- clear step boundaries and failure status
- dry-run mode and section-limited mode for prompt tuning
- conversational checkpoint support

Expected result:

- a whole writing task can be processed without manually calling each API step

### 3. Prompt Assembly Layer

Needed:

- reusable prompt modules
- prompt assembly from task profile, source mode, workflow stage, and risk profile
- use-case framing injection
- prompt versioning and persistence

Expected result:

- the system can adapt prompts to academic papers, reports, theses, and other writing modes
- prompt tuning becomes an organized engineering activity instead of an ad hoc rewrite habit

### 4. Section / Unit Action Engine

Implemented first pass:

- runtime support for planner actions:
  - `preserve`
  - `polish`
  - `rewrite`
  - `repair`
  - `draft`
  - `blocked`
- workflow-step persistence records each section action, status, output draft IDs, and skip/fallback
  reasons
- `draft` attempts deterministic evidence-pack alignment and section drafting
- `repair` uses existing review/revision context where possible, with conservative fallback revision
- `rewrite` and `polish` produce new traceable draft versions when existing draft text is available
- `preserve` records the non-destructive decision without generating a new draft
- `blocked` records an explicit skipped step

Still needed:

- section diagnostics before generation
- tuned model-backed prompts and deeper section review/revision loops driven by planning output

Expected result:

- existing strong material is preserved
- weak but recoverable sections are repaired
- missing sections are drafted only when appropriate
- blocked sections are surfaced explicitly instead of papered over

### 5. Global Document Coherence

Needed:

- whole-document terminology consistency checks
- high-level structure alignment
- audience and goal consistency
- figure/table/citation cross-checking where relevant
- document-level revision pass after section loops

Expected result:

- the final output reads like one coherent document rather than a pile of independently revised sections

### 6. Final Export

Needed:

- use-case-sensitive export targets
- template-aware academic export where needed
- compile or render check where relevant
- final export quality gate

Expected result:

- exported output is close to a delivery candidate instead of a merely readable intermediate artifact

### 7. Agent State And Interaction

Needed:

- persistent workflow state model
- user interaction records and clarification checkpoints
- explicit state transitions for discovery, planning, execution, and review
- resumable agent runs

Expected result:

- the system behaves like a serious writing agent rather than a pile of disconnected text endpoints

## Proposed Delivery Stages

### Stage 1: Agent Foundation

- define discovery and planning schema
- add product-level prompt foundation
- add use-case framing
- persist planning and interaction records

### Stage 2: Planning And Prompt Assembly

- define planning schema
- add planning prompt
- add prompt assembly modules
- expose discovery/planning endpoints

### Stage 3: Workflow Runner

- add `run-workflow` endpoint or script
- connect planning output to prompt assembly and section actions
- add dry-run and section-limit controls
- add conversational checkpoints

### Stage 4: Section / Unit Revision Quality

- add tuned prompts for rewrite/repair/polish
- add section action execution
- add review/revision loop controls

### Stage 5: Whole-Document Quality

- add global editor/verifier passes
- add whole-paper issue summaries
- improve blocked-section handling

### Stage 6: Delivery-Oriented Export

- add JCST template-aware export
- add compile and packaging checks

## Completion Criteria

This phase should be considered complete when:

- one unified workflow exists for multiple writing use cases
- discovery and planning are first-class phases
- prompt assembly is structured and persisted
- a full workflow can run from user goal and source material to exported output with persisted run records
- prompts are versioned and tracked
- development tasks are managed outside runtime workflow state
- the exported result is suitable for serious manual review before delivery
