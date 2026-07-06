"""Guarded M8.5 repair reruns through the deterministic verifier."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Callable

from burnaby_prototype.m8.extraction.rule_schema import (
    PROMOTED_STATUSES,
    RepairAttempt,
    VerificationDecision,
)
from burnaby_prototype.m8.verification.m8_verifier import verify_candidate_with_m7
from burnaby_prototype.m8_5.repair_evaluation import RepairEvaluation


Verifier = Callable[[dict[str, Any], tuple[RepairAttempt, ...]], VerificationDecision]


def disabled_repair_rerun_report() -> dict[str, Any]:
    return {
        "mode": "m8_5_guarded_repair_rerun",
        "enabled": False,
        "notes": [
            "Repair rerun was not enabled for this pipeline invocation.",
            "Repair evaluations remain advisory and cannot promote rules directly.",
        ],
        "eligible_rule_count": 0,
        "attempt_count": 0,
        "promotion_ready_count": 0,
        "review_needed_count": 0,
        "context_required_count": 0,
        "rejected_count": 0,
        "failed_count": 0,
        "attempts": [],
        "promotion_ready": [],
        "skipped": [],
    }


def empty_guarded_repair_promotions() -> dict[str, Any]:
    return {
        "mode": "m8_5_guarded_repair_promotions",
        "applied": False,
        "promotion_count": 0,
        "review_removed_count": 0,
        "promoted_rule_ids": [],
        "promotions": [],
        "rejected_promotion_count": 0,
        "rejected_promotions": [],
        "notes": [
            "No guarded repair promotions were applied.",
            "Only deterministic verifier proof can move a repair into repaired_successfully.",
        ],
    }


def select_verifier_ready_repairs(repair_evaluations: list[Any]) -> list[RepairEvaluation]:
    """Return one deterministic verifier-ready repair evaluation per rule."""
    eligible = [
        _as_evaluation(evaluation)
        for evaluation in repair_evaluations
        if _as_evaluation(evaluation).verifier_ready
        and _as_evaluation(evaluation).recommended_status == "ready_for_verifier"
    ]
    selected: dict[str, RepairEvaluation] = {}
    for evaluation in sorted(eligible, key=_selection_key):
        selected.setdefault(evaluation.rule_id, evaluation)
    return [selected[rule_id] for rule_id in sorted(selected)]


def run_repair_reruns(
    *,
    config: dict[str, Any],
    structured_rules: list[dict[str, Any]],
    repair_evaluations: list[Any],
    evidence_units: list[dict[str, Any]],
    verifier: Verifier | None = None,
) -> dict[str, Any]:
    """Run verifier-ready repair patches through the deterministic verifier."""
    verifier = verifier or (
        lambda candidate, history: verify_candidate_with_m7(
            config=config,
            evidence_units=evidence_units,
            candidate=candidate,
            repair_history=history,
        )
    )
    rules_by_id = {str(rule.get("rule_id") or ""): rule for rule in structured_rules}
    selected = select_verifier_ready_repairs(repair_evaluations)
    attempts: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for evaluation in selected:
        original_rule = rules_by_id.get(evaluation.rule_id)
        if not original_rule:
            skipped.append({"rule_id": evaluation.rule_id, "reason": "structured_rule_not_found"})
            continue
        patched_candidate = patched_candidate_for_evaluation(original_rule, evaluation)
        if not str(patched_candidate.get("evidence_id") or ""):
            skipped.append({"rule_id": evaluation.rule_id, "reason": "patched_candidate_missing_evidence_id"})
            continue
        repair_history = _typed_repair_history(evaluation)
        decision = _with_original_rule_id(verifier(patched_candidate, repair_history), evaluation.rule_id)
        risk_flags = promotion_risk_flags(
            evaluation=evaluation,
            decision=decision,
            original_rule=original_rule,
            patched_candidate=patched_candidate,
        )
        promotion_ready = decision.status in PROMOTED_STATUSES and not risk_flags
        attempts.append(
            {
                "rule_id": evaluation.rule_id,
                "original_status": original_rule.get("status"),
                "selected_repair": selected_repair_summary(evaluation),
                "patched_candidate": patched_candidate,
                "retry_decision": decision.status,
                "retry_reason": decision.reason,
                "retry_evidence_ids": list(decision.evidence_ids),
                "retry_support_gaps": list(decision.support_gaps),
                "retry_unresolved_dependencies": list(decision.unresolved_dependencies),
                "promotion_ready": promotion_ready,
                "promotion_risk_flags": risk_flags,
                "verification_decision": decision.to_dict(),
                "repair_history": [attempt.to_dict() for attempt in repair_history],
            }
        )
    promotion_ready = [attempt for attempt in attempts if attempt["promotion_ready"]]
    status_counts = _status_counts(attempts)
    return {
        "mode": "m8_5_guarded_repair_rerun",
        "enabled": True,
        "notes": [
            "Repair reruns test candidate copies through the deterministic verifier.",
            "Repair evaluation readiness is not promotion authority.",
            "Promotion-ready requires verifier proof, evidence ids, no support gaps, no unresolved dependencies, and no risk flags.",
        ],
        "eligible_rule_count": len(selected),
        "attempt_count": len(attempts),
        "promotion_ready_count": len(promotion_ready),
        "review_needed_count": status_counts.get("review_needed", 0),
        "context_required_count": status_counts.get("context_required", 0),
        "rejected_count": status_counts.get("rejected", 0),
        "failed_count": len(attempts) - len(promotion_ready),
        "attempts": attempts,
        "promotion_ready": promotion_ready,
        "skipped": skipped,
    }


def apply_guarded_repair_promotions(
    *,
    verification_decisions: list[dict[str, Any]],
    structured_rules: list[dict[str, Any]],
    repair_rerun_report: dict[str, Any],
    apply: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not apply:
        report = empty_guarded_repair_promotions()
        report["applied"] = False
        return list(verification_decisions), list(structured_rules), report
    ready_by_rule = {
        str(attempt.get("rule_id") or ""): attempt
        for attempt in repair_rerun_report.get("promotion_ready", [])
    }
    promoted_rule_ids = set(ready_by_rule)
    updated_decisions = [
        _promoted_decision(row, ready_by_rule[str(row.get("rule_id") or "")])
        if str(row.get("rule_id") or "") in ready_by_rule
        else dict(row)
        for row in verification_decisions
    ]
    existing_decision_ids = {str(row.get("rule_id") or "") for row in verification_decisions}
    original_rules_by_id = {str(rule.get("rule_id") or ""): rule for rule in structured_rules}
    for rule_id in sorted(promoted_rule_ids - existing_decision_ids):
        original_rule = original_rules_by_id.get(rule_id, {})
        updated_decisions.append(
            _promoted_decision(
                {
                    "rule_id": rule_id,
                    "status": original_rule.get("status") or "review_needed",
                    "reason": (original_rule.get("raw") or {}).get("review_reason") or "missing original decision row",
                },
                ready_by_rule[rule_id],
            )
        )
    updated_rules = [
        _promoted_structured_rule(rule, ready_by_rule[str(rule.get("rule_id") or "")])
        if str(rule.get("rule_id") or "") in ready_by_rule
        else dict(rule)
        for rule in structured_rules
    ]
    review_removed_rule_ids = {
        str(row.get("rule_id") or "")
        for row in verification_decisions
        if str(row.get("rule_id") or "") in promoted_rule_ids
        and str(row.get("status") or "") in {"review_needed", "context_required"}
    }
    review_removed_rule_ids.update(
        str(rule.get("rule_id") or "")
        for rule in structured_rules
        if str(rule.get("rule_id") or "") in promoted_rule_ids
        and str(rule.get("status") or "") in {"review_needed", "context_required"}
    )
    review_removed_count = len(review_removed_rule_ids)
    report = {
        "mode": "m8_5_guarded_repair_promotions",
        "applied": True,
        "promotion_count": len(promoted_rule_ids),
        "review_removed_count": review_removed_count,
        "promoted_rule_ids": sorted(promoted_rule_ids),
        "promotions": [_promotion_summary(ready_by_rule[rule_id]) for rule_id in sorted(promoted_rule_ids)],
        "rejected_promotion_count": sum(
            1
            for attempt in repair_rerun_report.get("attempts", [])
            if not attempt.get("promotion_ready")
        ),
        "rejected_promotions": [
            {
                "rule_id": attempt.get("rule_id"),
                "retry_decision": attempt.get("retry_decision"),
                "promotion_risk_flags": list(attempt.get("promotion_risk_flags") or []),
                "retry_support_gaps": list(attempt.get("retry_support_gaps") or []),
            }
            for attempt in repair_rerun_report.get("attempts", [])
            if not attempt.get("promotion_ready")
        ],
        "notes": [
            "Promotions require deterministic verifier proof from the repair rerun.",
            "Repair readiness, reviewer actions, and confidence scores cannot promote by themselves.",
        ],
    }
    return updated_decisions, updated_rules, report


def repair_rerun_metrics(repair_rerun_report: dict[str, Any], guarded_promotions: dict[str, Any]) -> dict[str, Any]:
    return {
        "repair_rerun_eligible_rule_count": int(repair_rerun_report.get("eligible_rule_count") or 0),
        "repair_rerun_attempt_count": int(repair_rerun_report.get("attempt_count") or 0),
        "repair_rerun_promotion_ready_count": int(repair_rerun_report.get("promotion_ready_count") or 0),
        "guarded_repair_promotion_count": int(guarded_promotions.get("promotion_count") or 0),
        "repair_rerun_review_needed_count": int(repair_rerun_report.get("review_needed_count") or 0),
        "repair_rerun_context_required_count": int(repair_rerun_report.get("context_required_count") or 0),
        "repair_rerun_rejected_count": int(repair_rerun_report.get("rejected_count") or 0),
        "review_needed_reduction_from_repair_rerun": int(guarded_promotions.get("review_removed_count") or 0),
    }


def repair_rerun_markdown(report: dict[str, Any], promotions: dict[str, Any], *, limit: int = 30) -> str:
    metrics = repair_rerun_metrics(report, promotions)
    lines = [
        "# M8.5 Repair Rerun Report",
        "",
        f"Enabled: `{report.get('enabled', False)}`",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Eligible repair-ready rules | {metrics['repair_rerun_eligible_rule_count']} |",
        f"| Rerun attempts | {metrics['repair_rerun_attempt_count']} |",
        f"| Promotion-ready repairs | {metrics['repair_rerun_promotion_ready_count']} |",
        f"| Guarded promotions applied | {metrics['guarded_repair_promotion_count']} |",
        f"| Review-needed after rerun | {metrics['repair_rerun_review_needed_count']} |",
        f"| Context-required after rerun | {metrics['repair_rerun_context_required_count']} |",
        f"| Rejected after rerun | {metrics['repair_rerun_rejected_count']} |",
        "",
        f"## First {limit} Attempts",
        "",
    ]
    for attempt in report.get("attempts", [])[:limit]:
        lines.append(
            f"- `{attempt.get('rule_id')}` -> `{attempt.get('retry_decision')}` "
            f"ready=`{attempt.get('promotion_ready')}` "
            f"evidence=`{', '.join(attempt.get('retry_evidence_ids') or []) or 'none'}` "
            f"gaps=`{', '.join(attempt.get('retry_support_gaps') or []) or 'none'}`"
        )
    return "\n".join(lines) + "\n"


def patched_candidate_for_evaluation(rule: dict[str, Any], evaluation: RepairEvaluation) -> dict[str, Any]:
    raw = dict(rule.get("raw") or {})
    candidate = dict(raw.get("candidate") or {})
    if not candidate:
        candidate = {
            "candidate_id": rule.get("rule_id"),
            "rule_object": rule.get("rule_type"),
            "constraint_scope": raw.get("constraint_scope") or rule.get("rule_type"),
            "applies_to": rule.get("subject"),
            "operator": rule.get("comparator"),
            "value": rule.get("value"),
            "unit": rule.get("unit"),
            "condition": next(iter(rule.get("conditions") or []), ""),
            "exception": next(iter(rule.get("exceptions") or []), ""),
            "evidence_id": next(iter(rule.get("evidence_ids") or []), ""),
        }
    attempt = _selected_history_attempt(evaluation)
    patch = dict((attempt.get("patch") or {}) if isinstance(attempt, dict) else {})
    changes = dict(patch.get("changes") or {})
    original_candidate_id = str(candidate.get("candidate_id") or evaluation.rule_id)
    evidence_id = str(changes.get("evidence_id") or next(iter(evaluation.evidence_ids), "") or candidate.get("evidence_id") or "")
    patched = {**candidate, **changes}
    patched["candidate_id"] = f"{original_candidate_id}__m8_5_rerun__{_safe_id(evidence_id)}"
    patched["original_candidate_id"] = original_candidate_id
    patched["original_rule_id"] = evaluation.rule_id
    patched["evidence_id"] = evidence_id
    patched["m8_5_repair_rerun"] = True
    patched["m8_5_repair_changed_fields"] = list(evaluation.changed_fields)
    if (evaluation.metadata or {}).get("clear_extraction_review"):
        patched.pop("extraction_final_action", None)
        patched.pop("extraction_review_reasons", None)
        patched["m8_5_repair_replaced_extraction_review"] = True
    return patched


def promotion_risk_flags(
    *,
    evaluation: RepairEvaluation,
    decision: VerificationDecision,
    original_rule: dict[str, Any],
    patched_candidate: dict[str, Any],
) -> list[str]:
    flags: list[str] = []
    if not evaluation.verifier_ready:
        flags.append("repair_evaluation_not_verifier_ready")
    if evaluation.promotes_directly:
        flags.append("repair_evaluation_attempted_direct_promotion")
    if decision.status in PROMOTED_STATUSES and not decision.evidence_ids:
        flags.append("promoted_decision_missing_evidence_ids")
    if decision.status in PROMOTED_STATUSES and decision.support_gaps:
        flags.append("promoted_decision_has_support_gaps")
    if decision.status in PROMOTED_STATUSES and decision.unresolved_dependencies:
        flags.append("promoted_decision_has_unresolved_dependencies")
    dependency_report = decision.metadata.get("dependency_report", {}) if isinstance(decision.metadata, dict) else {}
    if dependency_report.get("has_conflicts"):
        flags.append("dependency_conflict_present")
    if not str(patched_candidate.get("evidence_id") or ""):
        flags.append("patched_candidate_missing_evidence_id")
    raw = original_rule.get("raw") or {}
    if raw.get("proof_decision_mismatch"):
        flags.append("original_rule_had_proof_decision_mismatch")
    return sorted(set(flags))


def selected_repair_summary(evaluation: RepairEvaluation) -> dict[str, Any]:
    attempt = _selected_history_attempt(evaluation)
    patch = dict(attempt.get("patch") or {}) if isinstance(attempt, dict) else {}
    return {
        "rule_id": evaluation.rule_id,
        "attempt_index": _attempt_index(evaluation),
        "confidence": _repair_confidence(evaluation),
        "evidence_ids": list(evaluation.evidence_ids),
        "changed_fields": list(evaluation.changed_fields),
        "safety_category": evaluation.safety_category,
        "safety_findings": list(evaluation.safety_findings),
        "metadata": dict(evaluation.metadata or {}),
        "patch": patch,
    }


def _promoted_decision(row: dict[str, Any], attempt: dict[str, Any]) -> dict[str, Any]:
    decision = dict(row)
    verifier_decision = dict(attempt.get("verification_decision") or {})
    metadata = dict(decision.get("metadata") or {})
    metadata["m8_5_guarded_repair_promotion"] = _promotion_summary(attempt)
    decision.update(
        {
            "status": "repaired_successfully",
            "reason": "verified after guarded M8.5 repair rerun",
            "evidence_ids": list(verifier_decision.get("evidence_ids") or attempt.get("retry_evidence_ids") or []),
            "support_gaps": [],
            "unresolved_dependencies": [],
            "repair_history": list(attempt.get("repair_history") or []),
            "metadata": metadata,
        }
    )
    return decision


def _promoted_structured_rule(rule: dict[str, Any], attempt: dict[str, Any]) -> dict[str, Any]:
    promoted = dict(rule)
    promoted["status"] = "repaired_successfully"
    selected = attempt.get("selected_repair") or {}
    patch = selected.get("patch") or {}
    if patch.get("evidence_pointers"):
        promoted["evidence_pointers"] = list(patch["evidence_pointers"])
    raw = dict(promoted.get("raw") or {})
    candidate = dict(raw.get("candidate") or {})
    candidate.update(dict(attempt.get("patched_candidate") or {}))
    raw.update(candidate)
    raw["candidate"] = candidate
    raw["verification_decision"] = "repaired_successfully"
    raw["support_gaps"] = []
    raw["review_reason"] = "verified after guarded M8.5 repair rerun"
    raw["m8_5_guarded_repair_promotion"] = _promotion_summary(attempt)
    promoted["raw"] = raw
    return promoted


def _promotion_summary(attempt: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule_id": attempt.get("rule_id"),
        "retry_decision": attempt.get("retry_decision"),
        "retry_evidence_ids": list(attempt.get("retry_evidence_ids") or []),
        "retry_reason": attempt.get("retry_reason"),
        "selected_repair": attempt.get("selected_repair"),
    }


def _with_original_rule_id(decision: VerificationDecision, rule_id: str) -> VerificationDecision:
    status = "repaired_successfully" if decision.status == "verified" and decision.repair_history else decision.status
    return replace(decision, rule_id=rule_id, status=status)


def _typed_repair_history(evaluation: RepairEvaluation) -> tuple[RepairAttempt, ...]:
    attempts: list[RepairAttempt] = []
    for row in evaluation.repair_history:
        if isinstance(row, RepairAttempt):
            attempts.append(row)
        elif isinstance(row, dict):
            attempts.append(RepairAttempt.from_dict(row))
    return tuple(attempts)


def _as_evaluation(evaluation: Any) -> RepairEvaluation:
    if isinstance(evaluation, RepairEvaluation):
        return evaluation
    return RepairEvaluation.from_dict(dict(evaluation or {}))


def _selection_key(evaluation: RepairEvaluation) -> tuple[float, int, int, str, str]:
    return (
        -_repair_confidence(evaluation),
        -_field_proof_count(evaluation),
        _attempt_index(evaluation),
        next(iter(evaluation.evidence_ids), ""),
        evaluation.rule_id,
    )


def _field_proof_count(evaluation: RepairEvaluation) -> int:
    metadata = dict(evaluation.metadata or {})
    try:
        return int(metadata.get("field_proof_count") or 0)
    except (TypeError, ValueError):
        return 0


def _repair_confidence(evaluation: RepairEvaluation) -> float:
    attempt = _selected_history_attempt(evaluation)
    patch = dict(attempt.get("patch") or {}) if isinstance(attempt, dict) else {}
    confidences = [
        float(pointer.get("confidence", 0.0) or 0.0)
        for pointer in patch.get("evidence_pointers") or []
        if isinstance(pointer, dict)
    ]
    return max(confidences) if confidences else 0.0


def _attempt_index(evaluation: RepairEvaluation) -> int:
    attempt = _selected_history_attempt(evaluation)
    if isinstance(attempt, dict):
        return int(attempt.get("attempt_index") or 999999)
    return 999999


def _selected_history_attempt(evaluation: RepairEvaluation) -> dict[str, Any]:
    for attempt in evaluation.repair_history:
        if isinstance(attempt, dict):
            return attempt
        if isinstance(attempt, RepairAttempt):
            return attempt.to_dict()
    return {}


def _status_counts(attempts: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for attempt in attempts:
        status = str(attempt.get("retry_decision") or "")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _safe_id(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", str(text or "evidence")).strip("_") or "evidence"
