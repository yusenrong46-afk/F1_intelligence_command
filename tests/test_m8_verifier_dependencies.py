from burnaby_prototype.m8.extraction.rule_schema import EvidencePointer, SourceSpan, StructuredRule
from burnaby_prototype.m8.verification.m8_verifier import verify_structured_rule


def pointer(text: str, evidence_id: str = "ev1") -> EvidencePointer:
    span = SourceSpan(city="burnaby_r1", document_id="source.pdf", page=1, text=text, metadata={"evidence_id": evidence_id})
    return EvidencePointer(evidence_id=evidence_id, span_id=span.span_id, field_name="rule", quote=text, source_span=span)


def test_verified_rule_with_unresolved_overlay_becomes_context_required():
    rule = StructuredRule(
        rule_id="r1",
        city="burnaby_r1",
        zone="R1",
        rule_type="height",
        subject="building",
        comparator="<=",
        value="10",
        unit="m",
        conditions=("subject to heritage overlay",),
        evidence_pointers=(pointer("Maximum height is 10 m subject to heritage overlay."),),
        status="verified",
        raw={"verification_decision": "verified"},
    )

    decision = verify_structured_rule(rule)

    assert decision.status == "context_required"
    assert "heritage_dependency" in decision.unresolved_dependencies


def test_repaired_history_can_label_success():
    from burnaby_prototype.m8.extraction.rule_schema import RepairAttempt, RepairCritique, RepairPatch

    critique = RepairCritique(rule_id="r1", category="missing_evidence", reason="missing")
    patch = RepairPatch(rule_id="r1", changes={"evidence_id": "ev1"}, category="missing_evidence")
    attempt = RepairAttempt(attempt_index=1, critique=critique, query="height 10 m", patch=patch)
    rule = StructuredRule(
        rule_id="r1",
        city="burnaby_r1",
        zone="R1",
        rule_type="height",
        subject="building",
        comparator="<=",
        value="10",
        unit="m",
        evidence_pointers=(pointer("Maximum height is 10 m."),),
        status="verified",
        raw={"verification_decision": "verified"},
    )

    decision = verify_structured_rule(rule, repair_history=(attempt,))

    assert decision.status == "repaired_successfully"


def test_conflicting_span_rejects_candidate():
    rule = StructuredRule(
        rule_id="r1",
        city="burnaby_r1",
        zone="R1",
        rule_type="height",
        subject="building",
        comparator="<=",
        value="10",
        unit="m",
        evidence_pointers=(pointer("The height is not 10 m."),),
        status="review_needed",
        raw={"support_gaps": ["column_value_mismatch"], "verification_decision": "review_needed"},
    )

    assert verify_structured_rule(rule).status == "rejected"


def test_no_evidence_remains_review_needed():
    rule = StructuredRule(rule_id="r1", city="burnaby_r1", zone="R1", rule_type="height", subject="building")

    assert verify_structured_rule(rule).status == "review_needed"
