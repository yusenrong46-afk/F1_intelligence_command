"""Pure data providers for M8.5 dashboard pages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_m8_5_output(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    return {
        "summary": _read_json(output / "m8_5_summary.json", {}),
        "comparison": _read_json(output / "m8_m8_5_comparison.json", {}),
        "table_blocks": _read_json(output / "table_blocks.json", []),
        "table_cell_lineage": _read_json(output / "table_cell_lineage.json", []),
        "table_derived_rules": _read_json(output / "table_derived_rules.json", []),
        "dependency_graph": _read_json(output / "dependency_graph.json", {}),
        "dependency_resolutions": _read_json(output / "dependency_resolutions.json", []),
        "repair_evaluations": _read_json(output / "repair_evaluations.json", []),
        "review_packets": _read_json(output / "review_packets.json", []),
        "verifier_rerun_requests": _read_json(output / "verifier_rerun_requests.json", []),
        "rules": _read_json(output / "m8_5_structured_rules.json", []),
        "decisions": _read_json(output / "m8_5_verification_decisions.json", []),
    }


def m8_5_metric_cards(data: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = ((data.get("comparison") or {}).get("m8_5") or (data.get("summary") or {}).get("m8_5_metrics") or {})
    return [
        {"label": "Verified-like", "value": metrics.get("verified_like_count", 0)},
        {"label": "Review Needed", "value": metrics.get("review_needed_count", 0)},
        {"label": "Context Required", "value": metrics.get("context_required_count", 0)},
        {"label": "Table Rules", "value": metrics.get("table_derived_rules_count", 0)},
        {"label": "Dependencies", "value": metrics.get("dependency_total_count", 0)},
        {"label": "Verifier-ready Patches", "value": metrics.get("verifier_ready_patches_count", 0)},
        {"label": "Review Packets", "value": metrics.get("reviewer_packets_count", 0)},
        {"label": "False Verified", "value": metrics.get("false_verified_count", 0)},
    ]


def status_count_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    counts = (((data.get("comparison") or {}).get("m8_5") or {}).get("status_counts") or {})
    return [{"status": key, "count": value} for key, value in sorted(counts.items())]


def table_lineage_rows(data: dict[str, Any], limit: int = 300) -> list[dict[str, Any]]:
    rows = []
    for lineage in data.get("table_cell_lineage") or []:
        rows.append(
            {
                "lineage_id": lineage.get("lineage_id"),
                "table_id": lineage.get("table_id"),
                "page": lineage.get("page"),
                "section": lineage.get("section_id"),
                "row": lineage.get("row_label"),
                "column": lineage.get("column_label"),
                "cell_text": lineage.get("cell_text"),
                "value": lineage.get("normalized_value"),
                "unit": lineage.get("normalized_unit"),
                "rule_type": lineage.get("inferred_rule_type"),
                "verifier_ready": lineage.get("verifier_ready"),
                "warnings": ", ".join(lineage.get("parse_warnings") or []),
            }
        )
        if len(rows) >= limit:
            return rows
    return rows


def table_derived_rule_rows(data: dict[str, Any], limit: int = 300) -> list[dict[str, Any]]:
    rows = []
    for rule in data.get("table_derived_rules") or []:
        lineage = rule.get("lineage") or {}
        rows.append(
            {
                "rule_id": rule.get("rule_id"),
                "status": rule.get("status"),
                "rule_type": rule.get("rule_type"),
                "subject": rule.get("subject"),
                "operator": rule.get("comparator"),
                "value": rule.get("normalized_value"),
                "unit": rule.get("normalized_unit"),
                "row": lineage.get("row_label"),
                "column": lineage.get("column_label"),
                "verifier_ready": rule.get("verifier_ready"),
                "confidence": rule.get("confidence"),
            }
        )
        if len(rows) >= limit:
            return rows
    return rows


def dependency_graph_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    graph = data.get("dependency_graph") or {}
    for dependency in graph.get("dependencies") or []:
        rows.append(
            {
                "dependency_id": dependency.get("dependency_id"),
                "rule_id": dependency.get("source_rule_id"),
                "type": dependency.get("dependency_type"),
                "target": dependency.get("target_reference"),
                "status": dependency.get("status"),
                "blocking": dependency.get("is_blocking"),
                "evidence_ids": ", ".join(dependency.get("evidence_ids") or []),
                "reason": dependency.get("reason"),
                "reviewer_note": dependency.get("reviewer_note"),
            }
        )
    return sorted(rows, key=lambda row: (str(row.get("status") or ""), str(row.get("rule_id") or "")))


def repair_evaluation_rows(data: dict[str, Any], limit: int = 500) -> list[dict[str, Any]]:
    rows = []
    for evaluation in data.get("repair_evaluations") or []:
        rows.append(
            {
                "rule_id": evaluation.get("rule_id"),
                "category": evaluation.get("safety_category"),
                "verifier_ready": evaluation.get("verifier_ready"),
                "recommended_status": evaluation.get("recommended_status"),
                "changed_fields": ", ".join(evaluation.get("changed_fields") or []),
                "findings": ", ".join(evaluation.get("safety_findings") or []),
                "evidence_ids": ", ".join(evaluation.get("evidence_ids") or []),
                "original_failure": evaluation.get("original_failure"),
            }
        )
        if len(rows) >= limit:
            return rows
    return rows


def review_queue_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for packet in data.get("review_packets") or []:
        context = packet.get("dashboard_context") or {}
        row = {
            "rule_id": packet.get("rule_id"),
            "status": packet.get("current_status"),
            "priority": _review_priority(packet),
            "recommended_action": packet.get("recommended_reviewer_action"),
            "failure_reason": packet.get("failure_reason"),
            "evidence_count": context.get("evidence_count", len(packet.get("evidence_spans") or [])),
            "dependency_count": context.get("dependency_count", len(packet.get("dependency_graph_slice") or [])),
            "repair_evaluation_count": context.get("repair_evaluation_count", len(packet.get("repair_evaluations") or [])),
            "has_table_lineage": context.get("has_table_lineage", packet.get("table_lineage") is not None),
            "updated_at": packet.get("updated_at"),
        }
        rows.append(row)
    return sorted(rows, key=lambda row: (-int(row["priority"]), str(row.get("rule_id") or "")))


def comparison_metric_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    states = (((data.get("comparison") or {}).get("m8_5") or {}).get("metric_states") or {})
    return [
        {
            "metric": key,
            "state": value.get("state"),
            "value": value.get("value"),
            "source": value.get("source"),
            "note": value.get("note"),
        }
        for key, value in sorted(states.items())
    ]


def coverage_rows(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = (((data.get("comparison") or {}).get("m8_5") or {}).get(key) or [])
    return list(rows)


def _review_priority(packet: dict[str, Any]) -> int:
    action = str(packet.get("recommended_reviewer_action") or "")
    status = str(packet.get("current_status") or "")
    dependency_count = len(packet.get("dependency_graph_slice") or [])
    repair_ready = any(bool(item.get("verifier_ready")) for item in packet.get("repair_evaluations") or [])
    score = 0
    if action == "send_to_verifier" or repair_ready:
        score += 50
    if status == "context_required":
        score += 20
    if dependency_count:
        score += 10 + min(dependency_count, 5)
    if action == "mark_needs_legal_review":
        score += 5
    return score


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
