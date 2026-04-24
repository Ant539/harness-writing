# Paper Harness v1 Implementation Brief

This brief translates the Paper Harness v1 design spec into a Codex-ready build plan. It defines the repository layout, module responsibilities, typed backend schemas, API contracts, frontend pages, state machine rules, and milestone order for implementation.

## 1. Product Scope

Paper Harness v1 is a local-first academic paper production system. It helps a user move from a research topic or paper title to an assembled manuscript through a controlled, evidence-first workflow.

The system must support:

- Creating a paper project.
- Generating and editing a hierarchical outline.
- Generating section-level writing contracts.
- Uploading or entering evidence.
- Building section-specific evidence packs.
- Drafting sections from contracts and evidence packs.
- Reviewing and revising drafts.
- Locking approved sections.
- Assembling locked sections into a manuscript.
- Exporting at least Markdown.

The system must not rely on unconstrained full-paper generation. All meaningful writing work happens section by section, with explicit artifacts persisted at each stage.

## 2. Repository Layout

```text
paper-harness/
|-- apps/
|   |-- api/
|   |   |-- app/
|   |   |   |-- main.py
|   |   |   |-- api/
|   |   |   |   |-- deps.py
|   |   |   |   `-- routes/
|   |   |   |       |-- papers.py
|   |   |   |       |-- sections.py
|   |   |   |       |-- evidence.py
|   |   |   |       |-- drafts.py
|   |   |   |       |-- reviews.py
|   |   |   |       `-- assembly.py
|   |   |   |-- db/
|   |   |   |   |-- base.py
|   |   |   |   |-- session.py
|   |   |   |   `-- models.py
|   |   |   |-- services/
|   |   |   |   |-- papers.py
|   |   |   |   |-- outlines.py
|   |   |   |   |-- contracts.py
|   |   |   |   |-- evidence.py
|   |   |   |   |-- drafting.py
|   |   |   |   |-- review.py
|   |   |   |   |-- verification.py
|   |   |   |   `-- assembly.py
|   |   |   |-- agents/
|   |   |   |   |-- base.py
|   |   |   |   |-- mock_llm.py
|   |   |   |   |-- planner.py
|   |   |   |   |-- researcher.py
|   |   |   |   |-- writer.py
|   |   |   |   |-- reviewer.py
|   |   |   |   |-- verifier.py
|   |   |   |   `-- editor.py
|   |   |   `-- settings.py
|   |   |-- tests/
|   |   |   |-- test_state_machine.py
|   |   |   |-- test_papers_api.py
|   |   |   |-- test_outline_api.py
|   |   |   |-- test_evidence_api.py
|   |   |   |-- test_drafting_api.py
|   |   |   `-- test_assembly_api.py
|   |   |-- pyproject.toml
|   |   `-- README.md
|   |-- web/
|   |   |-- app/
|   |   |   |-- layout.tsx
|   |   |   |-- page.tsx
|   |   |   |-- papers/
|   |   |   |   |-- page.tsx
|   |   |   |   |-- new/page.tsx
|   |   |   |   `-- [paperId]/
|   |   |   |       |-- page.tsx
|   |   |   |       |-- outline/page.tsx
|   |   |   |       |-- sections/[sectionId]/page.tsx
|   |   |   |       `-- review/page.tsx
|   |   |   `-- globals.css
|   |   |-- components/
|   |   |   |-- paper-dashboard.tsx
|   |   |   |-- outline-tree.tsx
|   |   |   |-- section-status-badge.tsx
|   |   |   |-- evidence-panel.tsx
|   |   |   |-- draft-viewer.tsx
|   |   |   |-- review-list.tsx
|   |   |   `-- revision-task-list.tsx
|   |   |-- lib/
|   |   |   |-- api.ts
|   |   |   `-- types.ts
|   |   |-- package.json
|   |   `-- README.md
|   `-- worker/
|       |-- worker.py
|       |-- queue.py
|       `-- README.md
|-- packages/
|   |-- core/
|   |   |-- paper_harness_core/
|   |   |   |-- enums.py
|   |   |   |-- schemas.py
|   |   |   |-- state_machine.py
|   |   |   `-- errors.py
|   |   |-- tests/
|   |   `-- pyproject.toml
|   |-- planner/
|   |-- research/
|   |-- drafting/
|   |-- review/
|   |-- verify/
|   |-- editor/
|   |-- memory/
|   `-- export/
|-- data/
|   |-- papers/
|   |-- evidence/
|   |-- drafts/
|   |-- reviews/
|   `-- exports/
|-- configs/
|   |-- prompts/
|   |   |-- planner.md
|   |   |-- researcher.md
|   |   |-- writer.md
|   |   |-- reviewer.md
|   |   |-- verifier.md
|   |   `-- editor.md
|   |-- styles/
|   |   `-- default-academic.json
|   `-- workflows/
|       `-- v1.json
|-- docs/
|   |-- architecture.md
|   |-- workflow.md
|   |-- schema.md
|   |-- api-spec.md
|   `-- implementation-brief.md
|-- README.md
`-- pyproject.toml
```

