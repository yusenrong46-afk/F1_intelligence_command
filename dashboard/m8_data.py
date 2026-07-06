"""Pure data providers for M8 dashboard pages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_m8_output(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    return {
        "summary": _read_json(output / "m8_summary.json", {}),
        "comparison": _read_json(output / "m7_m8_comparison.json", {}),
        "rules": _read_json(output / "structured_rules.json", []),
        "decisions": _read_json(output / "verification_decisions.json", []),
        "repair_attempts": _read_json(output / "repair_attempts.json", []),
        "evidence_bundles": _read_json(output / "evidence_bundles.json", []),
    }


def m8_metric_cards(data: dict[str, Any]) -> list[dict[str, Any]]:
    m8 = ((data.get("comparison") or {}).get("m8") or {})
    return [
        {"label": "Verified", "value": m8.get("verified_count", 0)},
        {"label": "Repaired", "value": m8.get("repaired_successfully_count", 0)},
        {"label": "Review Needed", "value": m8.get("review_needed_count", 0)},
        {"label": "Context Required", "value": m8.get("context_required_count", 0)},
        {"label": "Rejected", "value": m8.get("rejected_count", 0)},
        {"label": "False Verified", "value": m8.get("false_verified_count", 0)},
    ]


def repair_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for attempt in data.get("repair_attempts") or []:
        critique = attempt.get("critique") or {}
        rows.append(
            {
                "rule_id": critique.get("rule_id"),
                "category": critique.get("category"),
                "decision_status": attempt.get("decision_status"),
                "query": attempt.get("query"),
                "reason": attempt.get("reason"),
            }
        )
    return rows


def rule_explorer_rows(data: dict[str, Any], *, status: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for rule in data.get("rules") or []:
        if status and rule.get("status") != status:
            continue
        pointers = rule.get("evidence_pointers") or []
        rows.append(
            {
                "rule_id": rule.get("rule_id"),
                "status": rule.get("status"),
                "rule_type": rule.get("rule_type"),
                "subject": rule.get("subject"),
                "value": rule.get("value"),
                "unit": rule.get("unit"),
                "evidence_id": (pointers[0] or {}).get("evidence_id") if pointers else "",
            }
        )
    return rows


def weakest_coverage_rows(data: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    rows = (((data.get("comparison") or {}).get("m8") or {}).get("coverage_by_rule_type") or [])
    return sorted(rows, key=lambda row: (row.get("coverage", 0), -row.get("total", 0)))[:limit]


def unresolved_dependency_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    decisions_by_rule = {row.get("rule_id"): row for row in data.get("decisions") or []}
    for rule in data.get("rules") or []:
        decision = decisions_by_rule.get(rule.get("rule_id")) or {}
        for dependency in decision.get("unresolved_dependencies") or []:
            rows.append(
                {
                    "rule_id": rule.get("rule_id"),
                    "status": rule.get("status"),
                    "rule_type": rule.get("rule_type"),
                    "dependency": dependency,
                }
            )
    return rows


def evidence_span_rows(data: dict[str, Any], limit: int = 200) -> list[dict[str, Any]]:
    rows = []
    for rule in data.get("rules") or []:
        for pointer in rule.get("evidence_pointers") or []:
            span = pointer.get("source_span") or {}
            rows.append(
                {
                    "rule_id": rule.get("rule_id"),
                    "status": rule.get("status"),
                    "evidence_id": pointer.get("evidence_id"),
                    "page": span.get("page"),
                    "section": span.get("section_id"),
                    "quote": (pointer.get("quote") or span.get("text") or "")[:220],
                }
            )
            if len(rows) >= limit:
                return rows
    return rows


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
