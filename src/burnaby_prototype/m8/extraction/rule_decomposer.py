"""Deterministic conversion from M7 rows to M8 structured rules."""

from __future__ import annotations

from typing import Any

from .rule_schema import EvidencePointer, SourceSpan, StructuredRule, structured_rule_from_m7


def evidence_pointer_for_rule(rule: dict[str, Any], span: SourceSpan | None) -> EvidencePointer | None:
    evidence_id = str(rule.get("evidence_id") or (rule.get("candidate") or {}).get("evidence_id") or "")
    if not evidence_id or span is None:
        return None
    quote = str((rule.get("source") or {}).get("evidence_quote") or rule.get("evidence_quote") or span.text)
    return EvidencePointer(
        evidence_id=evidence_id,
        span_id=span.span_id,
        field_name="rule",
        quote=quote[:500],
        source_span=span,
        metadata={"rule_id": rule.get("rule_id"), "source": "m7_artifact"},
    )


def decompose_m7_rule(
    rule: dict[str, Any],
    *,
    city: str,
    zone: str,
    span: SourceSpan | None,
    status: str | None = None,
) -> StructuredRule:
    return structured_rule_from_m7(
        rule,
        city=city,
        zone=zone,
        evidence_pointer=evidence_pointer_for_rule(rule, span),
        status=status,
    )


def decompose_m7_rules(
    rules: list[dict[str, Any]],
    *,
    city: str,
    zone: str,
    spans_by_evidence_id: dict[str, SourceSpan],
    status: str | None = None,
) -> list[StructuredRule]:
    structured: list[StructuredRule] = []
    for rule in rules:
        evidence_id = str(rule.get("evidence_id") or (rule.get("candidate") or {}).get("evidence_id") or "")
        structured.append(
            decompose_m7_rule(
                rule,
                city=city,
                zone=zone,
                span=spans_by_evidence_id.get(evidence_id),
                status=status,
            )
        )
    return structured
