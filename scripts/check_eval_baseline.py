"""Fail when a guarded evaluation number falls below its committed baseline (L3).

Compares ``outputs/eval_summary.json`` with ``benchmark/eval_baseline.json``.
Per city: false verified at most the max (0), verified precision at least the
min (1.00), adversarial leaks (cases plus bundles) at most the max (0),
extraction coverage recall at least the min, and verified and review counts
exactly equal to the committed counts.

Usage: ``python scripts/check_eval_baseline.py [--summary ...] [--baseline ...]``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def check(summary: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for city, guard in baseline["cities"].items():
        data = summary.get("cities", {}).get(city)
        if data is None:
            problems.append(f"{city}: missing from the eval summary")
            continue
        b, a = data["benchmark"], data["adversarial"]
        leaked = a["leaked"] + a["bundle_leaked"]
        checks = [
            ("false verified", b["false_verified_count"], "<=", guard["false_verified_count_max"]),
            ("verified precision", b["verified_precision"], ">=", guard["verified_precision_min"]),
            ("adversarial leaked", leaked, "<=", guard["adversarial_leaked_max"]),
            ("extraction coverage recall", b["extraction_coverage_recall"], ">=", guard["extraction_coverage_recall_min"]),
            ("verified count", b["verified_rule_count"], "==", guard["verified_rule_count"]),
            ("review count", b["review_rule_count"], "==", guard["review_rule_count"]),
        ]
        for name, value, op, bound in checks:
            ok = value is not None and {
                "<=": lambda v, x: v <= x, ">=": lambda v, x: v >= x, "==": lambda v, x: v == x
            }[op](value, bound)
            line = f"{city}: {name} {value} (baseline {op} {bound})"
            if not ok:
                problems.append(line)
            else:
                print(f"PASS {line}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--summary", type=Path, default=ROOT / "outputs" / "eval_summary.json")
    parser.add_argument("--baseline", type=Path, default=ROOT / "benchmark" / "eval_baseline.json")
    args = parser.parse_args(argv)
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    problems = check(summary, baseline)
    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
