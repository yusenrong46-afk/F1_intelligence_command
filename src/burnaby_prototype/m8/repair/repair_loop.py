"""Bounded M8 repair loop."""

from __future__ import annotations

from typing import Any, Callable

from ..extraction.rule_schema import EvidenceBundle, RepairAttempt, VerificationDecision
from ..retrieval.evidence_bundle import build_evidence_bundle
from ..retrieval.hybrid_index import HybridM8Index
from ..retrieval.query_planner import plan_query
from .patch_applier import apply_patch_to_candidate
from .patch_generator import generate_patch
from .repair_judge import judge_repair
from .repair_planner import plan_repair_query


VerifierCallback = Callable[[dict[str, Any], tuple[RepairAttempt, ...]], VerificationDecision]


STATUS_RANK = {
    "verified": 6,
    "repaired_successfully": 5,
    "context_required": 4,
    "review_needed": 3,
    "not_used": 2,
    "rejected": 1,
}


def run_repair_loop(
    rule: dict[str, Any],
    *,
    index: HybridM8Index,
    verifier: VerifierCallback,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Run bounded repair on a candidate copy and return audit data."""
    candidate = dict(rule.get("candidate") or rule)
    attempts: list[RepairAttempt] = []
    bundles: list[EvidenceBundle] = []
    best_decision = verifier(candidate, tuple(attempts))
    best_candidate = dict(candidate)
    for attempt_index in range(1, max(0, max_attempts) + 1):
        critique = judge_repair({**rule, **candidate})
        query = plan_repair_query({**rule, **candidate}, critique)
        planned = plan_query(query, city=rule.get("city") or "")
        hits = index.search(planned, top_k=6)
        bundle = build_evidence_bundle(query, hits)
        bundles.append(bundle)
        patch = generate_patch({**rule, **candidate}, critique, bundle)
        patched = apply_patch_to_candidate(candidate, patch) if not patch.is_empty else dict(candidate)
        decision = verifier(patched, tuple(attempts))
        if decision.status == "verified" and not patch.is_empty:
            decision = VerificationDecision(
                rule_id=decision.rule_id,
                status="repaired_successfully",
                reason=decision.reason,
                evidence_ids=decision.evidence_ids,
                unresolved_dependencies=decision.unresolved_dependencies,
                support_gaps=decision.support_gaps,
                repair_history=decision.repair_history,
                verifier=decision.verifier,
                metadata=decision.metadata,
            )
        attempt = RepairAttempt(
            attempt_index=attempt_index,
            critique=critique,
            query=query,
            patch=patch,
            decision_status=decision.status,
            reason=decision.reason,
            evidence_bundle_id=bundle.bundle_id,
        )
        attempts.append(attempt)
        if STATUS_RANK[decision.status] > STATUS_RANK[best_decision.status]:
            best_decision = decision
            best_candidate = patched
        candidate = patched
        if decision.status in {"verified", "repaired_successfully"}:
            break
        if patch.is_empty:
            break
    return {
        "rule_id": rule.get("rule_id") or candidate.get("candidate_id"),
        "best_candidate": best_candidate,
        "best_decision": best_decision,
        "attempts": attempts,
        "evidence_bundles": bundles,
        "attempt_count": len(attempts),
        "stopped_reason": "success" if best_decision.status in {"verified", "repaired_successfully"} else "budget_or_no_safe_patch",
    }
