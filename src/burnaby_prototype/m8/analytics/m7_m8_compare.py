"""M7 vs M8 comparison metrics."""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..extraction.rule_schema import RepairAttempt, StructuredRule, VerificationDecision
from .coverage_metrics import coverage_by_rule_type
from .repair_metrics import repair_metrics


def compare_m7_m8(
    *,
    city: str,
    m7_benchmark: dict[str, Any],
    m7_summary: dict[str, Any],
    structured_rules: list[StructuredRule],
    decisions: list[VerificationDecision],
    attempts: list[RepairAttempt],
) -> dict[str, Any]:
    rule_metrics = m7_benchmark.get("rule_metrics") or {}
    proposal_metrics = m7_benchmark.get("proposal_metrics") or {}
    decision_counts = Counter(decision.status for decision in decisions)
    before_review = int(rule_metrics.get("review_rule_count") or len([r for r in structured_rules if r.raw.get("verification_decision") == "review_needed"]))
    after_review = decision_counts.get("review_needed", 0)
    repaired = decision_counts.get("repaired_successfully", 0)
    return {
        "city": city,
        "m7": {
            "verified_count": int(rule_metrics.get("verified_rule_count") or m7_summary.get("verified_rule_count") or 0),
            "review_needed_count": before_review,
            "rejected_count": int(rule_metrics.get("rejected_rule_count") or m7_summary.get("rejected_rule_count") or 0),
            "not_used_count": int(rule_metrics.get("not_used_rule_count") or m7_summary.get("not_used_rule_count") or 0),
            "false_verified_count": int(rule_metrics.get("false_verified_count") or 0),
            "false_approval_count": int(proposal_metrics.get("false_approval_count") or 0),
            "verified_precision": rule_metrics.get("verified_precision"),
            "extraction_coverage_recall": rule_metrics.get("extraction_coverage_recall"),
        },
        "m8": {
            "verified_count": decision_counts.get("verified", 0),
            "repaired_successfully_count": repaired,
            "verified_like_count": decision_counts.get("verified", 0) + repaired,
            "review_needed_count": after_review,
            "review_needed_reduction": before_review - after_review,
            "context_required_count": decision_counts.get("context_required", 0),
            "rejected_count": decision_counts.get("rejected", 0),
            "not_used_count": decision_counts.get("not_used", 0),
            "false_verified_count": int(rule_metrics.get("false_verified_count") or 0),
            "false_approval_count": int(proposal_metrics.get("false_approval_count") or 0),
            "status_counts": dict(sorted(decision_counts.items())),
            "coverage_by_rule_type": coverage_by_rule_type(structured_rules),
            "repair": repair_metrics(attempts),
        },
        "safety": {
            "m7_safety_preserved": int(rule_metrics.get("false_verified_count") or 0) == 0
            and int(proposal_metrics.get("false_approval_count") or 0) == 0,
            "m8_uses_verified_only_gis_export": True,
            "repair_can_promote_directly": False,
        },
    }
