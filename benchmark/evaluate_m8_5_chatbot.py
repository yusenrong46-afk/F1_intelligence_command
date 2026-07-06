#!/usr/bin/env python3
"""Evaluate the M8.5 artifact-grounded analytic chatbot."""

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
from burnaby_prototype.m8_5.chatbot import answer_m8_5_question, load_m8_5_chatbot_context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=str(ROOT / "benchmark" / "gold" / "m8_5_chatbot_gold_cases.json"))
    parser.add_argument("--output-dir", default=str(ROOT / "outputs" / "m8_5_runs" / "burnaby_r1" / "local_m8_5"))
    parser.add_argument("--out", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = read_json(Path(args.cases), [])
    context = load_m8_5_chatbot_context(args.output_dir)
    rows = []
    for case in cases:
        answer = answer_m8_5_question(case["question"], context)
        missing = [token for token in case.get("must_include", []) if token.lower() not in answer.lower()]
        rows.append(
            {
                "case_id": case["case_id"],
                "category": case.get("category"),
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
        "category_counts": category_counts(rows),
        "cases": rows,
    }
    out = Path(args.out) if args.out else Path(args.output_dir) / "m8_5_chatbot_eval.json"
    write_json(out, report)
    update_comparison_metric_state(Path(args.output_dir), report)
    print("M8.5 chatbot benchmark complete")
    print(f"Cases passed: {report['passed_count']}/{report['case_count']}")
    print(f"Hard failures: {len(report['hard_failures'])}")
    return 0 if not report["hard_failures"] else 1


def category_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        category = str(row.get("category") or "uncategorized")
        bucket = counts.setdefault(category, {"case_count": 0, "passed_count": 0})
        bucket["case_count"] += 1
        bucket["passed_count"] += int(bool(row.get("passed")))
    return dict(sorted(counts.items()))


def update_comparison_metric_state(output_dir: Path, report: dict[str, Any]) -> None:
    path = output_dir / "m8_m8_5_comparison.json"
    if not path.exists():
        return
    comparison = read_json(path, {})
    m8_5 = comparison.setdefault("m8_5", {})
    states = m8_5.setdefault("metric_states", {})
    states["m8_5_chatbot_gold"] = {
        "state": "measured",
        "value": f"{report['passed_count']}/{report['case_count']}",
        "source": "m8_5_chatbot_eval.json",
        "note": f"hard failures {len(report['hard_failures'])}",
    }
    write_json(path, comparison)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
