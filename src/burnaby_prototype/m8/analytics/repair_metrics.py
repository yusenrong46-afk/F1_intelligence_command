"""Repair metrics for M8 attempts."""

from __future__ import annotations

from collections import Counter

from ..extraction.rule_schema import RepairAttempt


def repair_metrics(attempts: list[RepairAttempt]) -> dict[str, object]:
    categories = Counter(attempt.critique.category for attempt in attempts)
    statuses = Counter(attempt.decision_status for attempt in attempts)
    success = statuses.get("repaired_successfully", 0) + statuses.get("verified", 0)
    return {
        "attempt_count": len(attempts),
        "success_count": success,
        "success_rate": round(success / len(attempts), 4) if attempts else 0.0,
        "failure_count": len(attempts) - success,
        "categories": dict(sorted(categories.items())),
        "decision_statuses": dict(sorted(statuses.items())),
    }
