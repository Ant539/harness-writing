# Prompt Templates

These prompt files are the prompt-assembly foundations for Paper Harness.

Current use:

- `foundation.md` provides the product-level mission
- `planner.md` defines structured planner behavior
- `writer.md`, `reviewer.md`, `reviser.md`, `verifier.md`, and `editor.md` provide stage-level
  instructions used by the prompt assembly service
- `evaluator.md` defines the academic-writing judge role used for prompt development and future
  model-backed evaluation

The runtime prompt assembly layer composes these files with persisted planning outputs such as task
profile, source mode, style guidance, and risk emphasis.

Prompt packs:

- `configs/prompt-packs/v1.json` defines versioned role packs for planner, writer, reviewer,
  reviser, verifier, and editor stages
- prompt assembly injects the current stage pack as the `stage_prompt_pack` module
- assembled prompt artifacts persist module contents, prompt hash, prompt pack version, and a prompt
  execution log entry
