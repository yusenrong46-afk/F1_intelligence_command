#!/usr/bin/env python3
"""Run M8.5 dry-run stress across available city artifacts."""

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

from burnaby_prototype.m8_5.multi_city import run_multi_city_stress


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cities", nargs="*", default=None, help="Subset of city IDs to run.")
    parser.add_argument("--output-dir", default=str(ROOT / "outputs" / "m8_5_runs" / "multi_city"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-bootstrap-m8", action="store_true", help="Skip cities without existing M8 artifacts.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    result = run_multi_city_stress(
        root=ROOT,
        output_root=ROOT / "outputs" / "m8_5_runs",
        cities=args.cities,
        dry_run=bool(args.dry_run),
        bootstrap_m8=not args.no_bootstrap_m8,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "city_run_matrix.json", result["city_run_matrix"])
    write_json(output_dir / "cross_city_summary.json", result["cross_city_summary"])
    write_json(output_dir / "city_format_profiles.json", result["city_format_profiles"])
    write_json(output_dir / "generalization_report.json", {"markdown": result["generalization_report"]})
    (output_dir / "generalization_report.md").write_text(result["generalization_report"], encoding="utf-8")
    summary = result["cross_city_summary"]
    update_city_metric_states(result["city_run_matrix"], output_dir)
    print("M8.5 multi-city stress complete")
    print(f"Measured cities: {summary['measured_city_count']}")
    print(f"Skipped cities: {summary['skipped_city_count']}")
    print(f"Failed cities: {summary['failed_city_count']}")
    print(f"False verified total: {summary['false_verified_total']}")
    return 0 if summary["safety_preserved"] else 1


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def update_city_metric_states(matrix: dict[str, Any], output_dir: Path) -> None:
    for row in matrix.get("results", []):
        if row.get("status") != "measured":
            continue
        comparison_path = Path(row["output_dir"]) / "m8_m8_5_comparison.json"
        comparison = read_json(comparison_path, {})
        if not comparison:
            continue
        m8_5 = comparison.setdefault("m8_5", {})
        states = m8_5.setdefault("metric_states", {})
        states["m8_5_multi_city_stress"] = {
            "state": "measured",
            "value": "measured",
            "source": str(output_dir / "cross_city_summary.json"),
            "note": "included in latest multi-city stress run",
        }
        write_json(comparison_path, comparison)


if __name__ == "__main__":
    raise SystemExit(main())
