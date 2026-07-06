from __future__ import annotations

import pytest

from burnaby_prototype.m8.extraction.rule_schema import SourceSpan
from burnaby_prototype.m8_5.llm_repair import (
    FixtureRepairClient,
    LLMRepairParseError,
    parse_llm_repair_payload,
    run_local_table_proof_repair,
    run_llm_repair,
    validate_llm_repair_payload,
)


def test_llm_repair_parser_rejects_unknown_fields_and_direct_verification_claims() -> None:
    with pytest.raises(LLMRepairParseError):
        parse_llm_repair_payload(
            {
                "action": "patch",
                "changes": {"evidence_id": "ev_1"},
                "field_proofs": [],
                "confidence": 1.0,
                "risk_flags": [],
                "no_patch_reason": "",
                "recommended_status": "verified",
            }
        )

    with pytest.raises(LLMRepairParseError):
        parse_llm_repair_payload(
            {
                "action": "patch",
                "changes": {"status": "verified"},
                "field_proofs": [],
                "confidence": 1.0,
                "risk_flags": [],
                "no_patch_reason": "",
            }
        )


def test_field_proof_validator_accepts_exact_value_unit_operator_evidence() -> None:
    evidence_by_id = {"ev_height": _span("ev_height", "R1 maximum building height 10.7 m")}
    payload = parse_llm_repair_payload(
        {
            "action": "patch",
            "changes": {
                "evidence_id": "ev_height",
                "operator": "<=",
                "value": "10.7",
                "unit": "m",
            },
            "field_proofs": [
                _proof("evidence_id", "ev_height", "R1 maximum building height 10.7 m"),
                _proof("operator", "ev_height", "R1 maximum building height 10.7 m"),
                _proof("value", "ev_height", "R1 maximum building height 10.7 m"),
                _proof("unit", "ev_height", "R1 maximum building height 10.7 m"),
            ],
            "confidence": 0.9,
            "risk_flags": [],
            "no_patch_reason": "",
        }
    )

    validation = validate_llm_repair_payload(payload, case=_case(), evidence_by_id=evidence_by_id)

    assert validation["accepted"] is True
    assert validation["findings"] == []
    assert validation["proof_completion_rate"] == 1.0


def test_field_proof_validator_rejects_related_but_incomplete_evidence() -> None:
    evidence_by_id = {"ev_height": _span("ev_height", "R1 maximum building height 10.7 m")}
    payload = parse_llm_repair_payload(
        {
            "action": "patch",
            "changes": {"value": "12.0"},
            "field_proofs": [_proof("value", "ev_height", "R1 maximum building height 10.7 m")],
            "confidence": 0.9,
            "risk_flags": [],
            "no_patch_reason": "",
        }
    )

    validation = validate_llm_repair_payload(payload, case=_case(), evidence_by_id=evidence_by_id)

    assert validation["accepted"] is False
    assert "value_not_supported_by_field_proof" in validation["findings"]


def test_exception_change_requires_explicit_exception_wording() -> None:
    evidence_by_id = {"ev_height": _span("ev_height", "R1 maximum building height 10.7 m")}
    payload = parse_llm_repair_payload(
        {
            "action": "patch",
            "changes": {"exception": "heritage resource"},
            "field_proofs": [_proof("exception", "ev_height", "R1 maximum building height 10.7 m")],
            "confidence": 0.9,
            "risk_flags": [],
            "no_patch_reason": "",
        }
    )

    validation = validate_llm_repair_payload(payload, case=_case(), evidence_by_id=evidence_by_id)

    assert validation["accepted"] is False
    assert "exception_not_supported_by_field_proof" in validation["findings"]
    assert "exception_not_explicitly_supported" in validation["findings"]


