"""Convert repair critiques into retrieval queries."""

from __future__ import annotations

from typing import Any

from ..extraction.rule_schema import RepairCritique


def plan_repair_query(rule: dict[str, Any], critique: RepairCritique) -> str:
    parts = [
        rule.get("rule_object"),
        rule.get("constraint_scope"),
        rule.get("applies_to"),
        rule.get("operator"),
        rule.get("value"),
        rule.get("unit"),
        rule.get("condition"),
    ]
    query = " ".join(str(part) for part in parts if part not in (None, ""))
    if critique.category == "missing_exception":
        query += " exception unless subject to"
    elif critique.category == "missing_scope":
        query += " applies to scope"
    elif critique.category == "unit_mismatch":
        query += " unit"
    query = " ".join(query.split())
    if not query:
        query = f"{critique.category} {critique.rule_id}".strip()
    return query
