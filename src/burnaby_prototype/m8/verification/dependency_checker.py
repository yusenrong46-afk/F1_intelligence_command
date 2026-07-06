"""Dependency-aware checks layered above M7."""

from __future__ import annotations

import re
from typing import Any

from ..extraction.definition_extractor import definition_dependencies
from ..extraction.exception_extractor import exception_dependencies
from ..extraction.rule_schema import SourceSpan, StructuredRule


DEPENDENCY_WORDS = {
    "overlay": "overlay_dependency",
    "heritage": "heritage_dependency",
    "covenant": "covenant_dependency",
    "section 219": "covenant_dependency",
    "subject to": "cross_reference_dependency",
    "except": "exception_or_override_dependency",
    "unless": "exception_or_override_dependency",
    "notwithstanding": "exception_or_override_dependency",
}


def dependency_report(rule: StructuredRule, spans: list[SourceSpan] | None = None) -> dict[str, Any]:
    text = " ".join(
        [
            " ".join(rule.conditions),
            " ".join(rule.exceptions),
            str(rule.raw.get("rule_sentence") or ""),
            " ".join(str(gap) for gap in rule.raw.get("support_gaps", []) or []),
        ]
    ).lower()
    dependencies = set(rule.dependencies)
    for cue, name in DEPENDENCY_WORDS.items():
        if cue in text:
            dependencies.add(name)
    dependencies.update(definition_dependencies(rule.raw))
    dependencies.update(exception_dependencies(rule.raw))
    gap_dependencies = {
        "unresolved_exception_cue": "exception_or_override_dependency",
        "cross_reference_only": "cross_reference_dependency",
        "text_condition_not_supported": "condition_dependency",
        "conditional_cell_condition_missing": "condition_dependency",
        "enumerated_branch_condition_missing": "condition_dependency",
    }
    for gap in rule.raw.get("support_gaps", []) or []:
        if str(gap) in gap_dependencies:
            dependencies.add(gap_dependencies[str(gap)])
    conflicts = _conflicts(rule, spans or [])
    return {
        "unresolved_dependencies": sorted(dependencies),
        "conflicting_source_spans": conflicts,
        "has_unresolved_dependencies": bool(dependencies),
        "has_conflicts": bool(conflicts),
    }


def field_support_report(rule: StructuredRule, spans: list[SourceSpan]) -> dict[str, bool]:
    text = " ".join(span.text for span in spans).lower()
    value = str(rule.value or "").lower()
    unit = str(rule.unit or "").lower()
    comparator = str(rule.comparator or "")
    same_city_scope = any(span.city == rule.city for span in spans)
    return {
        "has_evidence": bool(spans),
        "value_visible": not value or value in text,
        "unit_visible": not unit or unit in text or _unit_alias(unit) in text,
        "comparator_valid": comparator in {"", "<", "<=", "=", ">=", ">", "allowed", "not permitted", "required"},
        "zone_scope_visible": same_city_scope or not rule.zone or rule.zone.lower() in text or rule.city.lower().split("_")[0] in text,
    }


def _unit_alias(unit: str) -> str:
    aliases = {"m2": "m²", "m²": "m2", "percent": "%"}
    return aliases.get(unit.lower(), unit.lower())


def _conflicts(rule: StructuredRule, spans: list[SourceSpan]) -> list[str]:
    if rule.value in (None, ""):
        return []
    value = re.escape(str(rule.value))
    opposite = []
    for span in spans:
        text = span.text.lower()
        if re.search(rf"\bnot\b.{0,40}\b{value}\b", text):
            opposite.append(span.span_id)
    return opposite
