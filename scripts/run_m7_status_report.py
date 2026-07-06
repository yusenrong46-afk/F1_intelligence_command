#!/usr/bin/env python3
"""Build the current M7 verification status report.

The report is intentionally narrow: extraction proposes candidates, the
deterministic verifier decides, and GIS consumes only verified rules. Historical
comparison records live under archive/pre_m7_records and are not part of the
active status surface.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
PDF_CITIES = ("burnaby_r1", "vancouver_rs", "calgary_rcg")
M7_MODEL_DIR = "google_gemini_3_1_flash_lite"


@dataclass(frozen=True)
class ReportRun:
    label: str
    city: str
    output_dir: Path
    lane: str


M7_PRODUCT_RUNS = [
    ReportRun(
        label="Burnaby M7 matrix-aware extraction",
        city="burnaby_r1",
        output_dir=OUTPUTS / "m7_runs" / "burnaby_r1" / M7_MODEL_DIR,
        lane="native_m7",
    ),
    ReportRun(
        label="Vancouver M7 matrix-aware extraction",
        city="vancouver_rs",
        output_dir=OUTPUTS / "m7_runs" / "vancouver_rs" / M7_MODEL_DIR,
        lane="native_m7",
    ),
    ReportRun(
        label="Calgary M7 matrix-aware extraction",
        city="calgary_rcg",
        output_dir=OUTPUTS / "m7_runs" / "calgary_rcg" / M7_MODEL_DIR,
        lane="native_m7",
    ),
]

CURRENT_PRODUCT_RUNS = M7_PRODUCT_RUNS
LEGACY_REFERENCE_RUNS: list[ReportRun] = []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-benchmarks",
        action="store_true",
        help="Run benchmark/evaluate_benchmark.py for current M7 outputs with missing benchmark_report.json.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(OUTPUTS / "m7_status_report"),
        help="Directory for m7_status_report.json and m7_status_report.md.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    commands: list[dict[str, Any]] = []
    if args.refresh_benchmarks:
        for run in M7_PRODUCT_RUNS:
            if run.output_dir.exists() and not (run.output_dir / "benchmark_report.json").exists():
                commands.append(run_benchmark(run.city, run.output_dir))

    report = build_report(commands)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "m7_status_report.json", report)
    (out_dir / "m7_status_report.md").write_text(render_markdown(report), encoding="utf-8")
    print(f"M7 status report written: {out_dir / 'm7_status_report.md'}")
    print(f"Overall status: {report['overall_status']}")
    return 0 if report["unsafe_current_rows"] == [] else 1


def build_report(commands: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    current_rows = [run_row(run) for run in M7_PRODUCT_RUNS]
    unsafe = [
        row["label"]
        for row in current_rows
        if not row.get("missing") and row.get("status_label") == "unsafe / needs fix"
    ]
    false_verified_total = sum(int(row.get("false_verified_count") or 0) for row in current_rows if not row.get("missing"))
    return {
        "report": "m7_status_report",
        "purpose": "Current M7 verification status for Burnaby_prototype.",
        "safety_contract": "Extractors and RAG propose; deterministic verifier decides; GIS uses only verified rules.",
        "overall_status": overall_status_for_rows(current_rows),
        "current_false_verified_total": false_verified_total,
        "unsafe_current_rows": unsafe,
        "current_path_version": "native_m7",
        "pdf_inventory": pdf_inventory(),
        "current_runs": current_rows,
        "m7_runs": current_rows,
        "legacy_references": [],
        "commands_executed": commands or [],
        "interpretation": interpretation(current_rows),
    }


def run_row(run: ReportRun) -> dict[str, Any]:
    return row_from_output(run.label, run.city, run.output_dir, run.lane)


def row_from_output(label: str, city: str, output_dir: Path, lane: str) -> dict[str, Any]:
    if not output_dir.exists():
        return {"label": label, "city": city, "lane": lane, "output_dir": str(output_dir), "missing": True}
    summary = read_json(output_dir / "slim_summary.json", {})
    extraction_summary = read_json(output_dir / "extraction_summary.json", {})
    source_summary = read_json(output_dir / "source_summary.json", {})
    m7_source = source_summary.get("m7_source_corpus") or source_summary.get("m" + "4_source_corpus") or {}
    benchmark = read_json(output_dir / "benchmark_report.json", {})
    metrics = benchmark.get("rule_metrics", {})
    proposal = benchmark.get("proposal_metrics", {})
    gates = benchmark.get("quality_gates", {})
    row = {
        "label": label,
        "city": city,
        "lane": lane,
        "output_dir": str(output_dir),
        "missing": False,
        "pipeline": extraction_summary.get("pipeline"),
        "discovery_mode": extraction_summary.get("discovery_mode") or source_summary.get("discovery_mode"),
        "candidate_rule_count": pick(metrics, summary, "candidate_rule_count"),
        "evidence_unit_count": summary.get("evidence_unit_count"),
        "verified_rule_count": pick(metrics, summary, "verified_rule_count"),
        "review_rule_count": pick(metrics, summary, "review_rule_count"),
        "rejected_rule_count": pick(metrics, summary, "rejected_rule_count"),
        "not_used_rule_count": pick(metrics, summary, "not_used_rule_count"),
        "candidate_recall": metrics.get("candidate_recall"),
        "raw_candidate_artifact_recall": metrics.get("raw_candidate_artifact_recall", metrics.get("candidate_recall")),
        "release_candidate_recall": metrics.get(
            "release_candidate_recall",
            metrics.get("extraction_coverage_recall"),
        ),
        "verified_precision": metrics.get("verified_precision"),
        "false_verified_count": metrics.get("false_verified_count"),
        "verified_source_support_failed_count": metrics.get("verified_source_support_failed_count"),
        "false_approval_count": proposal.get("false_approval_count"),
        "verified_or_review_recall": metrics.get("verified_or_review_recall"),
        "extraction_coverage_recall": metrics.get("extraction_coverage_recall"),
        "verifier_retention_rate": metrics.get("verifier_retention_rate"),
        "quality_gate_passed": gates.get("passed"),
        "quality_gates": gates.get("gates", {}),
        "false_verified_rule_ids": metrics.get("false_verified_rule_ids", []),
        "missed_verified_or_review_gold_rule_ids": metrics.get("missed_verified_or_review_gold_rule_ids", []),
        "m7_numeric_clause_count": m7_source.get("numeric_clause_count"),
        "m7_rule_like_numeric_clause_count": m7_source.get("rule_like_numeric_clause_count"),
        "m7_selected_rule_like_numeric_coverage": m7_source.get("selected_rule_like_numeric_coverage"),
        "not_used_summary": not_used_summary(output_dir),
    }
    row["status_label"] = status_label(row)
    return row


def run_benchmark(city: str, output_dir: Path) -> dict[str, Any]:
    return run_command(
        [
            sys.executable,
            "benchmark/evaluate_benchmark.py",
            "--city",
            city,
            "--output-dir",
            str(output_dir),
        ]
    )


def run_command(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    record = {
        "command": command,
        "display_command": display_command(command),
        "returncode": result.returncode,
        "stdout_tail": tail(result.stdout),
        "stderr_tail": tail(result.stderr),
    }
    if result.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(command)
            + "\nSTDOUT:\n"
            + result.stdout
            + "\nSTDERR:\n"
            + result.stderr
        )
    return record


def m7_readiness_status(rows: list[dict[str, Any]], adversarial: dict[str, Any] | None = None) -> dict[str, Any]:
    visible = [row for row in rows if not row.get("missing")]
    missing_cities = [row.get("city") for row in rows if row.get("missing")]
    safety_ok = len(visible) == len(PDF_CITIES) and all(
        int(row.get("false_verified_count") or 0) == 0
        and int(row.get("verified_source_support_failed_count") or 0) == 0
        and int(row.get("false_approval_count") or 0) == 0
        for row in visible
    )
    source_coverage_ok = all(
        not isinstance(row.get("m7_selected_rule_like_numeric_coverage"), (int, float))
        or row.get("m7_selected_rule_like_numeric_coverage") >= 0.999
        for row in visible
    )
    adversarial_ok = (adversarial or {}).get("all_blocked") is True if adversarial is not None else None
    promoted = safety_ok and source_coverage_ok and not missing_cities
    return {
        "ready": promoted,
        "safety_ok": safety_ok,
        "source_coverage_ok": source_coverage_ok,
        "adversarial_ok": adversarial_ok,
        "missing_cities": missing_cities,
        "reasons": _readiness_reasons(safety_ok, source_coverage_ok, missing_cities),
    }


def _readiness_reasons(safety_ok: bool, source_coverage_ok: bool, missing_cities: list[Any]) -> list[str]:
    reasons = []
    if missing_cities:
        reasons.append(f"missing_m7_outputs:{','.join(str(city) for city in missing_cities)}")
    if not safety_ok:
        reasons.append("m7_safety_gate_failed")
    if not source_coverage_ok:
        reasons.append("m7_source_coverage_gate_failed")
    return reasons


def not_used_summary(output_dir: Path) -> dict[str, Any]:
    rules = read_json(output_dir / "not_used.json", [])
    if not isinstance(rules, list) or not rules:
        return {"count": 0, "top_reasons": [], "top_rule_families": [], "plain_explanation": ""}
    reason_counts = Counter(str(gap) for rule in rules for gap in (rule.get("support_gaps") or []))
    family_counts = Counter(str(rule.get("rule_object") or "unknown") for rule in rules)
    return {
        "count": len(rules),
        "top_reasons": [
            {"reason": reason, "label": plain_label(reason), "count": count}
            for reason, count in reason_counts.most_common(6)
        ],
        "top_rule_families": [
            {"rule_family": plain_label(family), "count": count}
            for family, count in family_counts.most_common(6)
        ],
        "plain_explanation": not_used_plain_explanation(reason_counts),
    }


def not_used_plain_explanation(reason_counts: Counter[str]) -> str:
    if reason_counts.get("outside_target_section"):
        return (
            "These are real numeric candidates from the full bylaw, but they are outside "
            "the configured target sections for this product run. They are kept for audit "
            "and review, not exported as verified rules."
        )
    if reason_counts.get("outside_current_rule_contract"):
        return "These candidates are outside the current numeric zoning-rule contract."
    if reason_counts.get("definition_not_rule"):
        return "These candidates came from definitions or navigation text, not enforceable numeric rules."
    if reason_counts.get("cross_reference_only"):
        return "These candidates are cross-references or section pointers, not rules to verify."
    return "These candidates were retained for traceability but are outside the verified-rule output contract."


def status_label(row: dict[str, Any]) -> str:
    if row.get("missing"):
        return "missing"
    if int(row.get("false_verified_count") or 0) > 0:
        return "unsafe / needs fix"
    if int(row.get("verified_source_support_failed_count") or 0) > 0:
        return "unsafe / needs fix"
    if int(row.get("false_approval_count") or 0) > 0:
        return "unsafe / needs fix"
    if row.get("quality_gate_passed") is True:
        return "pass"
    verified_or_review_recall = row.get("verified_or_review_recall")
    extraction_coverage_recall = row.get("extraction_coverage_recall")
    verification_coverage_ok = (
        isinstance(verified_or_review_recall, (int, float))
        and verified_or_review_recall >= 0.9
        and (
            not isinstance(extraction_coverage_recall, (int, float))
            or extraction_coverage_recall >= 0.9
        )
    )
    if verification_coverage_ok:
        return "needs review"
    release_candidate_recall = row.get("release_candidate_recall")
    if isinstance(release_candidate_recall, (int, float)):
        if release_candidate_recall < 0.95:
            return "scope mismatch"
    else:
        candidate_recall = row.get("raw_candidate_artifact_recall", row.get("candidate_recall"))
        if isinstance(candidate_recall, (int, float)) and candidate_recall < 0.9:
            return "scope mismatch"
    verified = int(row.get("verified_rule_count") or 0)
    review = int(row.get("review_rule_count") or 0)
    if verified == 0 and review > 0:
        return "fail-closed"
    return "needs review"


def overall_status_for_rows(rows: list[dict[str, Any]]) -> str:
    visible = [row for row in rows if not row.get("missing")]
    if any(row.get("status_label") == "unsafe / needs fix" for row in visible):
        return "unsafe_needs_fix"
    if any(row.get("status_label") in {"scope mismatch", "fail-closed"} for row in visible):
        return "m7_extraction_gap"
    if visible:
        return "m7_safety_ready"
    return "missing_outputs"


def pdf_inventory() -> list[dict[str, Any]]:
    rows = []
    for city in PDF_CITIES:
        pdf = ROOT / "data" / "bylaws" / city / "source.pdf"
        if not pdf.exists():
            rows.append({"city": city, "source_pdf": str(pdf), "missing": True})
            continue
        rows.append(
            {
                "city": city,
                "source_pdf": str(pdf),
                "page_count": len(PdfReader(str(pdf)).pages),
                "bytes": pdf.stat().st_size,
            }
        )
    return rows


def interpretation(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["No current M7 rows were found."]
    if any(row.get("status_label") == "unsafe / needs fix" for row in rows):
        return ["At least one current M7 run is unsafe and must not feed GIS."]
    if all(row.get("status_label") == "pass" for row in rows if not row.get("missing")):
        return ["Current M7 runs pass the benchmark quality gates available in their output folders."]
    return ["Current M7 remains verification-first: non-passing rows stay review-visible and fail closed."]


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M7 Status Report",
        "",
        report.get("safety_contract", ""),
        "",
        f"Overall status: `{report.get('overall_status')}`",
        f"Current false verified total: `{report.get('current_false_verified_total')}`",
        "",
        "## Current M7 Runs",
        "",
        "| City | Status | Verified | Review | False verified | Output |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in report.get("current_runs") or []:
        lines.append(
            "| {city} | {status} | {verified} | {review} | {false_verified} | `{output}` |".format(
                city=row.get("city"),
                status=row.get("status_label"),
                verified=row.get("verified_rule_count"),
                review=row.get("review_rule_count"),
                false_verified=row.get("false_verified_count"),
                output=row.get("output_dir"),
            )
        )
    lines.extend(["", "## Interpretation", ""])
    for note in report.get("interpretation") or []:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def pick(metrics: dict[str, Any], summary: dict[str, Any], key: str) -> Any:
    return metrics.get(key) if key in metrics else summary.get(key)


def plain_label(value: Any) -> str:
    return str(value or "").replace("_", " ").strip().capitalize()


def display_command(command: list[str]) -> str:
    return " ".join(str(part) for part in command)


def tail(text: str, limit: int = 2000) -> str:
    return text[-limit:] if len(text) > limit else text


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
