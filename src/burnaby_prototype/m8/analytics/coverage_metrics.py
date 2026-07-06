"""Coverage metrics for M8 rules."""

from __future__ import annotations

from collections import Counter

from ..extraction.rule_schema import StructuredRule


def coverage_by_rule_type(rules: list[StructuredRule]) -> list[dict[str, object]]:
    counts = Counter(rule.rule_type or "unknown" for rule in rules)
    verified = Counter(
        rule.rule_type or "unknown"
        for rule in rules
        if rule.status in {"verified", "repaired_successfully"}
    )
    return [
        {
            "rule_type": rule_type,
            "total": total,
            "verified_like": verified.get(rule_type, 0),
            "coverage": round(verified.get(rule_type, 0) / total, 4) if total else 0.0,
        }
        for rule_type, total in sorted(counts.items())
    ]
