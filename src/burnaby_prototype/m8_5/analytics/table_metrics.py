"""M8.5 table lineage metrics."""

from __future__ import annotations

from collections import Counter
from typing import Any


def table_metrics(table_blocks: list[Any], table_derived_rules: list[Any]) -> dict[str, Any]:
    diagnostics = Counter()
    cell_count = 0
    for block in table_blocks:
        cells = _field(block, "cells") or []
        cell_count += len(cells)
        for diagnostic in _field(block, "diagnostics") or []:
            diagnostics[_field(diagnostic, "code") or "unknown"] += 1
    status_counts = Counter(_field(rule, "status") or "unknown" for rule in table_derived_rules)
    verified_count = sum(1 for rule in table_derived_rules if (_field(rule, "status") or "") in {"verified", "repaired_successfully"})
    review_count = len(table_derived_rules) - verified_count
    return {
        "table_block_count": len(table_blocks),
        "table_cell_count": cell_count,
        "table_derived_rules_count": len(table_derived_rules),
        "table_derived_verified_count": verified_count,
        "table_derived_review_count": review_count,
        "table_derived_verifier_ready_count": sum(1 for rule in table_derived_rules if bool(_field(rule, "verifier_ready"))),
        "table_derived_status_counts": dict(sorted(status_counts.items())),
        "table_diagnostic_counts": dict(sorted(diagnostics.items())),
    }


def _field(row: Any, name: str) -> Any:
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)