## 3. File-by-File Responsibilities

### Root

- `README.md`: project overview, local setup, basic development commands, and current milestone status.
- `pyproject.toml`: optional root tooling config for Ruff, pytest, and workspace conventions.
- `docs/implementation-brief.md`: this build plan.
- `docs/architecture.md`: architecture narrative organized by the six layers.
- `docs/workflow.md`: lifecycle states, transitions, and user approval checkpoints.
- `docs/schema.md`: canonical object model and relationship notes.
- `docs/api-spec.md`: route-level request and response contracts.

### `packages/core`

- `enums.py`: shared enum definitions for paper types, statuses, source types, comment types, priorities, and artifact kinds.
- `schemas.py`: Pydantic schemas shared by API services and tests.
- `state_machine.py`: explicit transition maps and transition validation helpers.
- `errors.py`: domain errors such as `InvalidStateTransition`, `MissingContract`, and `MissingEvidencePack`.

### `apps/api`

- `main.py`: FastAPI application factory, router registration, health endpoint, and CORS setup for the local frontend.
- `settings.py`: app settings including database URL, data directory, mock LLM mode, and export directory.
- `db/session.py`: SQLAlchemy engine and session dependency.
- `db/models.py`: SQLAlchemy ORM models for all persisted objects.
- `api/deps.py`: shared dependencies for database sessions and service construction.
- `api/routes/*.py`: thin route handlers. They validate inputs, call services, and return typed schemas.
- `services/*.py`: domain behavior. Services enforce state rules, create artifacts, call agent adapters, and persist version history.
- `agents/base.py`: common interface for role-specific agents.
- `agents/mock_llm.py`: deterministic mock LLM adapter for early implementation and tests.
- `agents/*.py`: role wrappers for Planner, Researcher, Writer, Reviewer, Verifier, and Editor.
- `tests/*.py`: state, API, and artifact persistence tests.

### `apps/web`

- `app/page.tsx`: redirect or entry point to the paper list.
- `app/papers/page.tsx`: paper list and high-level progress overview.
- `app/papers/new/page.tsx`: create-paper form.
- `app/papers/[paperId]/page.tsx`: paper dashboard.
- `app/papers/[paperId]/outline/page.tsx`: outline workspace.
- `app/papers/[paperId]/sections/[sectionId]/page.tsx`: section workspace.
- `app/papers/[paperId]/review/page.tsx`: global review workspace.
- `components/outline-tree.tsx`: hierarchical section navigation and status display.
- `components/evidence-panel.tsx`: evidence pack and evidence item viewer.
- `components/draft-viewer.tsx`: current draft, paragraph evidence links, and versions.
- `components/review-list.tsx`: review comments with resolve actions.
- `components/revision-task-list.tsx`: revision task status controls.
- `lib/api.ts`: typed API client.
- `lib/types.ts`: frontend TypeScript types matching backend schemas.

### `apps/worker`

- `queue.py`: simple in-process or SQLite-backed job queue abstraction.
- `worker.py`: background runner for long agent tasks.

For v1, API routes may execute mock agent calls synchronously. The worker can be introduced once the basic domain flow is stable.

## 4. Core Domain Enums

