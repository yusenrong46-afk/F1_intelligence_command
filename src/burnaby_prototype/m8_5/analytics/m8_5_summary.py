"""Shared M8.5 summary metrics."""

from __future__ import annotations

from collections import Counter
from typing import Any


VERIFIED_LIKE_STATUSES = frozenset({"verified", "repaired_successfully"})


def status_metrics(decisions: list[Any]) -> dict[str, Any]:
    counts = Counter(_field(row, "status") for row in decisions)
    counts.pop("", None)
    return {
        "status_counts": dict(sorted(counts.items())),
        "verified_count": counts.get("verified", 0),
        "repaired_successfully_count": counts.get("repaired_successfully", 0),
        "verified_like_count": counts.get("verified", 0) + counts.get("repaired_successfully", 0),
        "review_needed_count": counts.get("review_needed", 0),
        "context_required_count": counts.get("context_required", 0),
        "rejected_count": counts.get("rejected", 0),
        "not_used_count": counts.get("not_used", 0),
    }


def coverage_by_rule_type(rules: list[Any], *, decisions_by_rule: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    totals: Counter[str] = Counter()
    verified: Counter[str] = Counter()
    decisions_by_rule = decisions_by_rule or {}
    for rule in rules:
        rule_type = _field(rule, "rule_type") or _field(rule, "rule_object") or "unknown"
        rule_id = _field(rule, "rule_id") or _field(rule, "candidate_id")
        status = _status_for_rule(rule, decisions_by_rule.get(rule_id))
        totals[rule_type] += 1
        if status in VERIFIED_LIKE_STATUSES:
            verified[rule_type] += 1
    return [
        {
            "rule_type": rule_type,
            "total": total,
            "verified_like": verified.get(rule_type, 0),
            "coverage": round(verified.get(rule_type, 0) / total, 4) if total else 0.0,
        }
        for rule_type, total in sorted(totals.items())
    ]


def coverage_by_source_type(rules: list[Any], *, decisions_by_rule: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    totals: Counter[str] = Counter()
    verified: Counter[str] = Counter()
    decisions_by_rule = decisions_by_rule or {}
    for rule in rules:
        source_type = _source_type(rule)
        rule_id = _field(rule, "rule_id") or _field(rule, "candidate_id")
        status = _status_for_rule(rule, decisions_by_rule.get(rule_id))
        totals[source_type] += 1
        if status in VERIFIED_LIKE_STATUSES:
            verified[source_type] += 1
    return [
        {
            "source_type": source_type,
            "total": total,
            "verified_like": verified.get(source_type, 0),
            "coverage": round(verified.get(source_type, 0) / total, 4) if total else 0.0,
        }
        for source_type, total in sorted(totals.items())
    ]


def metric_state(value: Any, *, state: str = "measured", source: str = "", note: str = "") -> dict[str, Any]:
    if state not in {"measured", "target", "not_yet_run"}:
        raise ValueError(f"unknown metric state: {state}")
    return {
        "state": state,
        "value": value,
        "source": source,
        "note": note,
    }


def _status_for_rule(rule: Any, decision: Any | None) -> str:
    if decision is not None:
        return _field(decision, "status")
    return _field(rule, "status") or _field(rule, "verification_decision")


def _source_type(rule: Any) -> str:
    lineage = _field(rule, "lineage")
    if lineage:
        return "table"
    table_lineage = _field(rule, "table_lineage")
    if table_lineage:
        return "table"
    pointers = _field(rule, "evidence_pointers") or []
    for pointer in pointers:
        span = _field(pointer, "source_span")
        block_type = _field(span, "block_type")
        if block_type:
            return "table" if "table" in block_type else "prose"
    raw = _field(rule, "raw") or {}
    evidence_type = _field(raw, "evidence_type") or _field(raw, "source_type")
    if evidence_type:
        return "table" if "table" in str(evidence_type).lower() else "prose"
    return "unknown"


def _field(row: Any, name: str) -> Any:
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)
