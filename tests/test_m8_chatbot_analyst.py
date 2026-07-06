from dashboard.m8_data import (
    evidence_span_rows,
    m8_metric_cards,
    repair_rows,
    rule_explorer_rows,
    unresolved_dependency_rows,
    weakest_coverage_rows,
)
from burnaby_prototype.m8.chatbot.analyst_tools import answer_m8_question


def context():
    return {
        "summary": {"city": "burnaby_r1", "status_counts": {"verified": 1, "review_needed": 1}},
        "comparison": {
            "city": "burnaby_r1",
            "m7": {"review_needed_count": 3},
            "m8": {
                "verified_count": 1,
                "repaired_successfully_count": 0,
                "review_needed_count": 1,
                "review_needed_reduction": 2,
                "false_verified_count": 0,
                "status_counts": {"verified": 1, "review_needed": 1},
                "coverage_by_rule_type": [
                    {"rule_type": "height", "total": 2, "verified_like": 1, "coverage": 0.5},
                    {"rule_type": "setback", "total": 3, "verified_like": 0, "coverage": 0.0},
                ],
            },
            "safety": {"m7_safety_preserved": True},
        },
        "rules": [
            {
                "rule_id": "r1",
                "status": "verified",
                "rule_type": "height",
                "subject": "building",
                "value": "10",
                "unit": "m",
                "evidence_pointers": [{"evidence_id": "ev1", "source_span": {"page": 1, "section_id": "101.3"}}],
            },
            {"rule_id": "r2", "status": "review_needed", "raw": {"review_reason": "scope missing"}},
        ],
        "decisions": [
            {"rule_id": "r2", "status": "context_required", "unresolved_dependencies": ["condition_dependency"]}
        ],
        "repair_attempts": [
            {"critique": {"rule_id": "r2", "category": "missing_scope"}, "decision_status": "review_needed", "query": "height", "reason": "no patch"}
        ],
    }


def test_m8_chatbot_answers_safety_question():
    answer = answer_m8_question("Did M8 preserve the M7 zero-false-verified guarantee?", context())

    assert "True" in answer
    assert "False verified count: 0" in answer


def test_m8_chatbot_refuses_mutation():
    assert "cannot support" in answer_m8_question("approve this rule", context())


def test_m8_dashboard_data_providers():
    data = context()

    assert m8_metric_cards(data)[0]["label"] == "Verified"
    assert repair_rows(data)[0]["category"] == "missing_scope"
    assert rule_explorer_rows(data, status="verified")[0]["rule_id"] == "r1"
    assert weakest_coverage_rows(data)[0]["rule_type"] == "setback"
    assert unresolved_dependency_rows(data)[0]["dependency"] == "condition_dependency"
    assert evidence_span_rows(data)[0]["evidence_id"] == "ev1"