```python
from enum import StrEnum


class PaperType(StrEnum):
    SURVEY = "survey"
    EMPIRICAL = "empirical"
    CONCEPTUAL = "conceptual"


class PaperStatus(StrEnum):
    IDEA = "idea"
    OUTLINE_READY = "outline_ready"
    EVIDENCE_IN_PROGRESS = "evidence_in_progress"
    DRAFTING_IN_PROGRESS = "drafting_in_progress"
    SECTION_REVIEW_IN_PROGRESS = "section_review_in_progress"
    REVISION_IN_PROGRESS = "revision_in_progress"
    ASSEMBLY_READY = "assembly_ready"
    GLOBAL_REVIEW = "global_review"
    FINAL_REVISION = "final_revision"
    SUBMISSION_READY = "submission_ready"


class SectionStatus(StrEnum):
    PLANNED = "planned"
    CONTRACT_READY = "contract_ready"
    EVIDENCE_READY = "evidence_ready"
    DRAFTED = "drafted"
    REVIEWED = "reviewed"
    REVISION_REQUIRED = "revision_required"
    REVISED = "revised"
    LOCKED = "locked"


class EvidenceSourceType(StrEnum):
    PAPER_QUOTE = "paper_quote"
    PAPER_SUMMARY = "paper_summary"
    NOTE = "note"
    EXPERIMENT_RESULT = "experiment_result"
    TABLE = "table"
    FIGURE = "figure"
    AUTHOR_CLAIM = "author_claim"


class DraftKind(StrEnum):
    SECTION_DRAFT = "section_draft"
    PARAGRAPH = "paragraph"


class ReviewCommentType(StrEnum):
    MISSING_CITATION = "missing_citation"
    LOGIC_GAP = "logic_gap"
    REDUNDANCY = "redundancy"
    STYLE_ISSUE = "style_issue"
    OVERCLAIM = "overclaim"
    HALLUCINATION_RISK = "hallucination_risk"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKER = "blocker"


class ArtifactStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    APPROVED = "approved"
    REJECTED = "rejected"
```

## 5. Backend Schema Definitions

The backend should use SQLAlchemy models for persistence and Pydantic models for request and response validation. The following are implementation targets, not exact final code.

### Paper

```python
class PaperBase(BaseModel):
    title: str
    paper_type: PaperType
    target_language: str = "English"
    target_venue: str | None = None
    global_style_guide: dict[str, Any] = Field(default_factory=dict)


class PaperCreate(PaperBase):
    user_goals: str | None = None


class PaperRead(PaperBase):
    id: UUID
    status: PaperStatus
    created_at: datetime
    updated_at: datetime
```

### OutlineNode

```python
class OutlineNodeBase(BaseModel):
    parent_id: UUID | None = None
    title: str
    level: int
    goal: str | None = None
    expected_claims: list[str] = Field(default_factory=list)
    word_budget: int | None = None
    order_index: int


class OutlineNodeCreate(OutlineNodeBase):
    paper_id: UUID


class OutlineNodeUpdate(BaseModel):
    title: str | None = None
    parent_id: UUID | None = None
    goal: str | None = None
    expected_claims: list[str] | None = None
    word_budget: int | None = None
    order_index: int | None = None
    status: SectionStatus | None = None


class OutlineNodeRead(OutlineNodeBase):
    id: UUID
    paper_id: UUID
    status: SectionStatus
```

### SectionContract

```python
class SectionContractBase(BaseModel):
    purpose: str
    questions_to_answer: list[str]
    required_claims: list[str]
    required_evidence_count: int = 1
    required_citations: list[str] = Field(default_factory=list)
    forbidden_patterns: list[str] = Field(default_factory=list)
    tone: str | None = None
    length_min: int | None = None
    length_max: int | None = None


class SectionContractCreate(SectionContractBase):
    section_id: UUID


class SectionContractRead(SectionContractBase):
    id: UUID
    section_id: UUID
    created_at: datetime
```

### EvidenceItem

```python
class EvidenceItemBase(BaseModel):
    section_id: UUID | None = None
    source_type: EvidenceSourceType
    source_ref: str | None = None
    content: str
    citation_key: str | None = None
    confidence: float = Field(ge=0, le=1, default=0.75)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceItemCreate(EvidenceItemBase):
    paper_id: UUID


class EvidenceItemRead(EvidenceItemBase):
    id: UUID
    paper_id: UUID
    created_at: datetime
```

