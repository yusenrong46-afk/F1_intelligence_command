from burnaby_prototype.m8.extraction.rule_schema import SourceSpan, VerificationDecision
from burnaby_prototype.m8.repair.repair_loop import run_repair_loop
from burnaby_prototype.m8.repair.repair_judge import judge_repair
from burnaby_prototype.m8.retrieval.hybrid_index import HybridM8Index


def test_missing_evidence_patch_can_be_repaired_successfully():
    span = SourceSpan(
        city="burnaby_r1",
        document_id="source.pdf",
        page=1,
        text="Maximum height is 10 m.",
        metadata={"evidence_id": "ev_height"},
    )
    index = HybridM8Index([span])
    rule = {
        "rule_id": "r1",
        "rule_object": "height",
        "applies_to": "building",
        "operator": "<=",
        "value": "10",
        "unit": "m",
        "support_gaps": ["source_evidence_id_not_found"],
    }

    def verifier(candidate, history):
        status = "verified" if candidate.get("evidence_id") == "ev_height" else "review_needed"
        return VerificationDecision(rule_id="r1", status=status, evidence_ids=("ev_height",) if status == "verified" else ())

    result = run_repair_loop(rule, index=index, verifier=verifier, max_attempts=2)

    assert result["best_decision"].status == "repaired_successfully"
    assert result["attempts"][0].patch.changes["evidence_id"] == "ev_height"


def test_failed_repair_stops_with_budget_or_no_safe_patch():
    index = HybridM8Index([])
    rule = {"rule_id": "r1", "support_gaps": ["source_evidence_id_not_found"]}

    def verifier(candidate, history):
        return VerificationDecision(rule_id="r1", status="review_needed")

    result = run_repair_loop(rule, index=index, verifier=verifier, max_attempts=3)

    assert result["attempt_count"] == 1
    assert result["best_decision"].status == "review_needed"


def test_unit_mismatch_is_not_auto_patched():
    critique = judge_repair({"rule_id": "r1", "support_gaps": ["unit_not_found_in_evidence"]})

    assert critique.category == "unit_mismatch"


def test_conflicting_evidence_cannot_promote():
    span = SourceSpan(city="burnaby_r1", document_id="source.pdf", page=1, text="Height is not 10 m.", metadata={"evidence_id": "ev1"})
    index = HybridM8Index([span])
    rule = {"rule_id": "r1", "value": "10", "support_gaps": ["column_value_mismatch"]}

    def verifier(candidate, history):
        return VerificationDecision(rule_id="r1", status="review_needed")

    result = run_repair_loop(rule, index=index, verifier=verifier, max_attempts=1)

    assert result["best_decision"].status == "review_needed"
    assert result["attempts"][0].patch.is_empty
