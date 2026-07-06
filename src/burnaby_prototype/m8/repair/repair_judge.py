"""Classify why a candidate needs repair."""

from __future__ import annotations

from typing import Any

from ..extraction.rule_schema import RepairCritique


GAP_TO_CATEGORY = {
    "source_evidence_id_not_found": "missing_evidence",
    "value_not_found_in_evidence": "weak_evidence",
    "unit_not_found_in_evidence": "unit_mismatch",
    "applies_to_not_supported": "missing_scope",
    "constraint_scope_not_supported": "missing_scope",
    "text_condition_not_supported": "missing_condition",
    "conditional_cell_condition_missing": "missing_condition",
    "unresolved_exception_cue": "missing_exception",
    "column_value_mismatch": "conflicting_evidence",
    "table_operator_refuted": "conflicting_evidence",
    "cross_reference_only": "unresolved_cross_reference",
    "outside_current_rule_contract": "unsupported_rule_type",
    "definition_not_rule": "unsupported_rule_type",
}


def judge_repair(rule: dict[str, Any]) -> RepairCritique:
    gaps = [str(gap) for gap in (rule.get("support_gaps") or [])]
    category = "general_review"
    for gap in gaps:
        if gap in GAP_TO_CATEGORY:
            category = GAP_TO_CATEGORY[gap]
            break
    fields = _fields_for_category(category)
    reason = str(rule.get("review_reason") or rule.get("blocking_reason") or ", ".join(gaps) or "review needed")
    return RepairCritique(
        rule_id=str(rule.get("rule_id") or rule.get("candidate_id") or ""),
        category=category,
        reason=reason,
        fields=tuple(fields),
        severity="high" if category in {"conflicting_evidence", "unsupported_rule_type"} else "medium",
        support_gaps=tuple(gaps),
    )


def _fields_for_category(category: str) -> list[str]:
    if category == "missing_evidence":
        return ["evidence_id"]
    if category == "weak_evidence":
        return ["evidence_text"]
    if category == "unit_mismatch":
        return ["unit"]
    if category == "missing_scope":
        return ["constraint_scope", "applies_to"]
    if category == "missing_condition":
        return ["condition"]
    if category == "missing_exception":
        return ["exception"]
    return []