### EvidencePack

```python
class EvidencePackBase(BaseModel):
    evidence_item_ids: list[UUID]
    coverage_summary: str
    open_questions: list[str] = Field(default_factory=list)
    status: ArtifactStatus = ArtifactStatus.ACTIVE


class EvidencePackCreate(EvidencePackBase):
    section_id: UUID


class EvidencePackRead(EvidencePackBase):
    id: UUID
    section_id: UUID
    created_at: datetime
```

### DraftUnit

```python
class DraftUnitBase(BaseModel):
    kind: DraftKind
    version: int
    content: str
    supported_evidence_ids: list[UUID] = Field(default_factory=list)
    status: ArtifactStatus = ArtifactStatus.DRAFT


class DraftUnitCreate(DraftUnitBase):
    section_id: UUID


class DraftUnitRead(DraftUnitBase):
    id: UUID
    section_id: UUID
    created_at: datetime
```

### ReviewComment

```python
class ReviewCommentBase(BaseModel):
    comment_type: ReviewCommentType
    severity: Severity
    comment: str
    suggested_action: str
    resolved: bool = False


class ReviewCommentCreate(ReviewCommentBase):
    target_draft_id: UUID


class ReviewCommentRead(ReviewCommentBase):
    id: UUID
    target_draft_id: UUID
    created_at: datetime
```

### RevisionTask

```python
class RevisionTaskBase(BaseModel):
    task_description: str
    priority: Severity
    status: ArtifactStatus = ArtifactStatus.ACTIVE


class RevisionTaskCreate(RevisionTaskBase):
    section_id: UUID
    draft_id: UUID


class RevisionTaskRead(RevisionTaskBase):
    id: UUID
    section_id: UUID
    draft_id: UUID
    created_at: datetime
```

### StyleGuide

```python
class StyleGuideBase(BaseModel):
    tone: str | None = None
    voice: str | None = None
    citation_style: str | None = None
    terminology_preferences: dict[str, str] = Field(default_factory=dict)
    forbidden_patterns: list[str] = Field(default_factory=list)
    format_rules: dict[str, Any] = Field(default_factory=dict)


class StyleGuideCreate(StyleGuideBase):
    paper_id: UUID


class StyleGuideRead(StyleGuideBase):
    id: UUID
    paper_id: UUID
```

## 6. State Machine Rules

State transitions must be explicit and testable. Service methods should call transition helpers instead of assigning statuses directly.

### Paper Transitions

```python
PAPER_TRANSITIONS = {
    "idea": {"outline_ready"},
    "outline_ready": {"evidence_in_progress"},
    "evidence_in_progress": {"drafting_in_progress"},
    "drafting_in_progress": {"section_review_in_progress"},
    "section_review_in_progress": {"revision_in_progress", "assembly_ready"},
    "revision_in_progress": {"drafting_in_progress", "section_review_in_progress"},
    "assembly_ready": {"global_review"},
    "global_review": {"final_revision", "submission_ready"},
    "final_revision": {"global_review", "submission_ready"},
    "submission_ready": set(),
}
```

### Section Transitions

```python
SECTION_TRANSITIONS = {
    "planned": {"contract_ready"},
    "contract_ready": {"evidence_ready"},
    "evidence_ready": {"drafted"},
    "drafted": {"reviewed"},
    "reviewed": {"revision_required", "locked"},
    "revision_required": {"revised"},
    "revised": {"reviewed", "locked"},
    "locked": set(),
}
```

### Transition Guards

- `planned -> contract_ready`: requires one `SectionContract`.
- `contract_ready -> evidence_ready`: requires one active `EvidencePack` with at least one evidence item.
- `evidence_ready -> drafted`: requires an active contract and active evidence pack.
- `drafted -> reviewed`: requires at least one section draft.
- `reviewed -> locked`: requires no unresolved high or blocker review comments.
- `reviewed -> revision_required`: requires unresolved review comments or verifier warnings.
- `revision_required -> revised`: requires a new draft version or explicit task resolution.
- `locked` sections are immutable except through an explicit unlock operation, which can be added after v1.

## 7. API Contracts

