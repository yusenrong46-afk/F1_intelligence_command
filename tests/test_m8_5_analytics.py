import json

import pytest

from burnaby_prototype.m8.extraction.rule_schema import SourceSpan
from burnaby_prototype.m8_5.analytics import (
    compare_m8_to_m8_5,
    dependency_metrics,
    metric_state,
    repair_quality_metrics,
    status_metrics,
    table_metrics,
)
from burnaby_prototype.m8_5.dependencies import DependencyGraph, RuleDependency
from burnaby_prototype.m8_5.repair_evaluation import RepairEvaluation


def test_status_metrics_keep_context_required_separate_from_review_needed():
    metrics = status_metrics([
        {"rule_id": "r1", "status": "verified"},
        {"rule_id": "r2", "status": "repaired_successfully"},
        {"rule_id": "r3", "status": "context_required"},
        {"rule_id": "r4", "status": "review_needed"},
    ])

    assert metrics["verified_like_count"] == 2
    assert metrics["context_required_count"] == 1
    assert metrics["review_needed_count"] == 1


def test_table_metrics_count_candidates_without_promoting_them():
    metrics = table_metrics(
        table_blocks=[
            {
                "cells": [{"cell_id": "c1"}, {"cell_id": "c2"}],
                "diagnostics": [{"code": "blank_cell"}],
            }
        ],
        table_derived_rules=[
            {"rule_id": "t1", "status": "candidate_only", "verifier_ready": True},
            {"rule_id": "t2", "status": "candidate_only", "verifier_ready": False},
        ],
    )

    assert metrics["table_derived_rules_count"] == 2
    assert metrics["table_derived_verified_count"] == 0
    assert metrics["table_derived_review_count"] == 2
    assert metrics["table_derived_verifier_ready_count"] == 1
    assert metrics["table_diagnostic_counts"] == {"blank_cell": 1}


def test_dependency_metrics_count_statuses_and_types():
    graph = DependencyGraph([
        RuleDependency(
            source_rule_id="r1",
            dependency_type="cross_reference",
            target_reference="Section 6.4",
            status="unresolved",
        ),
        RuleDependency(
            source_rule_id="r2",
            dependency_type="definition",
            target_reference="height",
            status="resolved",
            evidence_ids=("ev1",),
        ),
    ])

    metrics = dependency_metrics(graph)

    assert metrics["dependency_total_count"] == 2
    assert metrics["dependency_unresolved_count"] == 1
    assert metrics["dependency_resolved_count"] == 1
    assert metrics["dependency_type_metrics"]["cross_reference"]["unresolved"] == 1


def test_repair_quality_metrics_never_counts_direct_promotion():
    evaluation = RepairEvaluation(
        rule_id="r1",
        original_failure="missing scope",
        changed_fields=("evidence_id",),
        safety_category="safe_for_verifier",
        safety_findings=(),
        verifier_ready=True,
        recommended_status="ready_for_verifier",
    )

    metrics = repair_quality_metrics([evaluation])

    assert metrics["repair_evaluations_count"] == 1
    assert metrics["verifier_ready_patches_count"] == 1
    assert metrics["direct_promotion_count"] == 0


def test_m8_to_m8_5_comparison_serializes_and_labels_unrun_metrics():
    span = SourceSpan(
        city="burnaby_r1",
        document_id="zoning.pdf",
        page=1,
        section_id="101",
        block_type="text",
        text="Maximum height is 10.7 m.",
        metadata={"evidence_id": "ev1"},
    )
    comparison = compare_m8_to_m8_5(
        city="burnaby_r1",
        m8_comparison={
            "m8": {
                "verified_like_count": 1,
                "false_verified_count": 0,
                "false_approval_count": 0,
            },
            "safety": {"m7_safety_preserved": True},
        },
        m8_summary={},
        m8_5_decisions=[
            {"rule_id": "r1", "status": "verified"},
            {"rule_id": "r2", "status": "context_required"},
        ],
        table_blocks=[],
        table_derived_rules=[
            {
                "rule_id": "t1",
                "status": "candidate_only",
                "verifier_ready": True,
                "lineage": {"lineage_id": "l1"},
            }
        ],
        dependency_graph=DependencyGraph([
            RuleDependency(
                source_rule_id="r2",
                dependency_type="cross_reference",
                target_reference="Section 6.4",
                status="unresolved",
            )
        ]),
        repair_evaluations=[],
        review_packets=[{"rule_id": "r2"}],
        structured_rules=[
            {
                "rule_id": "r1",
                "rule_type": "height",
                "evidence_pointers": [{"source_span": span.to_dict()}],
            },
            {"rule_id": "r2", "rule_type": "setback"},
        ],
    )

    assert comparison["m8_5"]["verified_like_count"] == 1
    assert comparison["m8_5"]["context_required_count"] == 1
    assert comparison["m8_5"]["table_derived_rules_count"] == 1
    assert comparison["m8_5"]["dependency_total_count"] == 1
    assert comparison["m8_5"]["metric_states"]["m8_5_chatbot_gold"]["state"] == "not_yet_run"
    json.dumps(comparison)


def test_metric_state_rejects_unknown_state():
    with pytest.raises(ValueError):
        metric_state(1, state="pretend")
