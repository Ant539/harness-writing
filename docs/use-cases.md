# Writing Agent Use Cases

This document records the current intended use cases for Paper Harness as it evolves from an
academic-paper prototype into a broader writing agent.

## Primary Product Direction

Paper Harness should become a general writing agent for structured long-form writing, with strong
planning, revision, verification, and state management.

The goal is closer to a "Claude Code for writing" than to a narrow manuscript template filler.

## Current Core Use Cases

### 1. Academic Paper

- journal paper
- conference paper
- survey or literature review
- paper revision from an imported LaTeX manuscript

Why it matters:

- this is the current strongest test case
- it exercises evidence grounding, section logic, and export rigor

### 2. Student Report

- undergraduate technical report
- course project report
- lab report with structured sections

Why it matters:

- it stresses audience adaptation and varying completeness of source material

### 3. Thesis / Dissertation

- thesis proposal
- chapter-level thesis drafting
- thesis revision and structure cleanup

Why it matters:

- it stresses long-horizon planning, document state, and chapter-level coordination

### 4. Proposal / Structured Technical Document

- research proposal
- engineering design proposal
- structured long-form internal technical writing

Why it matters:

- it broadens the system beyond academic manuscripts while keeping the same planning discipline

## Shared Requirements Across Use Cases

All use cases require the system to:

- understand the user's actual goal before drafting
- determine what source material already exists
- decide whether to preserve, polish, rewrite, repair, or draft
- maintain state across a multi-step workflow
- assemble prompts according to task type and workflow stage

## Implication For System Design

Use cases should shape planning and prompt assembly, not fork the entire product into unrelated
code paths. The planner should detect and encode the use case, then downstream components should
consume that structured decision.
