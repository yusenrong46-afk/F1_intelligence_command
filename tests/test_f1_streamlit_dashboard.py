from __future__ import annotations

import ast
import json
import importlib.util
from pathlib import Path

from dashboard.f1_data import (
    answer_artifact_question,
    artifact_rows,
    benchmark_gate_rows,
    command_center_cards,
    compliance_rows,
    compliance_status_rows,
    discover_f1_outputs,
    evaluate_rule_set,
    evaluate_single_rule,
    evidence_navigation_rows,
    evidence_rows,
    load_f1_output,
    operator_action_template_rows,
    operator_review_action_rows,
    pipeline_stage_rows,
    review_gap_rows,
    review_rows,
    rule_object_summary_rows,
    rule_rows,
    save_operator_review_action,
    scenario_template_rows,
    top_review_items,
    workflow_rows,
)


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "dashboard" / "f1_command_center.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_f1_streamlit_app_source_parses_and_imports() -> None:
    ast.parse(APP_PATH.read_text(encoding="utf-8"))
    module = _load_module("f1_command_center_import_test", APP_PATH)
    assert hasattr(module, "main")
    assert module.NAV_ITEMS == [
        "0 Command Center",
        "1 Sources",
        "2 Verified Rules",
        "3 Review Workbench",
        "4 Repair Evidence",
        "5 GIS + Compliance",
        "6 Quality Audit",
    ]
    assert "M8.5" not in APP_PATH.read_text(encoding="utf-8")


def test_f1_dashboard_has_no_active_m_series_pages() -> None:
    pages_dir = ROOT / "dashboard" / "pages"
    assert not pages_dir.exists()


