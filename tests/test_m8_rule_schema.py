import pytest

from burnaby_prototype.m8.extraction.rule_schema import (
    EvidencePointer,
    SourceSpan,
    StructuredRule,
    VerificationDecision,
)


def span() -> SourceSpan:
    return SourceSpan(
        city="burnaby_r1",
        document_id="source.pdf",
        page=1,
        section_id="101.3",
        block_type="clause",
        text="Maximum height is 10 m in the R1 district.",
    )


def test_m8_contract_defaults_fail_closed():
    rule = StructuredRule(
        rule_id="r1",
        city="burnaby_r1",
        zone="R1",
        rule_type="height",
        subject="building",
        value="10",
        unit="m",
    )
    decision = VerificationDecision(rule_id=rule.rule_id)

    assert rule.status == "review_needed"
    assert decision.status == "review_needed"


def test_promoted_rule_requires_source_evidence():
    with pytest.raises(ValueError):
        StructuredRule(
            rule_id="r1",
            city="burnaby_r1",
            zone="R1",
            rule_type="height",
            subject="building",
            value="10",
            unit="m",
            status="verified",
        )


def test_unknown_status_is_rejected():
    with pytest.raises(ValueError):
        VerificationDecision(rule_id="r1", status="maybe")


def test_json_roundtrip_preserves_evidence_pointer():
    source = span()
    pointer = EvidencePointer(
        evidence_id="ev1",
        span_id=source.span_id,
        field_name="value",
        quote="10 m",
        source_span=source,
    )
    rule = StructuredRule(
        rule_id="r1",
        city="burnaby_r1",
        zone="R1",
        rule_type="height",
        subject="building",
        comparator="<=",
        value="10",
        unit="m",
        evidence_pointers=(pointer,),
        status="verified",
    )

    payload = rule.to_dict()
    restored = StructuredRule.from_dict(payload)

    assert restored.status == "verified"
    assert restored.evidence_ids == ("ev1",)
    assert restored.evidence_pointers[0].source_span.text.startswith("Maximum height")
