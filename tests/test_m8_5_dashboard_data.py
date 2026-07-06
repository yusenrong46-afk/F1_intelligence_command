import json

from dashboard.m8_5_data import (
    dependency_graph_rows,
    load_m8_5_output,
    review_queue_rows,
    status_count_rows,
    table_derived_rule_rows,
    table_lineage_rows,
)


def test_dashboard_provider_loads_m8_5_summary(tmp_path):
    (tmp_path / "m8_5_summary.json").write_text(json.dumps({"city": "burnaby_r1"}), encoding="utf-8")
    (tmp_path / "m8_m8_5_comparison.json").write_text(
        json.dumps({"m8_5": {"status_counts": {"verified": 1}}}),
        encoding="utf-8",
    )

    data = load_m8_5_output(tmp_path)

    assert data["summary"]["city"] == "burnaby_r1"
    assert status_count_rows(data) == [{"status": "verified", "count": 1}]


def test_table_lineage_display_model_preserves_row_and_column():
    data = {
        "table_cell_lineage": [
            {
                "lineage_id": "l1",
                "table_id": "tbl1",
                "page": 2,
                "section_id": "101",
                "row_label": "R1",
                "column_label": "Height",
                "cell_text": "10.7 m",
                "normalized_value": "10.7",
                "normalized_unit": "m",
                "inferred_rule_type": "height",
                "verifier_ready": True,
                "parse_warnings": [],
            }
        ],
        "table_derived_rules": [
            {
                "rule_id": "tr1",
                "status": "candidate_only",
                "rule_type": "height",
                "subject": "height",
                "comparator": "<=",
                "normalized_value": "10.7",
                "normalized_unit": "m",
                "lineage": {"row_label": "R1", "column_label": "Height"},
                "verifier_ready": True,
                "confidence": 0.95,
            }
        ],
    }

    lineage_rows = table_lineage_rows(data)
    rule_rows = table_derived_rule_rows(data)

    assert lineage_rows[0]["row"] == "R1"
    assert lineage_rows[0]["column"] == "Height"
    assert rule_rows[0]["status"] == "candidate_only"
    assert rule_rows[0]["verifier_ready"] is True


def test_dependency_graph_display_model():
    data = {
        "dependency_graph": {
            "dependencies": [
                {
                    "dependency_id": "dep1",
                    "source_rule_id": "r1",
                    "dependency_type": "cross_reference",
                    "target_reference": "Section 6.4",
                    "status": "unresolved",
                    "is_blocking": True,
                    "evidence_ids": [],
                    "reason": "reference missing",
                }
            ]
        }
    }

    rows = dependency_graph_rows(data)

    assert rows[0]["rule_id"] == "r1"
    assert rows[0]["type"] == "cross_reference"
    assert rows[0]["blocking"] is True


def test_review_queue_priority_sorting_prefers_verifier_ready_items():
    data = {
        "review_packets": [
            {
                "rule_id": "low",
                "current_status": "review_needed",
                "recommended_reviewer_action": "request_more_retrieval",
                "repair_evaluations": [],
                "dependency_graph_slice": [],
            },
            {
                "rule_id": "high",
                "current_status": "context_required",
                "recommended_reviewer_action": "send_to_verifier",
                "repair_evaluations": [{"verifier_ready": True}],
                "dependency_graph_slice": [{"dependency_id": "dep1"}],
            },
        ]
    }

    rows = review_queue_rows(data)

    assert [row["rule_id"] for row in rows] == ["high", "low"]
    assert rows[0]["priority"] > rows[1]["priority"]