All endpoints return JSON. Errors should use a consistent shape:

```json
{
  "error": {
    "code": "invalid_state_transition",
    "message": "Section must have an active evidence pack before drafting.",
    "details": {}
  }
}
```

### Paper APIs

#### `POST /papers`

Request:

```json
{
  "title": "Evidence-First LLM Workflows for Academic Writing",
  "paper_type": "conceptual",
  "target_language": "English",
  "target_venue": "CHI-style workshop",
  "user_goals": "Argue for controlled section-level paper generation."
}
```

Response: `PaperRead`.

#### `GET /papers`

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "title": "Evidence-First LLM Workflows for Academic Writing",
      "paper_type": "conceptual",
      "target_language": "English",
      "target_venue": "CHI-style workshop",
      "status": "idea",
      "created_at": "iso-datetime",
      "updated_at": "iso-datetime"
    }
  ]
}
```

#### `GET /papers/{paper_id}`

Response: `PaperRead`.

#### `GET /papers/{paper_id}/outline`

Response:

```json
{
  "paper_id": "uuid",
  "nodes": [
    {
      "id": "uuid",
      "paper_id": "uuid",
      "parent_id": null,
      "title": "Introduction",
      "level": 1,
      "goal": "Frame the paper problem and contribution.",
      "expected_claims": ["Current LLM writing workflows are under-controlled."],
      "word_budget": 900,
      "status": "planned",
      "order_index": 1
    }
  ]
}
```

### Outline APIs

#### `POST /papers/{paper_id}/generate-outline`

Request:

```json
{
  "additional_context": "Prefer a 6-section conceptual paper with strong design implications.",
  "target_word_count": 8000
}
```

Response:

```json
{
  "paper": "PaperRead",
  "outline": ["OutlineNodeRead"]
}
```

Behavior:

- Calls the Planner agent.
- Persists outline nodes.
- Moves paper from `idea` to `outline_ready`.

#### `POST /sections/{section_id}/generate-contract`

Request:

```json
{
  "additional_constraints": "Keep the section focused on workflow design, not model evaluation."
}
```

Response: `SectionContractRead`.

Behavior:

- Calls the Planner agent.
- Persists the contract.
- Moves section from `planned` to `contract_ready`.

#### `PATCH /sections/{section_id}`

Request: `OutlineNodeUpdate`.

Response: `OutlineNodeRead`.

Behavior:

- Supports manual outline edits.
- Status changes must pass transition validation.

### Evidence APIs

#### `POST /papers/{paper_id}/evidence/upload`

Request:

```json
{
  "items": [
    {
      "section_id": "uuid-or-null",
      "source_type": "paper_summary",
      "source_ref": "smith2024",
      "content": "Smith argues that LLM-assisted writing benefits from explicit decomposition.",
      "citation_key": "smith2024",
      "confidence": 0.85,
      "metadata": {
        "page": 12
      }
    }
  ]
}
```

Response:

```json
{
  "items": ["EvidenceItemRead"]
}
```

#### `POST /sections/{section_id}/build-evidence-pack`

Request:

```json
{
  "candidate_evidence_item_ids": ["uuid"],
  "notes": "Prioritize evidence about decomposition and review loops."
}
```

Response: `EvidencePackRead`.

Behavior:

- Requires section status `contract_ready`.
- Calls Researcher agent or deterministic mock selection.
- Persists pack and moves section to `evidence_ready`.

#### `GET /sections/{section_id}/evidence-pack`

Response:

```json
{
  "pack": "EvidencePackRead",
  "items": ["EvidenceItemRead"]
}
```

### Drafting APIs

#### `POST /sections/{section_id}/draft`

Request:

```json
{
  "instructions": "Draft in a concise academic style.",
  "neighbor_context": "Previous section defines the design problem."
}
```

Response:

```json
{
  "draft": "DraftUnitRead",
  "paragraphs": ["DraftUnitRead"],
  "unsupported_claims": []
}
```

Behavior:

- Requires status `evidence_ready`.
- Requires active contract and active evidence pack.
- Calls Writer agent.
- Persists section draft and paragraph draft units.
- Moves section to `drafted`.

#### `POST /sections/{section_id}/revise`

Request:

```json
{
  "instructions": "Address all high-priority comments and preserve citations.",
  "review_comment_ids": ["uuid"]
}
```

Response:

```json
{
  "draft": "DraftUnitRead",
  "resolved_review_ids": ["uuid"]
}
```

Behavior:

- Requires status `revision_required`.
- Calls Writer agent with review comments and previous draft.
- Creates a new draft version.
- Moves section to `revised`.

#### `GET /sections/{section_id}/drafts`

Response:

```json
{
  "items": ["DraftUnitRead"]
}
```

### Review APIs

#### `POST /sections/{section_id}/review`

Request:

```json
{
  "draft_id": "uuid",
  "include_verification": true
}
```

Response:

```json
{
  "comments": ["ReviewCommentRead"],
  "revision_tasks": ["RevisionTaskRead"],
  "section_status": "reviewed"
}
```

Behavior:

- Requires section status `drafted` or `revised`.
- Calls Reviewer agent.
- Optionally calls Verifier agent.
- Persists comments and revision tasks.
- Moves section to `reviewed` if no required revision is detected, otherwise `revision_required`.

#### `GET /sections/{section_id}/reviews`

Response:

```json
{
  "items": ["ReviewCommentRead"]
}
```

#### `POST /reviews/{review_id}/resolve`

Request:

```json
{
  "resolution_note": "Addressed by narrowing the claim and adding citation smith2024."
}
```

Response: `ReviewCommentRead`.

### Assembly APIs

#### `POST /sections/{section_id}/lock`

Request:

```json
{
  "draft_id": "uuid"
}
```

Response:

```json
{
  "section": "OutlineNodeRead"
}
```

Behavior:

- Requires status `reviewed` or `revised`.
- Requires no unresolved high or blocker comments.
- Moves section to `locked`.

#### `POST /papers/{paper_id}/assemble`

Request:

```json
{
  "include_unlocked": false
}
```

Response:

```json
{
  "manuscript_markdown": "# Title\n\n...",
  "included_section_ids": ["uuid"],
  "omitted_section_ids": []
}
```

Behavior:

- Default requires all included sections to be locked.
- Persists assembled manuscript artifact under `data/exports/`.
- Moves paper to `assembly_ready` when enough sections are locked for assembly.

#### `POST /papers/{paper_id}/global-review`

Request:

```json
{
  "manuscript_artifact_id": "uuid"
}
```

Response:

```json
{
  "comments": ["ReviewCommentRead"],
  "terminology_flags": [],
  "unresolved_global_issues": []
}
```

#### `POST /papers/{paper_id}/export`

Request:

```json
{
  "format": "markdown"
}
```

Response:

```json
{
  "format": "markdown",
  "path": "data/exports/{paper_id}/manuscript.md"
}
```

## 8. Agent Interfaces

All agent roles should expose deterministic method signatures. In v1, implementations can use `MockLLMAdapter` so tests and development do not depend on external model calls.

```python
class PlannerAgent:
    def generate_outline(self, request: OutlineGenerationRequest) -> OutlineGenerationResult: ...
    def generate_contract(self, request: ContractGenerationRequest) -> SectionContractCreate: ...


