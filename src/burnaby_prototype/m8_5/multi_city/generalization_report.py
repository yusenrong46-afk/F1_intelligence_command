"""Cross-city M8.5 generalization summaries."""

from __future__ import annotations

from typing import Any

from .city_run_matrix import CityRunResult


def build_cross_city_summary(results: list[CityRunResult], profiles: list[dict[str, Any]]) -> dict[str, Any]:
    measured = [result for result in results if result.status.startswith("measured")]
    unsafe = [result for result in results if result.status == "measured_unsafe"]
    skipped = [result for result in results if result.status == "skipped"]
    failed = [result for result in results if result.status == "failed"]
    false_verified_total = sum(int((result.measured_metrics or {}).get("false_verified_count", 0) or 0) for result in measured)
    false_approval_total = sum(int((result.measured_metrics or {}).get("false_approval_count", 0) or 0) for result in measured)
    repair_attempt_total = sum(int((result.measured_metrics or {}).get("repair_rerun_attempt_count", 0) or 0) for result in measured)
    guarded_promotion_total = sum(int((result.measured_metrics or {}).get("guarded_repair_promotion_count", 0) or 0) for result in measured)
    llm_safe_patch_total = sum(int((result.measured_metrics or {}).get("llm_repair_safe_patch_count", 0) or 0) for result in measured)
    return {
        "measured_city_count": len(measured),
        "measured_unsafe_city_count": len(unsafe),
        "skipped_city_count": len(skipped),
        "failed_city_count": len(failed),
        "measured_cities": [result.city for result in measured],
        "measured_city_metrics": [_city_metric_row(result) for result in measured],
        "skipped_cities": [
            {
                "city": result.city,
                "reason": result.skip_reason,
                "source_status": result.source_status,
                "source_pdf": result.source_pdf,
                "source_provenance": result.source_provenance,
            }
            for result in skipped
        ],
        "failed_cities": [{"city": result.city, "return_code": result.return_code} for result in failed],
        "false_verified_total": false_verified_total,
        "false_approval_total": false_approval_total,
        "repair_rerun_attempt_total": repair_attempt_total,
        "guarded_repair_promotion_total": guarded_promotion_total,
        "llm_repair_safe_patch_total": llm_safe_patch_total,
        "safety_preserved": false_verified_total == 0 and false_approval_total == 0 and not failed and not unsafe,
        "profiles": profiles,
    }


def _city_metric_row(result: CityRunResult) -> dict[str, Any]:
    metrics = result.measured_metrics or {}
    return {
        "city": result.city,
        "status": result.status,
        "verified_like_count": int(metrics.get("verified_like_count", 0) or 0),
        "review_needed_count": int(metrics.get("review_needed_count", 0) or 0),
        "repair_rerun_attempt_count": int(metrics.get("repair_rerun_attempt_count", 0) or 0),
        "llm_repair_safe_patch_count": int(metrics.get("llm_repair_safe_patch_count", 0) or 0),
        "guarded_repair_promotion_count": int(metrics.get("guarded_repair_promotion_count", 0) or 0),
        "false_verified_count": int(metrics.get("false_verified_count", 0) or 0),
        "false_approval_count": int(metrics.get("false_approval_count", 0) or 0),
    }


def render_generalization_report(summary: dict[str, Any]) -> str:
    lines = [
        "# M8.5 Multi-City Generalization Report",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Measured cities | {summary['measured_city_count']} |",
        f"| Measured unsafe cities | {summary['measured_unsafe_city_count']} |",
        f"| Skipped cities | {summary['skipped_city_count']} |",
        f"| Failed cities | {summary['failed_city_count']} |",
        f"| Repair rerun attempts | {summary['repair_rerun_attempt_total']} |",
        f"| LLM safe proof patches | {summary['llm_repair_safe_patch_total']} |",
        f"| Guarded repair promotions | {summary['guarded_repair_promotion_total']} |",
        f"| False verified total | {summary['false_verified_total']} |",
        f"| False approval total | {summary['false_approval_total']} |",
        "",
        f"Safety preserved: `{summary['safety_preserved']}`",
        "",
    ]
    if summary.get("measured_city_metrics"):
        lines.extend(
            [
                "## Measured Cities",
                "",
                "| City | Status | Verified-like | Review needed | Repair attempts | Safe proof patches | Guarded promotions | False verified | False approvals |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in summary["measured_city_metrics"]:
            lines.append(
                f"| `{row['city']}` | `{row['status']}` | {row['verified_like_count']} | {row['review_needed_count']} | "
                f"{row['repair_rerun_attempt_count']} | {row['llm_repair_safe_patch_count']} | "
                f"{row['guarded_repair_promotion_count']} | {row['false_verified_count']} | "
                f"{row['false_approval_count']} |"
            )
        lines.append("")
    if summary.get("skipped_cities"):
        lines.extend(["## Skipped Cities", ""])
        for row in summary["skipped_cities"]:
            source_note = f" ({row['source_status']})" if row.get("source_status") else ""
            lines.append(f"- `{row['city']}`: {row['reason']}{source_note}")
        lines.append("")
    return "\n".join(lines)
