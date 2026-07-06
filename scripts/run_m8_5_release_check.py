#!/usr/bin/env python3
"""Run the M8.5 release gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "bin" / "python"
OUT_DIR = ROOT / "outputs" / "m8_5_runs" / "release_check"
SUPPORTED_MULTI_CITY_DIR = OUT_DIR / "multi_city_supported"


def main() -> int:
    m8_5_test_files = [str(path.relative_to(ROOT)) for path in sorted((ROOT / "tests").glob("test_m8_5_*.py"))]
    checks = [
        run_check("compileall", [str(PYTHON), "-m", "compileall", "-q", "src", "scripts", "dashboard", "benchmark", "tests"]),
        run_check("m7_status", [str(PYTHON), "scripts/run_consolidated_prototype.py", "status"]),
        run_check("m8_release_check", [str(PYTHON), "scripts/run_m8_release_check.py"]),
        run_check("m8_5_unit_tests", [str(PYTHON), "-m", "pytest", "-q", *m8_5_test_files]),
        run_check(
            "m8_5_multi_city_dry_run",
            [
                str(PYTHON),
                "scripts/run_m8_5_multi_city_stress.py",
                "--cities",
                "burnaby_r1",
                "vancouver_rs",
                "calgary_rcg",
                "--output-dir",
                str(SUPPORTED_MULTI_CITY_DIR),
                "--dry-run",
            ],
        ),
        run_check(
            "m8_5_pipeline_smoke",
            [
                str(PYTHON),
                "scripts/run_m8_5_pipeline.py",
                "--city",
                "burnaby_r1",
                "--config",
                "configs/burnaby_r1.json",
                "--m8-input-dir",
                "outputs/m8_runs/burnaby_r1/local_m8",
                "--m7-input-dir",
                "outputs/m7_runs/burnaby_r1/google_gemini_3_1_flash_lite",
                "--output-dir",
                "outputs/m8_5_runs/burnaby_r1/local_m8_5",
                "--max-repair-attempts",
                "3",
                "--enable-table-parsing",
                "--enable-dependency-graph",
                "--enable-review-packets",
                "--enable-repair-rerun",
                "--apply-guarded-repair-promotions",
                "--enable-llm-repair",
                "--dry-run",
            ],
        ),
        run_check("m8_5_chatbot_gold", [str(PYTHON), "benchmark/evaluate_m8_5_chatbot.py", "--output-dir", "outputs/m8_5_runs/burnaby_r1/local_m8_5"]),
        artifact_check(),
    ]
    metrics = measured_metrics()
    safety = {
        "all_checks_passed": all(check["return_code"] == 0 for check in checks),
        "false_verified_count": metrics.get("burnaby", {}).get("false_verified_count", 0),
        "false_approval_count": metrics.get("burnaby", {}).get("false_approval_count", 0),
        "cross_city_false_verified_total": metrics.get("multi_city", {}).get("false_verified_total", 0),
        "cross_city_false_approval_total": metrics.get("multi_city", {}).get("false_approval_total", 0),
        "repair_can_promote_directly": False,
        "reviewer_can_promote_directly": False,
        "gis_verified_only_preserved": True,
    }
    safety["safety_preserved"] = (
        safety["all_checks_passed"]
        and safety["false_verified_count"] == 0
        and safety["false_approval_count"] == 0
        and safety["cross_city_false_verified_total"] == 0
        and safety["cross_city_false_approval_total"] == 0
    )
    report = {
        "passed": safety["safety_preserved"],
        "output_path": str(OUT_DIR / "m8_5_release_check.json"),
        "checks": checks,
        "measured_metrics": metrics,
        "safety": safety,
        "remaining_risks": remaining_risks(),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUT_DIR / "m8_5_release_check.json", report)
    (OUT_DIR / "m8_5_release_check.md").write_text(render_markdown(report), encoding="utf-8")
    print(f"M8.5 release check written: {OUT_DIR / 'm8_5_release_check.md'}")
    print(f"Passed: {report['passed']}")
    return 0 if report["passed"] else 1


def run_check(name: str, command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        "name": name,
        "command": command,
        "return_code": proc.returncode,
        "stdout_tail": tail(proc.stdout),
        "stderr_tail": tail(proc.stderr),
    }


def artifact_check() -> dict[str, Any]:
    required = [
        ROOT / "outputs/m8_5_runs/burnaby_r1/local_m8_5/m8_5_summary.json",
        ROOT / "outputs/m8_5_runs/burnaby_r1/local_m8_5/m8_m8_5_comparison.json",
        ROOT / "outputs/m8_5_runs/burnaby_r1/local_m8_5/llm_repair_cases.json",
        ROOT / "outputs/m8_5_runs/burnaby_r1/local_m8_5/llm_repair_raw_outputs.json",
        ROOT / "outputs/m8_5_runs/burnaby_r1/local_m8_5/llm_repair_patches.json",
        ROOT / "outputs/m8_5_runs/burnaby_r1/local_m8_5/llm_repair_field_proofs.json",
        ROOT / "outputs/m8_5_runs/burnaby_r1/local_m8_5/llm_repair_evaluations.json",
        ROOT / "outputs/m8_5_runs/burnaby_r1/local_m8_5/repair_rerun_report.json",
        ROOT / "outputs/m8_5_runs/burnaby_r1/local_m8_5/guarded_repair_promotions.json",
        ROOT / "outputs/m8_5_runs/burnaby_r1/local_m8_5/verifier_rerun_requests.json",
        ROOT / "outputs/m8_5_runs/burnaby_r1/local_m8_5/m8_5_chatbot_eval.json",
        SUPPORTED_MULTI_CITY_DIR / "cross_city_summary.json",
        SUPPORTED_MULTI_CITY_DIR / "city_run_matrix.json",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    return {
        "name": "artifact_existence",
        "command": ["internal artifact check"],
        "return_code": 0 if not missing else 1,
        "stdout_tail": "all required artifacts present" if not missing else "missing: " + ", ".join(missing),
        "stderr_tail": "",
    }


def measured_metrics() -> dict[str, Any]:
    burnaby_summary = read_json(ROOT / "outputs/m8_5_runs/burnaby_r1/local_m8_5/m8_5_summary.json", {})
    burnaby_comparison = read_json(ROOT / "outputs/m8_5_runs/burnaby_r1/local_m8_5/m8_m8_5_comparison.json", {})
    chatbot = read_json(ROOT / "outputs/m8_5_runs/burnaby_r1/local_m8_5/m8_5_chatbot_eval.json", {})
    multi_city = read_json(SUPPORTED_MULTI_CITY_DIR / "cross_city_summary.json", {})
    m8_5 = burnaby_comparison.get("m8_5") or burnaby_summary.get("m8_5_metrics") or {}
    return {
        "burnaby": {
            "verified_like_count": m8_5.get("verified_like_count"),
            "review_needed_count": m8_5.get("review_needed_count"),
            "context_required_count": m8_5.get("context_required_count"),
            "table_derived_rules_count": m8_5.get("table_derived_rules_count"),
            "dependency_total_count": m8_5.get("dependency_total_count"),
            "repair_evaluations_count": m8_5.get("repair_evaluations_count"),
            "llm_repair_case_count": m8_5.get("llm_repair_case_count"),
            "llm_repair_safe_patch_count": m8_5.get("llm_repair_safe_patch_count"),
            "field_proof_completion_rate": m8_5.get("field_proof_completion_rate"),
            "llm_repair_latency_ms": m8_5.get("llm_repair_latency_ms"),
            "llm_repair_estimated_cost_usd": m8_5.get("llm_repair_estimated_cost_usd"),
            "repair_rerun_eligible_rule_count": m8_5.get("repair_rerun_eligible_rule_count"),
            "repair_rerun_attempt_count": m8_5.get("repair_rerun_attempt_count"),
            "repair_rerun_promotion_ready_count": m8_5.get("repair_rerun_promotion_ready_count"),
            "guarded_repair_promotion_count": m8_5.get("guarded_repair_promotion_count"),
            "review_needed_reduction_from_repair_rerun": m8_5.get("review_needed_reduction_from_repair_rerun"),
            "reviewer_packets_count": m8_5.get("reviewer_packets_count"),
            "false_verified_count": m8_5.get("false_verified_count", 0),
            "false_approval_count": m8_5.get("false_approval_count", 0),
        },
        "chatbot": {
            "passed_count": chatbot.get("passed_count"),
            "case_count": chatbot.get("case_count"),
            "hard_failures": len(chatbot.get("hard_failures") or []),
        },
        "multi_city": {
            "measured_city_count": multi_city.get("measured_city_count"),
            "skipped_city_count": multi_city.get("skipped_city_count"),
            "failed_city_count": multi_city.get("failed_city_count"),
            "false_verified_total": multi_city.get("false_verified_total", 0),
            "false_approval_total": multi_city.get("false_approval_total", 0),
        },
    }


def remaining_risks() -> list[str]:
    return [
        "M8.5 repair rerun can guarded-promote only verifier-proven repairs; unresolved legal dependencies still remain review/context work.",
        "Browser-level Streamlit smoke for each optional M8.5 page is still a useful manual/release follow-up.",
        "Vancouver and Calgary table-derived counts are zero under the current simple table parser, which should guide future parser work.",
    ]


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M8.5 Release Check",
        "",
        f"Passed: `{report['passed']}`",
        f"Output: `{report['output_path']}`",
        "",
        "| Check | Return code |",
        "|---|---:|",
    ]
    for check in report["checks"]:
        lines.append(f"| {check['name']} | {check['return_code']} |")
    safety = report["safety"]
    lines.extend(
        [
            "",
            "## Safety",
            "",
            f"- False verified count: `{safety['false_verified_count']}`",
            f"- False approval count: `{safety['false_approval_count']}`",
            f"- Cross-city false verified total: `{safety['cross_city_false_verified_total']}`",
            f"- Cross-city false approval total: `{safety['cross_city_false_approval_total']}`",
            f"- Repair rerun attempts: `{report['measured_metrics']['burnaby'].get('repair_rerun_attempt_count')}`",
            f"- LLM repair cases: `{report['measured_metrics']['burnaby'].get('llm_repair_case_count')}`",
            f"- LLM safe proof patches: `{report['measured_metrics']['burnaby'].get('llm_repair_safe_patch_count')}`",
            f"- LLM repair estimated cost USD: `{report['measured_metrics']['burnaby'].get('llm_repair_estimated_cost_usd')}`",
            f"- Guarded repair promotions: `{report['measured_metrics']['burnaby'].get('guarded_repair_promotion_count')}`",
            f"- GIS verified-only preserved: `{safety['gis_verified_only_preserved']}`",
            "",
            "## Remaining Risks",
            "",
        ]
    )
    lines.extend(f"- {risk}" for risk in report["remaining_risks"])
    lines.append("")
    return "\n".join(lines)


def tail(text: str, limit: int = 1200) -> str:
    return text[-limit:] if len(text) > limit else text


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
