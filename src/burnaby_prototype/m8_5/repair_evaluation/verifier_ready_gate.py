"""Verifier-ready gate for M8.5 repair evaluations."""

from __future__ import annotations


VERIFIER_READY_CATEGORIES = frozenset({"safe_for_verifier"})


class VerifierReadyGate:
    def is_ready(self, *, safety_category: str, findings: tuple[str, ...]) -> bool:
        if safety_category not in VERIFIER_READY_CATEGORIES:
            return False
        blockers = {
            "missing_patch_evidence",
            "changed_value_not_in_evidence",
            "changed_unit_not_in_evidence",
            "zone_scope_mismatch",
            "contradictory_evidence",
            "exception_dependency_introduced",
            "unsafe_exception_removal",
        }
        return not any(finding in blockers for finding in findings)


def recommended_status_for_category(safety_category: str, *, verifier_ready: bool) -> str:
    if verifier_ready:
        return "ready_for_verifier"
    if safety_category == "introduced_dependency":
        return "context_required"
    if safety_category in {"contradictory_evidence", "unsupported_patch", "unsafe_field_change"}:
        return "review_needed"
    return "review_needed"

