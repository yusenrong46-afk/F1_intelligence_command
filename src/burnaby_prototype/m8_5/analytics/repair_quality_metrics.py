"""M8.5 repair quality metrics."""

from __future__ import annotations

from collections import Counter
from typing import Any


def repair_quality_metrics(evaluations: list[Any]) -> dict[str, Any]:
    category_counts = Counter(_field(evaluation, "safety_category") or "unknown" for evaluation in evaluations)
    recommended_status_counts = Counter(_field(evaluation, "recommended_status") or "unknown" for evaluation in evaluations)
    verifier_ready_count = sum(1 for evaluation in evaluations if bool(_field(evaluation, "verifier_ready")))
    direct_promotion_count = sum(1 for evaluation in evaluations if bool(_field(evaluation, "promotes_directly")))
    return {
        "repair_evaluations_count": len(evaluations),
        "verifier_ready_patches_count": verifier_ready_count,
        "human_review_required_count": len(evaluations) - verifier_ready_count,
        "direct_promotion_count": direct_promotion_count,
        "repair_safety_category_counts": dict(sorted(category_counts.items())),
        "repair_recommended_status_counts": dict(sorted(recommended_status_counts.items())),
        "repair_scorecard": {
            "evaluation_count": len(evaluations),
            "verifier_ready_count": verifier_ready_count,
            "human_review_required_count": len(evaluations) - verifier_ready_count,
            "direct_promotion_count": direct_promotion_count,
            "category_counts": dict(sorted(category_counts.items())),
            "recommended_status_counts": dict(sorted(recommended_status_counts.items())),
        },
    }


def _field(row: Any, name: str) -> Any:
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)
