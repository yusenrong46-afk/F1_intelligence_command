#!/usr/bin/env python3
"""Evaluate the M8 artifact-backed analytic chatbot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from burnaby_prototype.config import write_json
from burnaby_prototype.m8.chatbot.analyst_tools import answer_m8_question, load_chatbot_context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=str(ROOT / "benchmark" / "gold" / "m8_chatbot_gold_cases.json"))
    parser.add_argument("--output-dir", default=str(ROOT / "outputs" / "m8_runs" / "burnaby_r1" / "local_m8"))
    parser.add_argument("--out", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = read_json(Path(args.cases), [])
    context = load_chatbot_context(args.output_dir)
    rows = []
    for case in cases:
        answer = answer_m8_question(case["question"], context)
        missing = [token for token in case.get("must_include", []) if token.lower() not in answer.lower()]
        rows.append(
            {
                "case_id": case["case_id"],
                "question": case["question"],
                "answer": answer,
                "passed": not missing,
                "missing": missing,
            }
        )
    report = {
        "case_count": len(rows),
        "passed_count": sum(1 for row in rows if row["passed"]),
        "hard_failures": [row["case_id"] for row in rows if not row["passed"]],
        "cases": rows,
    }
    out = Path(args.out) if args.out else Path(args.output_dir) / "m8_chatbot_eval.json"
    write_json(out, report)
    print("M8 chatbot benchmark complete")
    print(f"Cases passed: {report['passed_count']}/{report['case_count']}")
    print(f"Hard failures: {len(report['hard_failures'])}")
    return 0 if not report["hard_failures"] else 1


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
