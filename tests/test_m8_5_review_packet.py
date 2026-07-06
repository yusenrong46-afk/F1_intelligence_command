from __future__ import annotations

import pytest

from burnaby_prototype.m8.extraction.rule_schema import SourceSpan
from burnaby_prototype.m8_5.dependencies.dependency_graph import RuleDependency
from burnaby_prototype.m8_5.repair_evaluation.repair_evaluation import evaluate_repair
from burnaby_prototype.m8_5.review.review_packet import ReviewPacket
from burnaby_prototype.m8_5.review.review_state import ReviewState
from burnaby_prototype.m8_5.review.reviewer_actions import ReviewerAction


def _source_span() -> SourceSpan:
    return SourceSpan(
        city="burnaby_r1",
        document_id="R1.pdf",
        page=2,
        section_id="101.4",
        block_type="table_cell",
        text="Maximum height 10.7 m",
        metadata={"evidence_id": "ev_height"},
    )


def _packet() -> ReviewPacket:
    dependency = RuleDependency(
        source_rule_id="rule_1",
        dependency_type="cross_reference",
        target_reference="Section 6.4",
        status="unresolved",
        reason="Referenced section is missing.",
    )
    repair = evaluate_repair(
        original_rule={"rule_id": "rule_1", "value": "9.0", "unit": "m"},
        patched_rule={"rule_id": "rule_1", "value": "10.7", "unit": "m", "evidence_id": "ev_height"},
        evidence_by_id={"ev_height": _source_span()},
    )
    return ReviewPacket(
        rule_id="rule_1",
        current_status="review_needed",
        failure_reason="value needs source confirmation",
        candidate_rule_fields={"rule_object": "height", "value": "10.7", "unit": "m"},
        evidence_spans=(_source_span(),),
        dependency_graph_slice=(dependency,),
        repair_evaluations=(repair,),
        recommended_reviewer_action="approve_evidence_link",
        reviewer_notes=("initial note",),
    )


def test_reviewer_cannot_directly_verify() -> None:
    with pytest.raises(ValueError, match="cannot directly verify"):
        ReviewerAction(
            rule_id="rule_1",
            action_type="mark_verified",
            reviewer_note="looks correct",
        )


def test_approved_evidence_triggers_verifier_rerun_request() -> None:
    state = ReviewState(packet=_packet())
    action = ReviewerAction(
        rule_id="rule_1",
        action_type="approve_evidence_link",
        evidence_ids=("ev_height",),
        reviewer_note="Evidence text supports the changed height value.",
    )

    updated = state.apply_action(action)
    request = updated.verifier_rerun_requests[0]

    assert request.rule_id == "rule_1"
    assert request.reason == "reviewer_action_requires_verifier_rerun"
    assert request.approved_evidence_ids == ("ev_height",)
    assert request.status == "pending"
    assert updated.current_status == "review_needed"


def test_rejected_evidence_keeps_rule_review_needed() -> None:
    state = ReviewState(packet=_packet())
    action = ReviewerAction(
        rule_id="rule_1",
        action_type="reject_evidence_link",
        evidence_ids=("ev_height",),
        reviewer_note="Evidence belongs to the wrong scope.",
    )

    updated = state.apply_action(action)

    assert updated.current_status == "review_needed"
    assert updated.verifier_rerun_requests == ()
    assert updated.actions[0].action_type == "reject_evidence_link"


def test_resolved_dependency_can_be_passed_to_verifier() -> None:
    state = ReviewState(packet=_packet())
    action = ReviewerAction(
        rule_id="rule_1",
        action_type="mark_dependency_resolved",
        dependency_ids=("dep_section_6_4",),
        reviewer_note="Section 6.4 source was attached.",
    )

    updated = state.apply_action(action)
    request = updated.verifier_rerun_requests[0]

    assert request.resolved_dependency_ids == ("dep_section_6_4",)
    assert request.candidate_rule_fields["value"] == "10.7"
    assert updated.current_status == "review_needed"


def test_reviewer_note_is_preserved() -> None:
    state = ReviewState(packet=_packet())
    action = ReviewerAction(
        rule_id="rule_1",
        action_type="mark_needs_legal_review",
        reviewer_note="Planner should review the exception manually.",
    )

    updated = state.apply_action(action)

    assert updated.actions[0].reviewer_note == "Planner should review the exception manually."
    assert "Planner should review" in updated.packet.reviewer_notes[-1]


def test_review_packet_serializes_to_json() -> None:
    packet = _packet()

    restored = ReviewPacket.from_dict(packet.to_dict())

    assert restored.rule_id == packet.rule_id
    assert restored.current_status == "review_needed"
    assert restored.evidence_spans[0].text == "Maximum height 10.7 m"
    assert restored.dependency_graph_slice[0].dependency_type == "cross_reference"
    assert restored.repair_evaluations[0].safety_category == "safe_for_verifier"


def test_review_packet_contains_dashboard_display_context() -> None:
    context = _packet().dashboard_context()

    assert context["rule_id"] == "rule_1"
    assert context["current_status"] == "review_needed"
    assert context["evidence_count"] == 1
    assert context["dependency_count"] == 1
    assert context["repair_evaluation_count"] == 1
    assert context["recommended_reviewer_action"] == "approve_evidence_link"
