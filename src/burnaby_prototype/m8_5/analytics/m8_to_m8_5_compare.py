"""Compare M8 and M8.5 artifact metrics."""

from __future__ import annotations

from typing import Any

from .dependency_metrics import dependency_metrics
from .m8_5_summary import coverage_by_rule_type, coverage_by_source_type, metric_state, status_metrics
from .repair_quality_metrics import repair_quality_metrics
from .table_metrics import table_metrics


def compare_m8_to_m8_5(
    *,
    city: str,
    m8_comparison: dict[str, Any],
    m8_summary: dict[str, Any],
    m8_5_decisions: list[dict[str, Any]],
    table_blocks: list[Any],
    table_derived_rules: list[Any],
    dependency_graph: Any,
    repair_evaluations: list[Any],
    review_packets: list[Any],
    structured_rules: list[Any] | None = None,
) -> dict[str, Any]:
    m8 = dict(m8_comparison.get("m8") or m8_summary.get("m8_metrics") or {})
    status = status_metrics(m8_5_decisions)
    table = table_metrics(table_blocks, table_derived_rules)
    dependencies = dependency_metrics(dependency_graph)
    repair = repair_quality_metrics(repair_evaluations)
    decisions_by_rule = {str(row.get("rule_id") or ""): row for row in m8_5_decisions}
    rules = list(structured_rules or [])
    m8_5 = {
        **status,
        "false_verified_count": int(m8.get("false_verified_count", 0) or 0),
        "false_approval_count": int(m8.get("false_approval_count", 0) or 0),
        **table,
        **dependencies,
        **repair,
        "reviewer_packets_count": len(review_packets),
        "human_review_required_count": len(review_packets),
        "coverage_by_rule_type": coverage_by_rule_type(rules, decisions_by_rule=decisions_by_rule) if rules else [],
        "coverage_by_city": [
            {
                "city": city,
                "total_rules": len(rules),
                "verified_like": status["verified_like_count"],
                "review_needed": status["review_needed_count"],
                "context_required": status["context_required_count"],
                "false_verified_count": int(m8.get("false_verified_count", 0) or 0),
            }
        ],
        "coverage_by_dependency_type": dependencies["dependency_type_metrics"],
        "coverage_by_table_vs_prose_source": coverage_by_source_type([*rules, *list(table_derived_rules)], decisions_by_rule=decisions_by_rule),
        "metric_states": _metric_states(
            m8=m8,
            status=status,
            table=table,
            dependencies=dependencies,
            repair=repair,
            review_packets=review_packets,
        ),
        "measured_scope": "m8_5_pipeline_artifacts_only",
    }
    return {
        "city": city,
        "m8": m8,
        "m8_5": m8_5,
        "safety": {
            "m7_safety_preserved": bool((m8_comparison.get("safety") or {}).get("m7_safety_preserved", True)),
            "repair_can_promote_directly": False,
            "reviewer_can_promote_directly": False,
            "gis_verified_only_preserved": True,
            "false_verified_count": m8_5["false_verified_count"],
            "false_approval_count": m8_5["false_approval_count"],
        },
    }


def _metric_states(
    *,
    m8: dict[str, Any],
    status: dict[str, Any],
    table: dict[str, Any],
    dependencies: dict[str, Any],
    repair: dict[str, Any],
    review_packets: list[Any],
) -> dict[str, dict[str, Any]]:
    return {
        "m8_verified_like_count": metric_state(m8.get("verified_like_count"), source="m8_summary.json"),
        "m8_5_verified_like_count": metric_state(status["verified_like_count"], source="m8_5_verification_decisions.json"),
        "false_verified_count": metric_state(m8.get("false_verified_count", 0), source="m8_m8_5_comparison.json"),
        "false_approval_count": metric_state(m8.get("false_approval_count", 0), source="m8_m8_5_comparison.json"),
        "table_derived_rules_count": metric_state(table["table_derived_rules_count"], source="table_derived_rules.json"),
        "dependency_total_count": metric_state(dependencies["dependency_total_count"], source="dependency_graph.json"),
        "repair_evaluations_count": metric_state(repair["repair_evaluations_count"], source="repair_evaluations.json"),
        "reviewer_packets_count": metric_state(len(review_packets), source="review_packets.json"),
        "m8_5_chatbot_gold": metric_state(None, state="not_yet_run", source="", note="Checkpoint 9 not implemented"),
        "m8_5_multi_city_stress": metric_state(None, state="not_yet_run", source="", note="Checkpoint 10 not implemented"),
    }
