"""Artifact-backed M8.5 analyst chatbot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .grounded_answer_policy import UNSUPPORTED_RESPONSE, missing_response, refuses_legal_override
from .review_workflow_answers import reviewer_next_step, sorted_review_packets


REQUIRED_ARTIFACTS = {
    "summary": "m8_5_summary.json",
    "comparison": "m8_m8_5_comparison.json",
    "table_cell_lineage": "table_cell_lineage.json",
    "table_derived_rules": "table_derived_rules.json",
    "dependency_graph": "dependency_graph.json",
    "repair_evaluations": "repair_evaluations.json",
    "review_packets": "review_packets.json",
}


def load_m8_5_chatbot_context(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    context: dict[str, Any] = {"output_dir": str(output), "_missing_artifacts": []}
    for key, filename in REQUIRED_ARTIFACTS.items():
        path = output / filename
        if not path.exists():
            context[key] = [] if key not in {"summary", "comparison", "dependency_graph"} else {}
            context["_missing_artifacts"].append(filename)
            continue
        context[key] = json.loads(path.read_text(encoding="utf-8"))
    return context


def answer_m8_5_question(question: str, context: dict[str, Any]) -> str:
    if refuses_legal_override(question):
        return UNSUPPORTED_RESPONSE
    text = str(question or "").lower()
    if "false verified" in text or "safety" in text or "zero" in text:
        return _answer_safety(context)
    if "m8 " in text and "m8.5" in text or "changed from m8" in text or "distinguish" in text:
        return _answer_m8_vs_m8_5(context)
    if (
        "table lineage" in text
        or "table context" in text
        or "table cell" in text
        or "table-derived" in text
        or "row" in text and "column" in text
    ):
        return _answer_table_lineage(context)
    if "city has" in text and "unresolved" in text:
        return _answer_city_dependency_summary(context)
    if "unresolved depend" in text or "blocked by depend" in text:
        return _answer_unresolved_dependencies(context)
    if "resolved" in text and "depend" in text:
        return _answer_resolved_dependencies(context)
    if (
        "verifier-ready" in text
        or "verifier ready" in text
        or "ready_for_verifier" in text
        or "repair patch" in text
        or "repair evaluation" in text
    ):
        return _answer_verifier_ready_repairs(context)
    if (
        "human review" in text
        or "reviewer inspect" in text
        or "inspect next" in text
        or "reviewer action" in text
        or "recommended" in text and "reviewer" in text
    ):
        return _answer_reviewer_queue(context)
    if "review_needed" in text or "context_required" in text:
        return _answer_status_separation(context)
    if "rule type improved" in text:
        return _answer_rule_type_improvement(context)
    return UNSUPPORTED_RESPONSE


def _answer_safety(context: dict[str, Any]) -> str:
    if _missing(context, "summary", "comparison"):
        return missing_response("m8_5_summary.json", "m8_m8_5_comparison.json")
    comparison = context.get("comparison") or {}
    safety = (context.get("summary") or {}).get("safety") or comparison.get("safety") or {}
    false_verified = safety.get("false_verified_count", ((comparison.get("m8_5") or {}).get("false_verified_count")))
    false_approval = safety.get("false_approval_count", ((comparison.get("m8_5") or {}).get("false_approval_count")))
    preserved = bool(safety.get("m7_safety_preserved"))
    return (
        f"M8.5 summary reports false_verified_count = {false_verified} and "
        f"false_approval_count = {false_approval}. M7/M8 safety preserved: {preserved}."
    )


def _answer_m8_vs_m8_5(context: dict[str, Any]) -> str:
    if _missing(context, "comparison"):
        return missing_response("m8_m8_5_comparison.json")
    comparison = context.get("comparison") or {}
    m8 = comparison.get("m8") or {}
    m8_5 = comparison.get("m8_5") or {}
    return (
        "M8 measured the diagnostic baseline; M8.5 adds table lineage, dependency graph, "
        "repair evaluation, reviewer packets, and metric-state labeling. "
        f"M8 verified-like: {m8.get('verified_like_count')}. "
        f"M8.5 verified-like: {m8_5.get('verified_like_count')}. "
        f"M8.5 table-derived rules: {m8_5.get('table_derived_rules_count')}. "
        f"M8.5 dependencies: {m8_5.get('dependency_total_count')}."
    )


def _answer_table_lineage(context: dict[str, Any]) -> str:
    if _missing(context, "table_cell_lineage", "table_derived_rules"):
        return missing_response("table_cell_lineage.json", "table_derived_rules.json")
    rules = list(context.get("table_derived_rules") or [])
    if not rules:
        return "not available: no table-derived rules are present in the M8.5 artifacts."
    rule = rules[0]
    lineage = rule.get("lineage") or {}
    return (
        f"M8.5 has {len(rules)} table-derived candidate rules. Example `{rule.get('rule_id')}` "
        f"uses lineage `{lineage.get('lineage_id')}` from table `{lineage.get('table_id')}`, "
        f"row `{lineage.get('row_label')}`, column `{lineage.get('column_label')}`, "
        f"cell `{lineage.get('cell_text')}`. Status remains `{rule.get('status')}` until verifier review."
    )


def _answer_unresolved_dependencies(context: dict[str, Any]) -> str:
    if _missing(context, "dependency_graph"):
        return missing_response("dependency_graph.json")
    deps = [
        dep for dep in ((context.get("dependency_graph") or {}).get("dependencies") or [])
        if dep.get("status") == "unresolved"
    ]
    if not deps:
        return "M8.5 dependency graph has 0 unresolved dependencies in the loaded artifacts."
    first = deps[0]
    return (
        f"M8.5 dependency graph has {len(deps)} unresolved dependencies. "
        f"Example `{first.get('dependency_id')}` blocks rule `{first.get('source_rule_id')}` "
        f"as `{first.get('dependency_type')}` targeting `{first.get('target_reference')}`."
    )


def _answer_resolved_dependencies(context: dict[str, Any]) -> str:
    if _missing(context, "dependency_graph"):
        return missing_response("dependency_graph.json")
    deps = [
        dep for dep in ((context.get("dependency_graph") or {}).get("dependencies") or [])
        if dep.get("status") == "resolved"
    ]
    return f"M8.5 dependency graph reports {len(deps)} resolved dependencies in the loaded artifacts."


def _answer_verifier_ready_repairs(context: dict[str, Any]) -> str:
    if _missing(context, "repair_evaluations"):
        return missing_response("repair_evaluations.json")
    ready = [row for row in context.get("repair_evaluations") or [] if row.get("verifier_ready")]
    if not ready:
        return "M8.5 repair evaluations report 0 verifier-ready patches."
    ids = ", ".join(str(row.get("rule_id")) for row in ready[:5])
    return (
        f"M8.5 repair evaluations report {len(ready)} verifier-ready patches. "
        f"Examples: {ids}. These are `ready_for_verifier`, not verified."
    )


def _answer_reviewer_queue(context: dict[str, Any]) -> str:
    if _missing(context, "review_packets"):
        return missing_response("review_packets.json")
    packets = sorted_review_packets(context)
    if not packets:
        return "not available: no review packets are present in the M8.5 artifacts."
    return reviewer_next_step(packets[0])


def _answer_status_separation(context: dict[str, Any]) -> str:
    if _missing(context, "comparison"):
        return missing_response("m8_m8_5_comparison.json")
    m8_5 = (context.get("comparison") or {}).get("m8_5") or {}
    return (
        f"M8.5 keeps review_needed and context_required separate: "
        f"review_needed = {m8_5.get('review_needed_count')}, "
        f"context_required = {m8_5.get('context_required_count')}. "
        "Neither status is verified."
    )


def _answer_rule_type_improvement(context: dict[str, Any]) -> str:
    if _missing(context, "comparison"):
        return missing_response("m8_m8_5_comparison.json")
    rows = ((context.get("comparison") or {}).get("m8_5") or {}).get("coverage_by_rule_type") or []
    if not rows:
        return "not available: rule-type coverage is missing from comparison artifacts."
    strongest = sorted(rows, key=lambda row: (row.get("coverage", 0), row.get("verified_like", 0)), reverse=True)[0]
    return (
        f"Highest current M8.5 rule-type coverage is `{strongest.get('rule_type')}` "
        f"with {strongest.get('verified_like')}/{strongest.get('total')} verified-like."
    )


def _answer_city_dependency_summary(context: dict[str, Any]) -> str:
    if _missing(context, "summary", "comparison"):
        return missing_response("m8_5_summary.json", "m8_m8_5_comparison.json")
    city = (context.get("summary") or {}).get("city") or (context.get("comparison") or {}).get("city")
    count = ((context.get("comparison") or {}).get("m8_5") or {}).get("dependency_unresolved_count")
    return f"Loaded M8.5 artifacts cover city `{city}` with unresolved dependency count {count}."


def _missing(context: dict[str, Any], *keys: str) -> bool:
    missing_files = set(context.get("_missing_artifacts") or [])
    return any(REQUIRED_ARTIFACTS[key] in missing_files for key in keys)
