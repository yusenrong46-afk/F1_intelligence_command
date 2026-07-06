"""Aggregate M8.5 repair evaluations."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .repair_evaluation import RepairEvaluation


def build_repair_scorecard(evaluations: list[RepairEvaluation]) -> dict[str, Any]:
    category_counts = Counter(evaluation.safety_category for evaluation in evaluations)
    recommended_status_counts = Counter(evaluation.recommended_status for evaluation in evaluations)
    return {
        "evaluation_count": len(evaluations),
        "verifier_ready_count": sum(1 for evaluation in evaluations if evaluation.verifier_ready),
        "human_review_required_count": sum(1 for evaluation in evaluations if not evaluation.verifier_ready),
        "direct_promotion_count": sum(1 for evaluation in evaluations if evaluation.promotes_directly),
        "category_counts": dict(sorted(category_counts.items())),
        "recommended_status_counts": dict(sorted(recommended_status_counts.items())),
    }

