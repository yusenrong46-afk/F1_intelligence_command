"""Offline evaluation for the three benchmarked cities (L3).

For each city this runs, with no model call and no network:

* ``benchmark/evaluate_benchmark.py`` against the committed M7 run in
  ``outputs/m7_runs/<city>/google_gemini_3_1_flash_lite`` (reports go to a
  temporary ``--report-dir`` so the committed artifacts are never touched);
* ``benchmark/evaluate_adversarial.py`` on the city's poisoned cases (and
  Burnaby's poisoned evidence bundles).

It writes ``outputs/eval_summary.json``: deterministic, sorted keys, floats
rounded to four places, no timestamps, so two runs give byte-identical files.
Wall-clock timings and the run date go to ``outputs/eval_summary.meta.json``,
which the reproducibility check excludes.

Usage: ``python scripts/run_eval.py [--out outputs/eval_summary.json]``.
Exit 1 when an evaluator fails to produce its report.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = "google_gemini_3_1_flash_lite"
CITIES = {
    "burnaby_r1": "Burnaby R1",
    "calgary_rcg": "Calgary R-CG",
    "vancouver_rs": "Vancouver RS",
}
SUMMARY_VERSION = 1

BENCHMARK_FIELDS = (
    "gold_rule_count",
    "candidate_rule_count",
    "verified_rule_count",
    "review_rule_count",
    "rejected_rule_count",
    "not_used_rule_count",
    "verified_precision",
    "false_verified_count",
    "extraction_coverage_recall",
    "verified_gold_recall",
    "verified_source_support_failed_count",
)
PROPOSAL_FIELDS = ("proposal_case_count", "proposal_case_accuracy", "false_approval_count")
ADVERSARIAL_FIELDS = {
    "total_cases": "cases",
    "blocked_count": "blocked",
    "leaked_count": "leaked",
    "decision_mismatch_count": "decision_mismatches",
    "bundle_case_count": "bundle_cases",
    "bundle_blocked_count": "bundle_blocked",
    "bundle_leaked_count": "bundle_leaked",
}


def _round(value: Any) -> Any:
    return round(value, 4) if isinstance(value, float) else value


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)  # noqa: S603
    return proc.returncode, (proc.stdout + proc.stderr)


def evaluate_city(city: str, work: Path) -> tuple[dict[str, Any], dict[str, float]]:
    timings: dict[str, float] = {}
    output_dir = Path("outputs") / "m7_runs" / city / MODEL_DIR
    report_dir = work / city
    started = time.perf_counter()
    code, log = _run([
        sys.executable, "benchmark/evaluate_benchmark.py", "--city", city,
        "--output-dir", str(output_dir), "--report-dir", str(report_dir),
    ])
    timings["benchmark_seconds"] = round(time.perf_counter() - started, 3)
    report_path = report_dir / "benchmark_report.json"
    if not report_path.exists():
        raise RuntimeError(f"{city}: benchmark produced no report (exit {code})\n{log}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rule = report["rule_metrics"]
    proposal = report.get("proposal_metrics") or {}

    cases = Path("benchmark") / "gold" / f"{city}_adversarial_cases.json"
    bundles = Path("benchmark") / "gold" / f"{city}_adversarial_bundles.json"
    adversarial_out = work / f"{city}_adversarial.json"
    started = time.perf_counter()
    code, log = _run([
        sys.executable, "benchmark/evaluate_adversarial.py", "--config", f"configs/{city}.json",
        "--cases", str(cases),
        # The evaluator defaults to Burnaby's bundles; only pass a city's own.
        "--bundle-cases", str(bundles if (ROOT / bundles).exists() else work / "no_bundles.json"),
        "--out", str(adversarial_out),
    ])
    timings["adversarial_seconds"] = round(time.perf_counter() - started, 3)
    if not adversarial_out.exists():
        raise RuntimeError(f"{city}: adversarial benchmark produced no report (exit {code})\n{log}")
    adversarial = json.loads(adversarial_out.read_text(encoding="utf-8"))

    summary = {
        "label": CITIES[city],
        "artifacts": output_dir.as_posix(),
        "benchmark": {field: _round(rule.get(field)) for field in BENCHMARK_FIELDS},
        "proposals": {field: _round(proposal.get(field)) for field in PROPOSAL_FIELDS},
        "quality_gates_passed": bool((report.get("quality_gates") or {}).get("passed")),
        "adversarial": {name: adversarial.get(key) for key, name in ADVERSARIAL_FIELDS.items()},
        "adversarial_leaked_case_ids": sorted(
            [*adversarial.get("leaked_case_ids", []), *adversarial.get("bundle_leaked_case_ids", [])]
        ),
    }
    return summary, timings


def build_summary() -> tuple[dict[str, Any], dict[str, Any]]:
    cities: dict[str, Any] = {}
    timings: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="eval-") as tmp:
        for city in CITIES:
            cities[city], timings[city] = evaluate_city(city, Path(tmp))
    totals = {
        "verified_rule_count": sum(c["benchmark"]["verified_rule_count"] for c in cities.values()),
        "review_rule_count": sum(c["benchmark"]["review_rule_count"] for c in cities.values()),
        "false_verified_count": sum(c["benchmark"]["false_verified_count"] for c in cities.values()),
        "adversarial_cases": sum(c["adversarial"]["cases"] for c in cities.values()),
        "adversarial_bundles": sum(c["adversarial"]["bundle_cases"] for c in cities.values()),
        "adversarial_leaked": sum(
            c["adversarial"]["leaked"] + c["adversarial"]["bundle_leaked"] for c in cities.values()
        ),
        "min_verified_precision": min(c["benchmark"]["verified_precision"] for c in cities.values()),
    }
    summary = {
        "summary_version": SUMMARY_VERSION,
        "model_calls": 0,
        "paid_cost_usd": 0.0,
        "cities": cities,
        "totals": totals,
    }
    meta = {
        "measured_on": datetime.now(timezone.utc).date().isoformat(),
        "python": sys.version.split()[0],
        "timings_seconds": timings,
    }
    return summary, meta


def dumps(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def repro(committed: Path) -> int:
    try:
        first, second = dumps(build_summary()[0]), dumps(build_summary()[0])
    except RuntimeError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if first != second:
        print("FAIL two eval runs gave different summaries", file=sys.stderr)
        return 1
    if not committed.exists() or committed.read_text(encoding="utf-8") != first:
        print(f"FAIL fresh eval summary differs from {committed.name}; run `make eval docs`", file=sys.stderr)
        return 1
    print(f"PASS eval summary byte-identical across two runs and equal to {committed.name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "eval_summary.json")
    parser.add_argument("--meta", type=Path, default=None, help="default: <out stem>.meta.json")
    parser.add_argument(
        "--repro", action="store_true",
        help="write nothing; build the summary twice and require both to equal --out byte-for-byte",
    )
    args = parser.parse_args(argv)
    if args.repro:
        return repro(args.out)
    try:
        summary, meta = build_summary()
    except RuntimeError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    meta_path = args.meta or args.out.with_name(args.out.stem + ".meta.json")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(dumps(summary), encoding="utf-8")
    meta_path.write_text(dumps(meta), encoding="utf-8")
    for city, data in summary["cities"].items():
        b, a = data["benchmark"], data["adversarial"]
        print(
            f"{city}: verified {b['verified_rule_count']} review {b['review_rule_count']} "
            f"precision {b['verified_precision']:.2f} false verified {b['false_verified_count']} "
            f"coverage {b['extraction_coverage_recall']} | poisoned {a['blocked']}/{a['cases']} blocked, "
            f"bundles {a['bundle_blocked']}/{a['bundle_cases']}, leaked {a['leaked'] + a['bundle_leaked']}"
        )
    print(f"wrote {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
