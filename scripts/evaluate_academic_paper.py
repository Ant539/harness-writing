#!/usr/bin/env python
"""Evaluate a generated academic paper draft against a case JSON file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.evaluation import AcademicEvalCase, AcademicPaperEvaluator  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, help="Path to academic evaluation case JSON.")
    parser.add_argument("--paper", required=True, help="Path to generated manuscript text/Markdown.")
    parser.add_argument("--out", help="Optional path to write the scorecard JSON.")
    parser.add_argument("--pretty", action="store_true", help="Print human-readable summary too.")
    args = parser.parse_args()

    case = AcademicEvalCase.from_json_file(args.case)
    paper_text = Path(args.paper).read_text(encoding="utf-8")
    evaluation = AcademicPaperEvaluator().evaluate(case, paper_text)
    payload = evaluation.as_dict()

    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(serialized + "\n", encoding="utf-8")

    if args.pretty:
        print(f"Overall: {payload['overall_score']} / 100")
        print(f"Readiness: {payload['readiness']}")
        if payload["blocking_issues"]:
            print("Blocking issues:")
            for issue in payload["blocking_issues"]:
                print(f"- {issue}")
        print("Revision priorities:")
        for priority in payload["revision_priorities"]:
            print(f"- {priority}")
    else:
        print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