def test_f1_data_provider_loads_command_center_manifest(tmp_path: Path) -> None:
    run = tmp_path / "outputs" / "f1_runs" / "burnaby_r1" / "checkpoint_16_product_operations"
    run.mkdir(parents=True)
    manifest = {
        "workflow_health": {
            "verified_rule_count": 1,
            "review_queue_count": 1,
            "quality_gates_passed": True,
            "false_verified_count": 0,
            "false_approval_count": 0,
        },
        "benchmark_metrics": {
            "retrieval_recall_at_6": 1.0,
            "candidate_recall": 0.9,
            "verified_precision": 1.0,
            "proposal_case_accuracy": 1.0,
        },
        "verified_rules": [
            {
                "rule_id": "rule_height",
                "rule_object": "height",
                "operator": "<=",
                "value": "4.6",
                "unit": "m",
                "applies_to": "accessory structure",
                "geometry_target": "building_envelope",
                "search_text": "rule_height height accessory ev_height",
                "citation": {"evidence_id": "ev_height", "page": 2, "quote": "height must not exceed 4.6 m"},
            }
        ],
        "review_queue": [
            {
                "rule_id": "rule_review",
                "status": "rejected",
                "rule_object": "height",
                "operator": "<=",
                "value": "5",
                "unit": "m",
                "support_gaps": ["operator_not_supported"],
                "search_text": "rule_review rejected operator_not_supported ev_review",
                "evidence": [{"field": "value", "evidence_id": "ev_review", "page": 3, "quote": "unsupported"}],
            }
        ],
        "compliance_decisions": [
            {"scenario_id": "scenario_height", "status": "approved", "verified_rule_ids": ["rule_height"], "review_rule_ids": []}
        ],
        "compliance_status_counts": {"approved": 1, "needs_review": 0, "rejected": 0},
        "product_workflows": [{"id": "rule_explorer", "label": "Rule Explorer", "status": "available"}],
        "source_artifacts": {"summary": "f1_summary.json"},
        "app_version": "checkpoint_16",
    }
    (run / "command_center_app_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run / "f1_summary.json").write_text(json.dumps({"extraction": {"candidate_count": 2}}), encoding="utf-8")
    (run / "verification_report.json").write_text(json.dumps({"verified_count": 1}), encoding="utf-8")
    (run / "guarded_repair_promotions.json").write_text(json.dumps([{"rule_id": "rule_height"}]), encoding="utf-8")
    (run / "operator_action_templates.json").write_text(
        json.dumps(
            [
                {
                    "rule_id": "rule_review",
                    "current_status": "rejected",
                    "recommended_action": "needs_source_research",
                    "support_gaps": ["operator_not_supported"],
                    "evidence_ids": ["ev_review"],
                    "cannot_promote": True,
                    "allowed_actions": ["needs_source_research", "defer"],
                }
            ]
        ),
        encoding="utf-8",
    )
    (run / "operator_review_actions.json").write_text(
        json.dumps({"artifact": "operator_review_actions.json", "actions": [], "writes_rule_status": False}),
        encoding="utf-8",
    )
    (run / "scenario_templates.json").write_text(
        json.dumps(
            [
                {
                    "scenario_template_id": "scenario_rule_height",
                    "rule_id": "rule_height",
                    "rule_object": "height",
                    "operator": "<=",
                    "threshold": 4.6,
                    "unit": "m",
                    "passing_example_value": 4.6,
                    "failing_example_value": 5.6,
                }
            ]
        ),
        encoding="utf-8",
    )
    (run / "evidence_navigation.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "source": "verified",
                        "rule_id": "rule_height",
                        "status": "verified",
                        "rule_object": "height",
                        "evidence_id": "ev_height",
                        "page": 2,
                        "quote": "height must not exceed 4.6 m",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (run / "operations_report.json").write_text(
        json.dumps(
            {
                "action_template_count": 1,
                "scenario_template_count": 1,
                "evidence_navigation_count": 1,
                "writes_rule_status": False,
                "writes_gis_contract": False,
                "verified_only_boundary_preserved": True,
            }
        ),
        encoding="utf-8",
    )
    (run / "retrieval_report.json").write_text(
        json.dumps({"evidence": [{"evidence_id": "ev1", "query": "height", "rank": 1, "quote": "height"}]}),
        encoding="utf-8",
    )

    assert discover_f1_outputs(tmp_path / "outputs" / "f1_runs") == [run]
    data = load_f1_output(run)

    assert data["guarded_repair_promotions"][0]["rule_id"] == "rule_height"
    assert command_center_cards(data)[0]["value"] == 1
    assert benchmark_gate_rows(data)[0]["status"] == "pass"
    assert workflow_rows(data)[0]["workflow"] == "Rule Explorer"
    assert pipeline_stage_rows(data)[2]["count"] == 2
    assert rule_rows(data, query="accessory")[0]["rule_id"] == "rule_height"
    assert rule_object_summary_rows(data)[0]["gis_ready"] == 1
    assert review_rows(data, status="rejected")[0]["rule_id"] == "rule_review"
    assert review_gap_rows(data)[0] == {"gap": "operator_not_supported", "count": 1}
    assert top_review_items(data)[0]["rule_id"] == "rule_review"
    assert evidence_rows(data)[0]["evidence_id"] == "ev_height"
    assert operator_action_template_rows(data)[0]["recommended_action"] == "needs_source_research"
    assert scenario_template_rows(data)[0]["rule_id"] == "rule_height"
    assert evidence_navigation_rows(data)[0]["evidence_id"] == "ev_height"
    saved = save_operator_review_action(data, rule_id="rule_review", action_type="defer", note="Hold for review.")
    assert saved["writes_rule_status"] is False
    assert operator_review_action_rows(data)[0]["rule_id"] == "rule_review"
    assert compliance_rows(data)[0]["scenario_id"] == "scenario_height"
    assert compliance_status_rows(data)[0]["status"] == "approved"
    assert artifact_rows(data)[0]["artifact"] == "f1_summary.json"
    assert evaluate_single_rule(manifest["verified_rules"][0], 4.5)["status"] == "passes_rule"
    assert evaluate_single_rule(manifest["verified_rules"][0], 4.7)["status"] == "fails_rule"
    assert evaluate_rule_set(manifest["verified_rules"], {"rule_height": 4.5})["decision"] == "approved"
    approval_answer = answer_artifact_question(data, "Can you approve my permit?")
    assert "cannot approve" in approval_answer["answer"]
    assert approval_answer["tone"] == "blocked"
    assert approval_answer["details"]
    gis_answer = answer_artifact_question(data, "Can GIS use review rules?")
    assert "Review rules cannot be used by GIS" in gis_answer["answer"]
    assert gis_answer["summary"] == "GIS can use verified rules only."
    rule_answer = answer_artifact_question(data, "What is the height?")
    assert rule_answer["summary"].startswith("I found")
    assert rule_answer["citations"] == ["ev_height"]
