"""Patch safety checker for M8.5 repair evaluation."""

from __future__ import annotations

import re
from typing import Any

from burnaby_prototype.m8.extraction.rule_schema import SourceSpan


PATCH_SAFETY_CATEGORIES = frozenset(
    {
        "safe_for_verifier",
        "needs_human_review",
        "insufficient_evidence",
        "contradictory_evidence",
        "introduced_dependency",
        "unsafe_field_change",
        "unsupported_patch",
    }
)

CHECKED_FIELDS = (
    "rule_object",
    "constraint_scope",
    "applies_to",
    "operator",
    "value",
    "unit",
    "condition",
    "exception",
    "evidence_id",
    "zone",
)


class PatchSafetyChecker:
    def check(
        self,
        *,
        original_rule: dict[str, Any],
        patched_rule: dict[str, Any],
        evidence_by_id: dict[str, SourceSpan],
    ) -> dict[str, Any]:
        changed_fields = changed_patch_fields(original_rule, patched_rule)
        findings: list[str] = []
        evidence_id = str(patched_rule.get("evidence_id") or "")
        evidence = evidence_by_id.get(evidence_id) if evidence_id else None

        if changed_fields and evidence is None and any(field in changed_fields for field in ("value", "unit", "applies_to", "constraint_scope")):
            findings.append("missing_patch_evidence")

        if evidence is not None:
            findings.extend(_field_support_findings(changed_fields, patched_rule, evidence))
            findings.extend(_scope_findings(patched_rule, evidence))
            if _evidence_contradicts_patch(patched_rule, evidence):
                findings.append("contradictory_evidence")

        if _introduces_exception(original_rule, patched_rule):
            findings.append("exception_dependency_introduced")

        if _removes_exception(original_rule, patched_rule):
            findings.append("unsafe_exception_removal")

        if patched_rule.get("table_lineage"):
            findings.append("table_lineage_present")

        category = _category_for_findings(findings, changed_fields)
        return {
            "changed_fields": tuple(changed_fields),
            "safety_findings": tuple(sorted(set(findings))),
            "safety_category": category,
        }


def changed_patch_fields(original_rule: dict[str, Any], patched_rule: dict[str, Any]) -> tuple[str, ...]:
    changed = []
    for field in CHECKED_FIELDS:
        if _norm(original_rule.get(field)) != _norm(patched_rule.get(field)):
            changed.append(field)
    return tuple(changed)


def _field_support_findings(changed_fields: tuple[str, ...], patched_rule: dict[str, Any], evidence: SourceSpan) -> list[str]:
    findings = []
    text = evidence.text.lower()
    if "value" in changed_fields:
        value = str(patched_rule.get("value") or "").lower()
        if value and value not in text:
            findings.append("changed_value_not_in_evidence")
    if "unit" in changed_fields:
        unit = str(patched_rule.get("unit") or "").lower()
        if unit and unit not in text and _unit_alias(unit) not in text:
            findings.append("changed_unit_not_in_evidence")
    return findings


def _scope_findings(patched_rule: dict[str, Any], evidence: SourceSpan) -> list[str]:
    zone = str(patched_rule.get("zone") or "").strip().lower()
    if not zone:
        return []
    span_zone = str((evidence.metadata or {}).get("zone") or "").strip().lower()
    text = evidence.text.lower()
    if span_zone and span_zone != zone:
        return ["zone_scope_mismatch"]
    if span_zone:
        return []
    if zone not in text and "table_lineage" not in patched_rule:
        return ["zone_scope_mismatch"]
    return []


def _evidence_contradicts_patch(patched_rule: dict[str, Any], evidence: SourceSpan) -> bool:
    value = str(patched_rule.get("value") or "").strip()
    if not value:
        return False
    return re.search(rf"\bnot\b.{{0,40}}\b{re.escape(value.lower())}\b", evidence.text.lower()) is not None


def _introduces_exception(original_rule: dict[str, Any], patched_rule: dict[str, Any]) -> bool:
    return not str(original_rule.get("exception") or "").strip() and bool(str(patched_rule.get("exception") or "").strip())


def _removes_exception(original_rule: dict[str, Any], patched_rule: dict[str, Any]) -> bool:
    return bool(str(original_rule.get("exception") or "").strip()) and not str(patched_rule.get("exception") or "").strip()


def _category_for_findings(findings: list[str], changed_fields: tuple[str, ...]) -> str:
    finding_set = set(findings)
    if "contradictory_evidence" in finding_set:
        return "contradictory_evidence"
    if "unsafe_exception_removal" in finding_set:
        return "unsafe_field_change"
    if "exception_dependency_introduced" in finding_set:
        return "introduced_dependency"
    if "zone_scope_mismatch" in finding_set:
        return "unsupported_patch"
    if {"missing_patch_evidence", "changed_value_not_in_evidence", "changed_unit_not_in_evidence"} & finding_set:
        return "insufficient_evidence"
    if changed_fields:
        return "safe_for_verifier"
    return "needs_human_review"


def _unit_alias(unit: str) -> str:
    aliases = {"m2": "m²", "m²": "m2", "percent": "%"}
    return aliases.get(unit.lower(), unit.lower())


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())

