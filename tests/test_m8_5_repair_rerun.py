from __future__ import annotations

from burnaby_prototype.m8.extraction.rule_schema import VerificationDecision
from burnaby_prototype.m8_5.repair_evaluation import RepairEvaluation
from burnaby_prototype.m8_5.repair_rerun import (
    apply_guarded_repair_promotions,
    run_repair_reruns,
    select_verifier_ready_repairs,
)


def test_verifier_ready_repair_selection_deduplicates_by_rule() -> None:
    selected = select_verifier_ready_repairs(
        [
            _evaluation("rule_1", attempt_index=2, confidence=0.5, evidence_id="ev_b"),
            _evaluation("rule_1", attempt_index=1, confidence=0.9, evidence_id="ev_a"),
            _evaluation("rule_2", verifier_ready=False, recommended_status="review_needed"),
        ]
    )

    assert [item.rule_id for item in selected] == ["rule_1"]
    assert selected[0].evidence_ids == ("ev_a",)


def test_verifier_passed_repair_can_be_guardedly_promoted() -> None:
    report = run_repair_reruns(
        config={"city": "burnaby", "zone": "r1"},
        structured_rules=[_structured_rule("rule_1")],
        repair_evaluations=[_evaluation("rule_1")],
        evidence_units=[],
        verifier=lambda candidate, history: VerificationDecision(
            rule_id="temporary_id",
            status="verified",
            reason="verifier accepted repaired evidence",
            evidence_ids=(candidate["evidence_id"],),
            repair_history=history,
        ),
    )

    assert report["attempt_count"] == 1
    assert report["promotion_ready_count"] == 1
    assert report["attempts"][0]["retry_decision"] == "repaired_successfully"

    decisions, rules, promotions = apply_guarded_repair_promotions(
        verification_decisions=[{"rule_id": "rule_1", "status": "review_needed", "metadata": {}}],
        structured_rules=[_structured_rule("rule_1")],
        repair_rerun_report=report,
        apply=True,
    )

    assert decisions[0]["status"] == "repaired_successfully"
    assert rules[0]["status"] == "repaired_successfully"
    assert promotions["promotion_count"] == 1


def test_verifier_failed_repair_stays_out_of_promotions() -> None:
    report = run_repair_reruns(
        config={"city": "burnaby", "zone": "r1"},
        structured_rules=[_structured_rule("rule_1")],
        repair_evaluations=[_evaluation("rule_1")],
        evidence_units=[],
        verifier=lambda candidate, history: VerificationDecision(
            rule_id="temporary_id",
            status="review_needed",
            reason="still missing scope",
            evidence_ids=(candidate["evidence_id"],),
            support_gaps=("scope_not_supported",),
            repair_history=history,
        ),
    )

    assert report["promotion_ready_count"] == 0
    decisions, rules, promotions = apply_guarded_repair_promotions(
        verification_decisions=[{"rule_id": "rule_1", "status": "review_needed", "metadata": {}}],
        structured_rules=[_structured_rule("rule_1")],
        repair_rerun_report=report,
        apply=True,
    )

    assert decisions[0]["status"] == "review_needed"
    assert rules[0]["status"] == "review_needed"
    assert promotions["promotion_count"] == 0


def test_guarded_promotion_rejects_verified_decision_with_support_gaps() -> None:
    report = run_repair_reruns(
        config={"city": "burnaby", "zone": "r1"},
        structured_rules=[_structured_rule("rule_1")],
        repair_evaluations=[_evaluation("rule_1")],
        evidence_units=[],
        verifier=lambda candidate, history: VerificationDecision(
            rule_id="temporary_id",
            status="repaired_successfully",
            reason="bad verifier snapshot",
            evidence_ids=(candidate["evidence_id"],),
            support_gaps=("verified_with_gap",),
            repair_history=history,
        ),
    )

    assert report["promotion_ready_count"] == 0
    assert "promoted_decision_has_support_gaps" in report["attempts"][0]["promotion_risk_flags"]


def _structured_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "city": "burnaby_r1",
        "zone": "R1",
        "rule_type": "height",
        "subject": "building",
        "comparator": "<=",
        "value": "10.7",
        "unit": "m",
        "conditions": [],
        "exceptions": [],
        "dependencies": [],
        "evidence_pointers": [],
        "status": "review_needed",
        "raw": {
            "rule_id": rule_id,
            "evidence_id": "ev_old",
            "candidate": {
                "candidate_id": f"{rule_id}_candidate",
                "rule_object": "height",
                "constraint_scope": "height",
                "applies_to": "building",
                "operator": "<=",
                "value": "10.7",
                "unit": "m",
                "condition": "",
                "exception": "",
                "evidence_id": "ev_old",
            },
        },
    }


def _evaluation(
    rule_id: str,
    *,
    attempt_index: int = 1,
    confidence: float = 1.0,
    evidence_id: str = "ev_new",
    verifier_ready: bool = True,
    recommended_status: str = "ready_for_verifier",
) -> RepairEvaluation:
    return RepairEvaluation(
        rule_id=rule_id,
        original_failure="needs better evidence",
        changed_fields=("evidence_id",),
        safety_category="safe_for_verifier" if verifier_ready else "unsupported_patch",
        safety_findings=(),
        verifier_ready=verifier_ready,
        recommended_status=recommended_status,
        evidence_ids=(evidence_id,),
        repair_history=(
            {
                "attempt_index": attempt_index,
                "critique": {
                    "rule_id": rule_id,
                    "category": "general_review",
                    "reason": "needs better evidence",
                    "fields": [],
                    "support_gaps": [],
                },
                "query": "height 10.7 m",
                "patch": {
                    "rule_id": rule_id,
                    "changes": {"evidence_id": evidence_id},
                    "evidence_pointers": [
                        {
                            "evidence_id": evidence_id,
                            "span_id": f"span_{evidence_id}",
                            "field_name": "retrieved_context",
                            "quote": "R1 maximum height 10.7 m",
                            "confidence": confidence,
                        }
                    ],
                    "reason": "test patch",
                    "category": "general_review",
                },
                "decision_status": "review_needed",
                "reason": "needs verifier",
                "evidence_bundle_id": "bundle_1",
            },
        ),
    )
