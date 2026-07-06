"""City format profiles for M8.5 stress output."""

from __future__ import annotations

from typing import Any


def build_city_format_profile(
    *,
    city: str,
    summary: dict[str, Any],
    comparison: dict[str, Any],
    table_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    metrics = comparison.get("m8_5") or summary.get("m8_5_metrics") or {}
    source_coverage = metrics.get("coverage_by_table_vs_prose_source") or []
    return {
        "city": city,
        "table_block_count": metrics.get("table_block_count", len(table_blocks)),
        "table_derived_rules_count": metrics.get("table_derived_rules_count", 0),
        "dependency_total_count": metrics.get("dependency_total_count", 0),
        "dependency_status_counts": metrics.get("dependency_status_counts", {}),
        "reviewer_packets_count": metrics.get("reviewer_packets_count", 0),
        "false_verified_count": metrics.get("false_verified_count", 0),
        "false_approval_count": metrics.get("false_approval_count", 0),
        "source_coverage": source_coverage,
        "format_notes": _format_notes(metrics, source_coverage),
    }


def _format_notes(metrics: dict[str, Any], source_coverage: list[dict[str, Any]]) -> list[str]:
    notes = []
    if metrics.get("table_derived_rules_count", 0):
        notes.append("table-derived rules present")
    if metrics.get("dependency_unresolved_count", 0):
        notes.append("unresolved dependencies present")
    if any(row.get("source_type") == "table" for row in source_coverage):
        notes.append("table source coverage tracked")
    if not notes:
        notes.append("no distinctive M8.5 format signals measured")
    return notes
