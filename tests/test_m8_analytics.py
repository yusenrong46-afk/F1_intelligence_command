from burnaby_prototype.m8.analytics.m7_m8_compare import compare_m7_m8
from burnaby_prototype.m8.extraction.rule_schema import StructuredRule, VerificationDecision


def test_m7_m8_comparison_metrics():
    rules = [
        StructuredRule(rule_id="r1", city="burnaby_r1", zone="R1", rule_type="height", subject="building", status="review_needed"),
        StructuredRule(rule_id="r2", city="burnaby_r1", zone="R1", rule_type="setback", subject="yard", status="review_needed"),
    ]
    decisions = [
        VerificationDecision(rule_id="r1", status="review_needed"),
        VerificationDecision(rule_id="r2", status="context_required", evidence_ids=("ev2",), unresolved_dependencies=("overlay_dependency",)),
    ]

    report = compare_m7_m8(
        city="burnaby_r1",
        m7_benchmark={
            "rule_metrics": {
                "verified_rule_count": 1,
                "review_rule_count": 2,
                "false_verified_count": 0,
            },
            "proposal_metrics": {"false_approval_count": 0},
        },
        m7_summary={},
        structured_rules=rules,
        decisions=decisions,
        attempts=[],
    )

    assert report["m8"]["context_required_count"] == 1
    assert report["m8"]["review_needed_reduction"] == 1
    assert report["safety"]["m7_safety_preserved"] is True
