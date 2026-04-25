# Evaluation Configs

This directory contains rubric configuration for prompt and writing-quality evaluation.

## Academic Paper v1

`academic-paper-v1.json` is the first narrow evaluation target. It scores academic paper drafts
generated from supplied method and result inputs. The standard is intentionally high: the draft
should move toward a top-tier journal or conference submission, not merely produce fluent prose.

Recommended case shape:

```json
{
  "title": "Paper title or working title",
  "field": "Computer science",
  "target_venue": "Top-tier systems journal",
  "audience": "Researchers in distributed systems",
  "method_summary": "What was done, measured, built, or analyzed.",
  "result_summary": "The main findings, numbers, comparisons, and observed effects.",
  "expected_contributions": ["Specific contribution the paper should claim"],
  "required_facts": ["Facts the generated paper must preserve"],
  "forbidden_claims": ["Claims the generated paper must not make"],
  "constraints": ["Additional style, scope, or format constraints"]
}
```

Run the deterministic evaluator with:

```bash
python scripts/evaluate_academic_paper.py --case path/to/case.json --paper path/to/paper.md
```
