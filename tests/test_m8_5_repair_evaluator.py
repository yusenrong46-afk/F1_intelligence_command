from __future__ import annotations

from burnaby_prototype.m8.extraction.rule_schema import SourceSpan
from burnaby_prototype.m8_5.repair_evaluation.repair_evaluation import evaluate_repair
from burnaby_prototype.m8_5.repair_evaluation.repair_scorecard import build_repair_scorecard
from burnaby_prototype.m8_5.tables.table_parser import parse_table_block
from burnaby_prototype.m8_5.tables.table_rule_mapper import map_table_derived_rules


def test_patch_changing_value_without_evidence_is_rejected() -> None:
    evaluation = evaluate_repair(
        original_rule={"rule_id": "rule_1", "value": "9.0", "unit": "m", "evidence_id": "ev_old"},
        patched_rule={"rule_id": "rule_1", "value": "10.7", "unit": "m"},
    )

    assert evaluation.safety_category == "insufficient_evidence"
    assert evaluation.verifier_ready is False
    assert "value" in evaluation.changed_fields
    assert evaluation.promotes_directly is False


def test_patch_adding_evidence_but_wrong_zone_is_not_verifier_ready() -> None:
    evidence = {
        "ev_wrong_zone": SourceSpan(
            city="burnaby_r1",
            document_id="R1.pdf",
            page=2,
            section_id="101.4",
            block_type="table_cell",
            text="R2 height 10.7 m",
            metadata={"zone": "R2"},
        )
    }

    evaluation = evaluate_repair(
        original_rule={"rule_id": "rule_2", "zone": "R1", "value": "9.0", "unit": "m"},
        patched_rule={"rule_id": "rule_2", "zone": "R1", "value": "10.7", "unit": "m", "evidence_id": "ev_wrong_zone"},
        evidence_by_id=evidence,
    )

    assert evaluation.safety_category == "unsupported_patch"
    assert evaluation.verifier_ready is False
    assert "zone_scope_mismatch" in evaluation.safety_findings


def test_patch_with_exact_row_column_lineage_is_verifier_ready() -> None:
    block = parse_table_block(
        city="burnaby_r1",
        zone="R1",
        document_id="R1.pdf",
        page=2,
        section_id="101.4",
        table_id="table_101_4",
        rows=[
            ["Zone", "Height"],
            ["R1", "10.7 m"],
        ],
    )
    table_rule = map_table_derived_rules(block)[0]
    evidence_id = table_rule.lineage.lineage_id

    evaluation = evaluate_repair(
        original_rule={"rule_id": "rule_3", "zone": "R1", "value": "9.0", "unit": "m"},
        patched_rule={
            "rule_id": "rule_3",
            "zone": "R1",
            "value": "10.7",
            "unit": "m",
            "evidence_id": evidence_id,
            "table_lineage": table_rule.lineage.to_dict(),
        },
        evidence_by_id={evidence_id: table_rule.source_span},
    )

    assert evaluation.safety_category == "safe_for_verifier"
    assert evaluation.verifier_ready is True
    assert evaluation.recommended_status == "ready_for_verifier"
    assert "table_lineage_present" in evaluation.safety_findings


def test_patch_introducing_exception_becomes_context_required() -> None:
    evaluation = evaluate_repair(
        original_rule={"rule_id": "rule_4", "value": "9.0", "unit": "m", "exception": ""},
        patched_rule={"rule_id": "rule_4", "value": "9.0", "unit": "m", "exception": "unless lane access is unavailable"},
    )

    assert evaluation.safety_category == "introduced_dependency"
    assert evaluation.recommended_status == "context_required"
    assert "exception_dependency_introduced" in evaluation.safety_findings


def test_patch_with_contradiction_becomes_review_needed() -> None:
    evidence = {
        "ev_conflict": SourceSpan(
            city="burnaby_r1",
            document_id="R1.pdf",
            page=2,
            section_id="101.4",
            block_type="clause",
            text="The maximum height is not 10.7 m for this condition.",
        )
    }

    evaluation = evaluate_repair(
        original_rule={"rule_id": "rule_5", "value": "9.0", "unit": "m"},
        patched_rule={"rule_id": "rule_5", "value": "10.7", "unit": "m", "evidence_id": "ev_conflict"},
        evidence_by_id=evidence,
    )

    assert evaluation.safety_category == "contradictory_evidence"
    assert evaluation.recommended_status == "review_needed"
    assert evaluation.verifier_ready is False


def test_evaluator_preserves_repair_history() -> None:
    history = ({"attempt_index": 1, "decision_status": "review_needed"},)

    evaluation = evaluate_repair(
        original_rule={"rule_id": "rule_6", "value": "9.0", "unit": "m"},
        patched_rule={"rule_id": "rule_6", "value": "9.0", "unit": "m"},
        repair_history=history,
    )

    assert evaluation.repair_history == history
    assert evaluation.to_dict()["repair_history"] == list(history)


def test_evaluator_cannot_promote_directly() -> None:
    evidence = {
        "ev_ok": SourceSpan(
            city="burnaby_r1",
            document_id="R1.pdf",
            page=2,
            section_id="101.4",
            block_type="clause",
            text="Maximum height 10.7 m.",
        )
    }

    evaluation = evaluate_repair(
        original_rule={"rule_id": "rule_7", "value": "9.0", "unit": "m"},
        patched_rule={"rule_id": "rule_7", "value": "10.7", "unit": "m", "evidence_id": "ev_ok"},
        evidence_by_id=evidence,
    )

    assert evaluation.verifier_ready is True
    assert evaluation.promotes_directly is False
    assert evaluation.recommended_status == "ready_for_verifier"
    assert evaluation.recommended_status != "verified"


def test_repair_scorecard_counts_categories() -> None:
    evaluations = [
        evaluate_repair(
            original_rule={"rule_id": "a", "value": "1"},
            patched_rule={"rule_id": "a", "value": "2"},
        ),
        evaluate_repair(
            original_rule={"rule_id": "b", "value": "1"},
            patched_rule={"rule_id": "b", "value": "1", "exception": "unless constrained"},
        ),
    ]

    scorecard = build_repair_scorecard(evaluations)

    assert scorecard["evaluation_count"] == 2
    assert scorecard["category_counts"]["insufficient_evidence"] == 1
    assert scorecard["category_counts"]["introduced_dependency"] == 1
