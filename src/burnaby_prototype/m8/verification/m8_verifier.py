"""M8 verification wrapper.

The wrapper can call the existing M7 verifier for candidate checks. It then
adds M8 dependency statuses. It never bypasses M7 verification.
"""

from __future__ import annotations

from typing import Any

from ...verification import verify_candidates
from ..extraction.rule_schema import (
    EvidencePointer,
    RepairAttempt,
    SourceSpan,
    StructuredRule,
    VerificationDecision,
)
from .dependency_checker import dependency_report, field_support_report


CRITICAL_REJECT_GAPS = {
    "source_evidence_id_not_found",
    "value_not_found_in_evidence",
    "unit_not_found_in_evidence",
    "rule_object_unit_not_compatible",
    "column_value_mismatch",
    "table_operator_refuted",
    "value_bound_to_foreign_unit",
}


def verify_structured_rule(rule: StructuredRule, *, repair_history: tuple[RepairAttempt, ...] = ()) -> VerificationDecision:
    spans = [pointer.source_span for pointer in rule.evidence_pointers if pointer.source_span is not None]
    evidence_ids = rule.evidence_ids
    if not spans:
        return VerificationDecision(
            rule_id=rule.rule_id,
            status="review_needed",
            reason="M8 rule has no source span evidence",
            support_gaps=("source_span_missing",),
            repair_history=repair_history,
        )
    deps = dependency_report(rule, spans)
    support = field_support_report(rule, spans)
    support_gaps = [
        name
        for name, ok in support.items()
        if not ok
    ]
    m7_status = str(rule.raw.get("verification_decision") or rule.status or "review_needed")
    m7_gaps = tuple(str(gap) for gap in rule.raw.get("support_gaps", []) or [])
    if any(gap in CRITICAL_REJECT_GAPS for gap in m7_gaps) or deps["has_conflicts"]:
        return VerificationDecision(
            rule_id=rule.rule_id,
            status="rejected",
            reason="critical M7 gap or conflicting source span",
            evidence_ids=evidence_ids,
            support_gaps=tuple(sorted({*m7_gaps, *support_gaps})),
            repair_history=repair_history,
            metadata={"dependency_report": deps},
        )
    unresolved = tuple(deps["unresolved_dependencies"])
    if unresolved and m7_status in {"verified", "repaired_successfully"}:
        return VerificationDecision(
            rule_id=rule.rule_id,
            status="context_required",
            reason="scalar evidence is present but dependency context remains unresolved",
            evidence_ids=evidence_ids,
            unresolved_dependencies=unresolved,
            support_gaps=tuple(sorted({*m7_gaps, *support_gaps})),
            repair_history=repair_history,
            metadata={"dependency_report": deps},
        )
    if m7_status in {"verified", "repaired_successfully"} and not support_gaps and not unresolved:
        status = "repaired_successfully" if repair_history or m7_status == "repaired_successfully" else "verified"
        return VerificationDecision(
            rule_id=rule.rule_id,
            status=status,
            reason="M7 verifier accepted and M8 dependency checks found no blocker",
            evidence_ids=evidence_ids,
            repair_history=repair_history,
            metadata={"dependency_report": deps},
        )
    if m7_status == "not_used":
        status = "not_used"
    elif m7_status == "rejected":
        status = "rejected"
    elif unresolved:
        status = "context_required"
    else:
        status = "review_needed"
    return VerificationDecision(
        rule_id=rule.rule_id,
        status=status,
        reason="M8 did not find enough verified support to promote",
        evidence_ids=evidence_ids,
        unresolved_dependencies=unresolved,
        support_gaps=tuple(sorted({*m7_gaps, *support_gaps})),
        repair_history=repair_history,
        metadata={"dependency_report": deps},
    )


def verify_candidate_with_m7(
    *,
    config: dict[str, Any],
    evidence_units: list[dict[str, Any]],
    candidate: dict[str, Any],
    repair_history: tuple[RepairAttempt, ...] = (),
) -> VerificationDecision:
    result = verify_candidates(config, evidence_units, [candidate])
    verified = result.get("verified_rules") or []
    review = result.get("review_needed") or []
    if verified:
        row = dict(verified[0])
        row["verification_decision"] = "verified"
    elif review:
        row = dict(review[0])
    else:
        row = dict(candidate)
        row["verification_decision"] = "review_needed"
    span = _span_for_candidate(candidate, evidence_units, config=config)
    pointer = None
    if span is not None:
        pointer = EvidencePointer(
            evidence_id=str(candidate.get("evidence_id") or ""),
            span_id=span.span_id,
            field_name="rule",
            quote=span.text[:500],
            source_span=span,
        )
    structured = StructuredRule(
        rule_id=str(row.get("rule_id") or candidate.get("candidate_id") or ""),
        city=str(config.get("city") or ""),
        zone=str(config.get("zone") or ""),
        rule_type=str(row.get("rule_object") or candidate.get("rule_object") or ""),
        subject=str(row.get("applies_to") or candidate.get("applies_to") or ""),
        comparator=str(row.get("operator") or candidate.get("operator") or ""),
        value=row.get("value", candidate.get("value")),
        unit=str(row.get("unit") or candidate.get("unit") or ""),
        conditions=tuple([str(row.get("condition") or candidate.get("condition") or "")]) if (row.get("condition") or candidate.get("condition")) else (),
        exceptions=tuple([str(row.get("exception") or candidate.get("exception") or "")]) if (row.get("exception") or candidate.get("exception")) else (),
        evidence_pointers=(pointer,) if pointer else (),
        status=str(row.get("verification_decision") or "review_needed"),
        raw=row,
    )
    return verify_structured_rule(structured, repair_history=repair_history)


def _span_for_candidate(candidate: dict[str, Any], evidence_units: list[dict[str, Any]], *, config: dict[str, Any]) -> SourceSpan | None:
    evidence_id = str(candidate.get("evidence_id") or "")
    for unit in evidence_units:
        if str(unit.get("evidence_id") or "") == evidence_id:
            text = str(unit.get("evidence_text") or "")
            context = str(unit.get("source_context") or "")
            combined = text if not context or context == text else f"{text}\n{context}"
            if not combined.strip():
                return None
            return SourceSpan(
                city=str(config.get("city") or ""),
                document_id=str((config.get("source_document") or "source.pdf")),
                page=unit.get("page"),
                section_id=str(unit.get("section") or ""),
                block_type=str(unit.get("evidence_type") or "evidence"),
                char_start=0,
                char_end=len(combined),
                text=combined,
                source_url=str(config.get("source_url") or ""),
                metadata={"evidence_id": evidence_id},
            )
    return None
