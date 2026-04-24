# Prompt Foundation

This file captures the product-level prompt foundation for Paper Harness.

Paper Harness is not only an academic-paper workflow. The long-term target is a writing agent with
Claude Code-level seriousness for document work: conversational, stateful, plan-driven, and able
to execute complex writing and revision workflows while staying grounded in source material.

## Product Target

The target system should:

- talk with the user to understand the writing objective before drafting
- maintain persistent workflow state
- build a plan before execution
- assemble downstream prompts from plan outputs
- write, revise, verify, and export long-form documents
- support multiple writing domains rather than a single fixed genre

## Current Core Use Cases

- academic paper drafting and revision
- student scientific or technical reports
- thesis and dissertation writing
- long-form structured technical writing
- literature reviews and proposal-style documents

## Agent Behavior Principles

1. Discovery first: understand goal, audience, constraints, and success criteria.
2. Planning first: decide source mode, document maturity, and unit actions before drafting.
3. Grounded generation: use supplied material, do not invent support.
4. Stateful execution: preserve workflow state, history, and intermediate artifacts.
5. Modular prompting: prompt assembly should be composed from reusable modules rather than one giant prompt.
6. Separation of concerns: system-development instructions and runtime document instructions are not the same thing.

## Prompt Assembly Modules

Every full run should be able to assemble prompts from modules such as:

- product mission
- use-case framing
- task profile
- source mode
- stage instructions
- style guidance
- safety and non-invention rules
- output schema
- verification emphasis

## Development Reminder

Prompt tuning is a persistent engineering process. The goal of this file is not to finalize every
prompt, but to provide a stable foundation so later planner, writer, reviewer, verifier, and
editor prompts all inherit the same product direction.
