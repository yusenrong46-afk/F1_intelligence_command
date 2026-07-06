"""Citation helpers for M8 chatbot answers."""

from __future__ import annotations

from typing import Any


def citation_for_rule(rule: dict[str, Any]) -> str:
    pointers = rule.get("evidence_pointers") or []
    if not pointers:
        raw = rule.get("raw") or {}
        evidence_id = raw.get("evidence_id") or (raw.get("candidate") or {}).get("evidence_id")
        return f"evidence `{evidence_id}`" if evidence_id else "no cited evidence"
    first = pointers[0]
    evidence_id = first.get("evidence_id")
    span = first.get("source_span") or {}
    page = span.get("page")
    section = span.get("section_id")
    suffix = []
    if page is not None:
        suffix.append(f"page {page}")
    if section:
        suffix.append(f"section {section}")
    location = ", ".join(suffix)
    return f"evidence `{evidence_id}`" + (f" ({location})" if location else "")


def citations_for_rules(rules: list[dict[str, Any]], limit: int = 3) -> list[str]:
    return [citation_for_rule(rule) for rule in rules[:limit]]
