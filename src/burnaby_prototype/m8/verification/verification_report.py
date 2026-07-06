"""M8 verification report helpers."""

from __future__ import annotations

from collections import Counter

from ..extraction.rule_schema import VerificationDecision


def summarize_decisions(decisions: list[VerificationDecision]) -> dict[str, object]:
    counts = Counter(decision.status for decision in decisions)
    dependency_counts = Counter(dep for decision in decisions for dep in decision.unresolved_dependencies)
    return {
        "status_counts": dict(sorted(counts.items())),
        "decision_count": len(decisions),
        "unresolved_dependency_counts": dict(sorted(dependency_counts.items())),
        "repaired_successfully_count": counts.get("repaired_successfully", 0),
        "verified_like_count": counts.get("verified", 0) + counts.get("repaired_successfully", 0),
    }
