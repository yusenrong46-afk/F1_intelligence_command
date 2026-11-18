"""Generate the README's result line and results table from the eval summary (L3).

Reads ``outputs/eval_summary.json`` (numbers) and ``outputs/eval_summary.meta.json``
(the date it was measured) and rewrites the text between these markers in
``README.md``:

* ``<!-- result:start -->`` / ``<!-- result:end -->``: the dated result line;
* ``<!-- results:start -->`` / ``<!-- results:end -->``: the per-city table.

``--check`` rewrites nothing and exits 1 when the README differs from what the
summary generates (``make check-docs``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BLOCKS = ("result", "results")


def result_line(summary: dict[str, Any], measured_on: str) -> str:
    t = summary["totals"]
    blocked = (
        f"all {t['adversarial_cases']} poisoned cases and {t['adversarial_bundles']} poisoned "
        "evidence bundles are blocked"
        if t["adversarial_leaked"] == 0
        else f"{t['adversarial_leaked']} of {t['adversarial_cases'] + t['adversarial_bundles']} "
        "poisoned cases leaked through"
    )
    return (
        f"**Result (measured {measured_on}):** {t['verified_rule_count']} rules verified across "
        f"Burnaby, Calgary and Vancouver with verified precision {t['min_verified_precision']:.2f} "
        f"and {t['false_verified_count']} false-verified rules against the gold benchmarks.\n"
        f"In the safety benchmark {blocked}. Offline, no model call (`make eval`)."
    )


def results_table(summary: dict[str, Any]) -> str:
    rows = [
        "| City | Candidates | Verified | Review | Verified precision | False verified | Coverage recall | Poisoned inputs blocked |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for data in summary["cities"].values():
        b, a = data["benchmark"], data["adversarial"]
        total = a["cases"] + a["bundle_cases"]
        rows.append(
            f"| {data['label']} | {b['candidate_rule_count']} | {b['verified_rule_count']} | "
            f"{b['review_rule_count']} | {b['verified_precision']:.2f} | {b['false_verified_count']} | "
            f"{b['extraction_coverage_recall']:.3f} | {a['blocked'] + a['bundle_blocked']} of {total} |"
        )
    return "\n".join(rows)


def render(readme: str, summary: dict[str, Any], measured_on: str) -> str:
    bodies = {"result": result_line(summary, measured_on), "results": results_table(summary)}
    for name in BLOCKS:
        start, end = f"<!-- {name}:start -->", f"<!-- {name}:end -->"
        if start not in readme or end not in readme:
            raise ValueError(f"README is missing the {start} ... {end} markers")
        head, rest = readme.split(start, 1)
        _, tail = rest.split(end, 1)
        readme = f"{head}{start}\n{bodies[name]}\n{end}{tail}"
    return readme


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--summary", type=Path, default=ROOT / "outputs" / "eval_summary.json")
    parser.add_argument("--readme", type=Path, default=ROOT / "README.md")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    meta_path = args.summary.with_name(args.summary.stem + ".meta.json")
    measured_on = json.loads(meta_path.read_text(encoding="utf-8"))["measured_on"]
    current = args.readme.read_text(encoding="utf-8")
    expected = render(current, summary, measured_on)
    if args.check:
        if current != expected:
            print(f"FAIL {args.readme.name} results differ from {args.summary.name}; run `make docs`", file=sys.stderr)
            return 1
        print(f"check-docs OK: {args.readme.name} matches {args.summary.name} (measured {measured_on})")
        return 0
    args.readme.write_text(expected, encoding="utf-8")
    print(f"updated {args.readme.name} from {args.summary.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
