"""Generate minimal candidate patches from evidence bundles."""

from __future__ import annotations

from typing import Any

from ..extraction.rule_schema import EvidenceBundle, RepairCritique, RepairPatch


UNPATCHABLE = {"unit_mismatch", "conflicting_evidence", "unsupported_rule_type", "unresolved_cross_reference"}


def generate_patch(rule: dict[str, Any], critique: RepairCritique, bundle: EvidenceBundle) -> RepairPatch:
    if critique.category in UNPATCHABLE or not bundle.pointers:
        return RepairPatch(
            rule_id=critique.rule_id,
            category=critique.category,
            reason=f"{critique.category} is not safe to patch automatically",
        )
    best = bundle.pointers[0]
    changes: dict[str, Any] = {}
    evidence_id = best.evidence_id
    if evidence_id:
        changes["evidence_id"] = evidence_id
    if critique.category in {"missing_scope", "missing_condition", "weak_evidence", "missing_evidence"}:
        changes["m8_repair_evidence_span_id"] = best.span_id
    return RepairPatch(
        rule_id=critique.rule_id,
        changes=changes,
        evidence_pointers=(best,),
        reason="minimal evidence pointer patch from M8 retrieval",
        category=critique.category,
    )