def test_run_llm_repair_turns_valid_fixture_patch_into_repair_attempt() -> None:
    evidence_by_id = {"ev_height": _span("ev_height", "R1 maximum building height 10.7 m")}
    client = FixtureRepairClient(
        {
            "rule_height": {
                "action": "patch",
                "changes": {"evidence_id": "ev_height", "operator": "<="},
                "field_proofs": [
                    _proof("evidence_id", "ev_height", "R1 maximum building height 10.7 m"),
                    _proof("operator", "ev_height", "R1 maximum building height 10.7 m"),
                ],
                "confidence": 1.0,
                "risk_flags": [],
                "no_patch_reason": "",
            }
        }
    )

    report = run_llm_repair(cases=[_case()], evidence_by_id=evidence_by_id, client=client, dry_run=False)

    assert report["metrics"]["llm_repair_case_count"] == 1
    assert report["metrics"]["llm_repair_safe_patch_count"] == 1
    assert report["attempts"][0]["metadata"]["repair_source"] == "llm_repair"


def test_local_table_proof_repair_accepts_safe_scope_refinement_only() -> None:
    evidence_by_id = {
        "ev_table_4": _span(
            "ev_table_4",
            "dwelling_units | Small-Scale Multi-Unit 3 to 4 Units | "
            "Permitted Dwelling Units (including secondary suites) | 3 to 4 Units",
        )
    }
    cases = [
        {
            **_case(),
            "rule_id": "rule_dwelling_units",
            "candidate_fields": {
                **_case()["candidate_fields"],
                "rule_object": "dwelling_units",
                "applies_to": "small-scale multi-unit housing",
                "operator": "",
                "value": "4",
                "unit": "units",
                "condition": "Total Dwelling Units on a Lot",
            },
        },
        {
            **_case(),
            "rule_id": "rule_heritage_scope",
            "candidate_fields": {
                **_case()["candidate_fields"],
                "rule_object": "dwelling_units",
                "applies_to": "lots on the Community Heritage Register",
                "operator": "",
                "value": "4",
                "unit": "units",
                "condition": "Section 219 Covenant",
            },
        },
    ]
    candidates = [
        {
            "candidate_id": "m7_matrix_4_units",
            "source_stream": "native_m7_matrix",
            "rule_object": "dwelling_units",
            "applies_to": "Small-Scale Multi-Unit 3 to 4 Units",
            "value": "4",
            "unit": "units",
            "evidence_id": "ev_table_4",
        }
    ]

    report = run_local_table_proof_repair(
        cases=cases,
        evidence_by_id=evidence_by_id,
        m7_candidates=candidates,
    )

    assert report["metrics"]["llm_repair_safe_patch_count"] == 1
    assert report["attempts"][0]["metadata"]["repair_source"] == "local_table_proof_repair"
    assert report["attempts"][0]["patch"]["changes"] == {
        "evidence_id": "ev_table_4",
        "applies_to": "Small-Scale Multi-Unit 3 to 4 Units",
        "condition": "",
    }


def _case() -> dict:
    return {
        "case_id": "case_1",
        "rule_id": "rule_height",
        "current_status": "review_needed",
        "support_gaps": ["operator_not_supported"],
        "candidate_fields": {
            "rule_object": "height",
            "constraint_scope": "height",
            "applies_to": "building",
            "operator": "<=",
            "value": "10.7",
            "unit": "m",
            "condition": "",
            "exception": "",
            "evidence_id": "ev_old",
        },
        "evidence_snippets": [
            {
                "evidence_id": "ev_height",
                "span_id": "span_ev_height",
                "quote": "R1 maximum building height 10.7 m",
            }
        ],
    }


def _proof(field: str, evidence_id: str, quote: str) -> dict:
    return {
        "field": field,
        "evidence_id": evidence_id,
        "span_id": f"span_{evidence_id}",
        "quote": quote,
        "rationale": "quote supports field",
    }


def _span(evidence_id: str, text: str) -> SourceSpan:
    return SourceSpan(
        city="burnaby_r1",
        document_id="R1.pdf",
        page=2,
        section_id="101.4",
        block_type="clause",
        char_start=0,
        char_end=len(text),
        text=text,
        metadata={"evidence_id": evidence_id},
    )