class ResearcherAgent:
    def build_evidence_pack(self, request: EvidencePackBuildRequest) -> EvidencePackCreate: ...


class WriterAgent:
    def draft_section(self, request: DraftSectionRequest) -> DraftSectionResult: ...
    def revise_section(self, request: ReviseSectionRequest) -> DraftSectionResult: ...


class ReviewerAgent:
    def review_section(self, request: ReviewSectionRequest) -> ReviewSectionResult: ...


class VerifierAgent:
    def verify_draft(self, request: VerifyDraftRequest) -> VerificationResult: ...


class EditorAgent:
    def global_review(self, request: GlobalReviewRequest) -> GlobalReviewResult: ...
    def edit_manuscript(self, request: EditManuscriptRequest) -> EditManuscriptResult: ...
```

Mock outputs should be realistic enough to exercise the workflow:

- Planner returns a conventional academic outline.
- Researcher selects evidence items matching section title, goal, or required claims.
- Writer creates paragraphs with explicit `supported_evidence_ids`.
- Reviewer produces at least one structured comment for missing support or style issues when appropriate.
- Verifier flags sentences with citation-like claims but no evidence mapping.
- Editor reports terminology inconsistencies and global repetition.

## 9. Prompt Template Files

Prompt templates live in `configs/prompts/`. They should be plain Markdown with explicit input and output contracts.

Each prompt should include:

- Role.
- Objective.
- Inputs.
- Hard constraints.
- Required JSON output schema.
- Failure mode: return missing-input questions instead of inventing facts.

Example writer constraints:

```text
You must only use citations present in the evidence pack.
Every paragraph must include supported_evidence_ids.
Unsupported inference or transition text must be marked as author_inference.
Do not draft the full paper.
Do not introduce new source claims.
```

## 10. Frontend Page List

### Paper List

Route: `/papers`

Purpose:

- Show all paper projects.
- Provide create-paper action.
- Display status, type, target venue, updated time, and progress counts.

Primary API calls:

- `GET /papers`

### New Paper

Route: `/papers/new`

Purpose:

- Collect title or topic, paper type, target language, venue/style, and user goals.
- Create a paper project.

Primary API calls:

- `POST /papers`

### Paper Dashboard

Route: `/papers/[paperId]`

Purpose:

- Show paper metadata and lifecycle status.
- Show progress summary: sections planned, contract-ready, evidence-ready, drafted, reviewed, locked.
- Provide navigation into outline, section workspace, and global review.

Primary API calls:

- `GET /papers/{paper_id}`
- `GET /papers/{paper_id}/outline`

### Outline Workspace

Route: `/papers/[paperId]/outline`

Purpose:

- Show hierarchical outline tree.
- Generate outline.
- Generate contracts section by section.
- Edit section metadata.

Primary API calls:

- `GET /papers/{paper_id}/outline`
- `POST /papers/{paper_id}/generate-outline`
- `POST /sections/{section_id}/generate-contract`
- `PATCH /sections/{section_id}`

### Section Workspace

Route: `/papers/[paperId]/sections/[sectionId]`

Purpose:

- Show section contract.
- Show evidence pack and evidence items.
- Upload or assign evidence.
- Draft section.
- Review section.
- Revise section.
- Resolve comments.
- Lock section.

Primary API calls:

- `GET /sections/{section_id}`
- `GET /sections/{section_id}/evidence-pack`
- `POST /sections/{section_id}/build-evidence-pack`
- `POST /sections/{section_id}/draft`
- `GET /sections/{section_id}/drafts`
- `POST /sections/{section_id}/review`
- `GET /sections/{section_id}/reviews`
- `POST /sections/{section_id}/revise`
- `POST /reviews/{review_id}/resolve`
- `POST /sections/{section_id}/lock`

### Global Review Workspace

Route: `/papers/[paperId]/review`

Purpose:

- Assemble locked sections.
- Preview full manuscript.
- Run global review.
- Show terminology flags and unresolved global issues.
- Export Markdown.

Primary API calls:

- `POST /papers/{paper_id}/assemble`
- `POST /papers/{paper_id}/global-review`
- `POST /papers/{paper_id}/export`

## 11. Milestone Coding Plan

### Milestone 1: Core Data Model and Backend Skeleton

Deliverables:

- Create repository structure.
- Add `packages/core` enums, schemas, errors, and state machine helpers.
- Add FastAPI app skeleton.
- Add SQLite database setup.
- Add SQLAlchemy models.
- Add create/list/get paper APIs.
- Add tests for state machine transition validation.

Acceptance checks:

- `pytest` passes.
- `POST /papers` creates a paper with status `idea`.
- Invalid state transitions raise a domain error.

### Milestone 2: Outline and Contract Generation

Deliverables:

- Add Planner agent interface and mock implementation.
- Add outline generation endpoint.
- Add section contract generation endpoint.
- Add manual section patch endpoint.
- Persist outline nodes and contracts.

Acceptance checks:

- A paper can move from `idea` to `outline_ready`.
- Generated outline nodes start as `planned`.
- Generating a contract moves a section to `contract_ready`.
- A section cannot skip from `planned` to `evidence_ready`.

### Milestone 3: Evidence Pipeline

Deliverables:

- Add evidence upload endpoint.
- Add Researcher agent interface and mock pack builder.
- Add build evidence pack endpoint.
- Add get evidence pack endpoint.
- Enforce evidence guards.

Acceptance checks:

- Evidence items persist with provenance and confidence.
- A section cannot draft without evidence.
- Building a valid evidence pack moves section to `evidence_ready`.

### Milestone 4: Drafting and Review Loop

Deliverables:

- Add Writer, Reviewer, and Verifier agent interfaces.
- Add draft endpoint.
- Add review endpoint.
- Add revise endpoint.
- Add resolve-review endpoint.
- Add revision tasks.
- Track draft versions.

Acceptance checks:

- Drafts include `supported_evidence_ids`.
- A section can move `evidence_ready -> drafted -> reviewed`.
- Review comments create revision tasks.
- Revision creates a new draft version.

### Milestone 5: Assembly and Export

Deliverables:

- Add section lock endpoint.
- Add manuscript assembly endpoint.
- Add global review endpoint.
- Add Markdown export endpoint.
- Persist export artifacts.

Acceptance checks:

- Sections with unresolved high or blocker comments cannot be locked.
- Locked sections assemble in outline order.
- Markdown export writes a file under `data/exports/{paper_id}/`.

### Milestone 6: Minimal Frontend Console

Deliverables:

- Add Next.js app skeleton.
- Add typed API client.
- Build paper list and new paper page.
- Build paper dashboard.
- Build outline workspace.
- Build section workspace.
- Build global review workspace.

Acceptance checks:

- User can create a paper from the UI.
- User can generate an outline and section contract from the UI.
- User can upload evidence, build a pack, draft, review, revise, and lock a section.
- User can assemble and export Markdown.

### Milestone 7: Codex-Oriented Hardening

Deliverables:

- Expand docs.
- Add module-level TODO files where helpful.
- Add prompt templates.
- Add richer mock fixtures.
- Add one end-to-end workflow test.

Acceptance checks:

- A fresh Codex session can use the docs and tests to continue implementation.
- The end-to-end test covers paper creation through Markdown export.

## 12. Testing Strategy

Use focused tests at three levels:

- Unit tests for state transitions and domain guards.
- Service tests for artifact persistence and versioning.
- API tests for the main workflow.

Minimum test cases:

- Create paper.
- Generate outline.
- Generate contract.
- Reject evidence pack before contract.
- Upload evidence.
- Build evidence pack.
- Reject draft before evidence pack.
- Draft section.
- Review section.
- Revise section after comments.
- Reject lock with unresolved high/blocker comments.
- Lock clean section.
- Assemble locked sections.
- Export Markdown.

## 13. Implementation Defaults

- Backend: FastAPI, SQLAlchemy 2.x, Pydantic v2, SQLite.
- Frontend: Next.js App Router, TypeScript, CSS modules or a small global stylesheet.
- LLM behavior: mock adapters first.
- IDs: UUID.
- Time fields: UTC-aware datetimes.
- Internal text format: Markdown strings plus JSON evidence mappings.
- Export format for v1: Markdown.
- Citation source: `EvidenceItem.citation_key` only.

## 14. First Codex Build Prompt

Use this prompt to begin implementation:

```text
Implement Milestone 1 of Paper Harness v1 using docs/implementation-brief.md as the source of truth.

Create the monorepo skeleton, shared core package, FastAPI backend skeleton, SQLite SQLAlchemy models, paper CRUD routes, and state machine tests.

Constraints:
- Use explicit typed schemas.
- Keep agent logic stubbed for now.
- Do not implement the frontend yet.
- Use mockable service boundaries.
- Persist paper records in SQLite.
- Add tests for valid and invalid paper/section state transitions.
- Keep changes scoped to Milestone 1.
```

## 15. Definition of Done for v1

Paper Harness v1 is complete when:

- A user can create a paper project.
- The system can generate an outline and section contracts.
- The user can upload source material and build evidence packs.
- The system can draft one section from a section contract and evidence pack.
- The system can review and revise that section.
- The system can assemble multiple approved sections into one manuscript.
- The system can export the manuscript in Markdown.
- All major lifecycle states are persisted and visible in the UI.
