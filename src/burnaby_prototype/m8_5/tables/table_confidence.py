"""Confidence helpers for M8.5 table lineage.

Confidence is advisory only. It can help prioritize review, but it cannot mark a
rule verified or bypass deterministic verification.
"""

from __future__ import annotations


def lineage_confidence(*, has_row_label: bool, has_column_label: bool, has_value: bool, warning_count: int = 0) -> float:
    score = 1.0
    if not has_row_label:
        score -= 0.35
    if not has_column_label:
        score -= 0.25
    if not has_value:
        score -= 0.35
    score -= min(max(warning_count, 0), 5) * 0.05
    return round(max(0.0, min(1.0, score)), 4)

