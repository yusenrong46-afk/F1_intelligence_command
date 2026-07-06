import json

from burnaby_prototype.m8_5.chatbot import answer_m8_5_question, load_m8_5_chatbot_context


def test_chatbot_cannot_call_review_needed_rule_verified(tmp_path):
    context = _write_context(tmp_path)

    answer = answer_m8_5_question("Can you mark as verified this review_needed rule?", context)

    assert "not available" in answer
    assert "cannot approve or verify" in answer


def test_chatbot_explains_table_lineage(tmp_path):
    context = _write_context(tmp_path)

    answer = answer_m8_5_question("Explain table lineage with row and column context.", context)

    assert "lineage" in answer
    assert "row `R1`" in answer
    assert "column `Height`" in answer
    assert "candidate_only" in answer


def test_chatbot_explains_unresolved_dependency(tmp_path):
    context = _write_context(tmp_path)

    answer = answer_m8_5_question("Which rules are blocked by unresolved dependencies?", context)

    assert "unresolved dependencies" in answer
    assert "blocks rule `r2`" in answer


def test_chatbot_reports_zero_false_verified_from_summary_artifact(tmp_path):
    context = _write_context(tmp_path)
    context["comparison"]["safety"]["false_verified_count"] = 99

    answer = answer_m8_5_question("Did M8.5 preserve zero false verified rules?", context)

    assert "false_verified_count = 0" in answer
    assert "false_approval_count = 0" in answer


def test_chatbot_distinguishes_m8_from_m8_5_measured_results(tmp_path):
    context = _write_context(tmp_path)

    answer = answer_m8_5_question("Distinguish M8 and M8.5 measured results.", context)

    assert "M8 verified-like: 87" in answer
    assert "M8.5 verified-like: 87" in answer
    assert "M8.5 table-derived rules: 1" in answer


def test_chatbot_says_not_available_when_artifact_missing(tmp_path):
    context = _write_context(tmp_path)
    (tmp_path / "table_derived_rules.json").unlink()
    context = load_m8_5_chatbot_context(tmp_path)

    answer = answer_m8_5_question("Explain table lineage with row and column context.", context)

    assert answer.startswith("not available")
    assert "table_derived_rules.json" in answer


def _write_context(path):
    summary = {
        "city": "burnaby_r1",
        "safety": {
            "m7_safety_preserved": True,
            "false_verified_count": 0,
            "false_approval_count": 0,
        },
    }
    comparison = {
        "city": "burnaby_r1",
        "m8": {"verified_like_count": 87},
        "m8_5": {
            "verified_like_count": 87,
            "review_needed_count": 48,
            "context_required_count": 9,
            "table_derived_rules_count": 1,
            "dependency_total_count": 1,
            "dependency_unresolved_count": 1,
            "false_verified_count": 0,
            "false_approval_count": 0,
        },
        "safety": {
            "m7_safety_preserved": True,
            "false_verified_count": 0,
            "false_approval_count": 0,
        },
    }
    table_lineage = [
        {
            "lineage_id": "lineage_1",
            "table_id": "tbl1",
            "row_label": "R1",
            "column_label": "Height",
            "cell_text": "10.7 m",
        }
    ]
    table_rules = [
        {
            "rule_id": "table_rule_1",
            "status": "candidate_only",
            "lineage": table_lineage[0],
        }
    ]
    dependency_graph = {
        "dependencies": [
            {
                "dependency_id": "dep1",
                "source_rule_id": "r2",
                "dependency_type": "cross_reference",
                "target_reference": "Section 6.4",
                "status": "unresolved",
            }
        ]
    }
    repair_evaluations = [
        {
            "rule_id": "r3",
            "verifier_ready": True,
            "recommended_status": "ready_for_verifier",
        }
    ]
    review_packets = [
        {
            "rule_id": "r2",
            "current_status": "context_required",
            "failure_reason": "unresolved cross-reference",
            "recommended_reviewer_action": "mark_dependency_resolved",
            "dependency_graph_slice": [dependency_graph["dependencies"][0]],
        }
    ]
    files = {
        "m8_5_summary.json": summary,
        "m8_m8_5_comparison.json": comparison,
        "table_cell_lineage.json": table_lineage,
        "table_derived_rules.json": table_rules,
        "dependency_graph.json": dependency_graph,
        "repair_evaluations.json": repair_evaluations,
        "review_packets.json": review_packets,
    }
    for name, payload in files.items():
        (path / name).write_text(json.dumps(payload), encoding="utf-8")
    return load_m8_5_chatbot_context(path)
