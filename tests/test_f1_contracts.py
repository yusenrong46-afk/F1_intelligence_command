from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import validate

from burnaby_prototype.bylaw_command_center import (
    ARTIFACT_SCHEMA_VERSION,
    CANONICAL_ARTIFACT_NAMES,
    CandidateRule,
    ChatAnswer,
    ComplianceDecision,
    ComplianceScenario,
    RepairPatch,
    SourceDocument,
    VerificationDecision,
    artifact_manifest,
    build_chatbot_eval_outputs,
    build_command_center_app_outputs,
    build_command_center_outputs,
    evaluate_benchmark_outputs,
    build_document_intelligence,
    build_document_intelligence_from_intermediate,
    build_candidate_rules_from_retrieval,
    build_gis_compliance_outputs,
    build_guarded_repair_rerun_outputs,
    build_model_chatbot_eval_outputs,
    build_model_chatbot_redteam_outputs,
    build_retrieval_report,
    build_repair_review_outputs,
    build_source_registry,
    build_verification_outputs,
    evaluate_compliance_scenario,
)
from burnaby_prototype.bylaw_command_center.document_intelligence import _ingest_with_pypdf


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
BURNABY_SOURCE_PDF = ROOT / "data" / "bylaws" / "burnaby_r1" / "source.pdf"
# The bylaw PDF is gitignored (URL + SHA-256 are committed in provenance.json).
needs_burnaby_pdf = pytest.mark.skipif(
    not BURNABY_SOURCE_PDF.exists(), reason="source PDF not fetched (run make fetch-sources)"
)
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_f1_checkpoint import build_checkpoint_summary  # noqa: E402


def test_f1_artifact_manifest_matches_schema() -> None:
    manifest = artifact_manifest(city="burnaby_r1", run_id="checkpoint_0", source_id="burnaby_zoning")
    schema = json.loads((ROOT / "schemas" / "f1_artifact_manifest.schema.json").read_text(encoding="utf-8"))

    validate(instance=manifest, schema=schema)

    assert manifest["schema_version"] == ARTIFACT_SCHEMA_VERSION
    assert manifest["artifact_names"] == list(CANONICAL_ARTIFACT_NAMES)
    assert "f1_summary.json" in manifest["artifact_names"]


@needs_burnaby_pdf
def test_f1_source_registry_matches_schema_for_burnaby() -> None:
    registry = build_source_registry(city_key="burnaby_r1", run_id="checkpoint_1_source_registry", root=ROOT)
    schema = json.loads((ROOT / "schemas" / "f1_source_registry.schema.json").read_text(encoding="utf-8"))

    validate(instance=registry, schema=schema)

    assert registry["validation"]["status"] == "pass"
    assert registry["validation"]["sha256_matches"] is True
    assert registry["documents"][0]["status"] == "registered"
    assert registry["documents"][0]["hash_verified"] is True


def test_f1_source_registry_flags_hash_mismatch(tmp_path: Path) -> None:
    root = tmp_path
    city = "demo_city"
    (root / "configs").mkdir()
    (root / "data" / "bylaws" / city).mkdir(parents=True)
    source = root / "data" / "bylaws" / city / "source.pdf"
    source.write_bytes(b"demo")
    (root / "configs" / f"{city}.json").write_text(
        json.dumps({"city": "Demo", "source_document": "Demo Bylaw", "source_url": "https://example.test/demo.pdf"}),
        encoding="utf-8",
    )
    (root / "data" / "bylaws" / city / "provenance.json").write_text(
        json.dumps(
            {
                "url": "https://example.test/demo.pdf",
                "sha256": "0" * 64,
                "bytes": 4,
                "page_count": 1,
            }
        ),
        encoding="utf-8",
    )

    registry = build_source_registry(city_key=city, run_id="r1", root=root)

    assert registry["validation"]["status"] == "needs_attention"
    assert registry["validation"]["sha256_matches"] is False
    assert registry["documents"][0]["status"] == "hash_mismatch"


def test_f1_document_intelligence_from_intermediate_emits_blocks_and_spans() -> None:
    registry = build_source_registry(city_key="burnaby_r1", run_id="checkpoint_2_document_intelligence", root=ROOT)
    source_document = registry["documents"][0]
    payload = build_document_intelligence_from_intermediate(
        intermediate={
            "ingest_backend": "fixture",
            "pages": [
                {
                    "page_number": 1,
                    "text": "101.1 Maximum height is 10.7 m.",
                    "blocks": [{"kind": "paragraph", "text": "101.1 Maximum height is 10.7 m."}],
                    "tables": [
                        {
                            "title_guess": "Height Table",
                            "rows": [["Rule", "Value"], ["Height", "10.7 m"]],
                        }
                    ],
                }
            ],
        },
        source_document=SourceDocument(**source_document),
        city_key="burnaby_r1",
        run_id="checkpoint_2_document_intelligence",
    )

    assert payload["summary"]["page_count"] == 1
    assert payload["summary"]["document_block_count"] == 3
    assert payload["summary"]["source_span_count"] == 3
    assert payload["summary"]["table_block_count"] == 1
    assert all(span["schema_version"] == ARTIFACT_SCHEMA_VERSION for span in payload["source_spans"])


@needs_burnaby_pdf
def test_f1_document_intelligence_fallback_parses_real_burnaby_pdf() -> None:
    registry = build_source_registry(city_key="burnaby_r1", run_id="checkpoint_2_document_intelligence", root=ROOT)
    payload = build_document_intelligence(
        source_registry=registry,
        run_id="checkpoint_2_document_intelligence",
        root=ROOT,
        prefer_docling=False,
    )

    assert payload["summary"]["page_count"] == 7
    assert payload["summary"]["document_block_count"] > 0
    assert payload["summary"]["source_span_count"] > 0
    assert payload["ingest_backend"] in {"pypdf", "pdfplumber"}


def test_f1_pypdf_fallback_respects_scoped_page_ranges(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    pdf_path = tmp_path / "source.pdf"
    writer = PdfWriter()
    for _ in range(5):
        writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as handle:
        writer.write(handle)

    payload = _ingest_with_pypdf(pdf_path, page_ranges=[(2, 3)])

    assert [page["page_number"] for page in payload["pages"]] == [2, 3]


def test_f1_proof_rag_returns_evidence_from_source_spans() -> None:
    spans = [
        {
            "span_id": "span_height",
            "page": 1,
            "section_id": "101.1",
            "block_type": "paragraph",
            "text": "The maximum building height is 10.7 m.",
        },
        {
            "span_id": "span_setback",
            "page": 2,
            "section_id": "101.2",
            "block_type": "paragraph",
            "text": "The minimum rear yard setback is 6.0 m.",
        },
    ]

    report = build_retrieval_report(
        source_spans=spans,
        city_key="burnaby_r1",
        run_id="checkpoint_3_proof_rag",
        queries=["maximum height", "minimum setback"],
        top_k=1,
    )

    assert report["summary"]["retrieval_quality_status"] == "pass"
    assert report["summary"]["total_hit_count"] == 2
    assert report["evidence"][0]["span_id"] == "span_height"
    assert "value" in report["evidence"][0]["supports_fields"]
    assert report["evidence"][0]["retrieval_method"] == "lexical_bm25_rrf"


def test_f1_proof_rag_marks_missing_hits_needs_attention() -> None:
    report = build_retrieval_report(
        source_spans=[{"span_id": "span_height", "text": "Maximum height is 10.7 m."}],
        city_key="burnaby_r1",
        run_id="checkpoint_3_proof_rag",
        queries=["minimum setback"],
    )

    assert report["summary"]["retrieval_quality_status"] == "needs_attention"
    assert report["summary"]["queries_with_hits"] == 0


def test_f1_structured_extraction_proposes_review_needed_candidates_only() -> None:
    retrieval_report = build_retrieval_report(
        source_spans=[
            {
                "span_id": "span_height",
                "page": 1,
                "section_id": "101.1",
                "block_type": "paragraph",
                "text": "The maximum building height is 10.7 m.",
            },
            {
                "span_id": "span_setback",
                "page": 2,
                "section_id": "101.2",
                "block_type": "paragraph",
                "text": "The minimum rear yard setback is 6.0 m.",
            },
        ],
        city_key="burnaby_r1",
        run_id="checkpoint_4_structured_extraction",
        queries=["maximum height", "minimum setback"],
        top_k=1,
    )

    payload = build_candidate_rules_from_retrieval(
        retrieval_report=retrieval_report,
        city_key="burnaby_r1",
        run_id="checkpoint_4_structured_extraction",
    )

    assert payload["extraction_report"]["candidate_count"] == 2
    assert payload["extraction_report"]["promoted_count"] == 0
    assert payload["extraction_report"]["all_candidates_review_needed"] is True
    assert {rule["status"] for rule in payload["candidate_rules"]} == {"review_needed"}
    assert payload["candidate_rules"][0]["evidence_ids"]
    assert "field_citations" in payload["candidate_rules"][0]["raw"]


def test_f1_structured_extraction_prefers_rule_family_units() -> None:
    retrieval_report = {
        "queries": [
            {
                "query": "maximum height",
                "hits": [
                    {
                        "evidence_id": "ev_height",
                        "span_id": "span_height",
                        "page": 1,
                        "section_id": "101.4",
                        "quote": "Permitted dwelling units 6 Units. Maximum Height Front Principal 9.5 m.",
                    }
                ],
            }
        ]
    }

    payload = build_candidate_rules_from_retrieval(
        retrieval_report=retrieval_report,
        city_key="burnaby_r1",
        run_id="checkpoint_4_structured_extraction",
    )

    assert payload["candidate_rules"][0]["value"] == "9.5"
    assert payload["candidate_rules"][0]["unit"] == "m"


def test_f1_verification_outputs_fail_closed_for_incomplete_candidates() -> None:
    retrieval_report = build_retrieval_report(
        source_spans=[
            {
                "span_id": "span_height",
                "page": 1,
                "section_id": "101.1",
                "block_type": "paragraph",
                "text": "A building shall not exceed 9.5 m in height.",
            }
        ],
        city_key="burnaby_r1",
        run_id="checkpoint_5_verification",
        queries=["maximum height"],
        top_k=1,
    )
    extraction = build_candidate_rules_from_retrieval(
        retrieval_report=retrieval_report,
        city_key="burnaby_r1",
        run_id="checkpoint_5_verification",
    )

    verification = build_verification_outputs(
        candidate_rules=extraction["candidate_rules"],
        city_key="burnaby_r1",
        run_id="checkpoint_5_verification",
    )

    assert verification["verification_report"]["false_verified_count"] == 0
    assert verification["verification_report"]["verified_count"] == 0
    assert verification["review_queue"]
    assert verification["verified_rules"] == []
    assert verification["verification_decisions"][0]["status"] in {"context_required", "review_needed", "rejected"}


def test_f1_repair_review_outputs_do_not_rerun_without_proof_patch() -> None:
    review_queue = [
        {
            "rule_id": "rule_height",
            "status": "context_required",
            "candidate": {"rule_type": "height"},
            "evidence_ids": ["ev_height"],
            "support_gaps": [],
            "unresolved_dependencies": ["applies_to_missing"],
        },
        {
            "rule_id": "rule_units",
            "status": "rejected",
            "candidate": {"rule_type": "dwelling_units"},
            "evidence_ids": ["ev_units"],
            "support_gaps": ["operator_not_supported"],
            "unresolved_dependencies": [],
        },
    ]
    retrieval_report = {"queries": [{"query": "maximum height"}, {"query": "dwelling units"}]}

    payload = build_repair_review_outputs(
        review_queue=review_queue,
        retrieval_report=retrieval_report,
        city_key="burnaby_r1",
        run_id="checkpoint_6_repair_review",
    )

    assert len(payload["repair_attempts"]) == 2
    assert len(payload["review_packets"]) == 2
    assert {attempt["action"] for attempt in payload["repair_attempts"]} == {"review_only"}
    assert {attempt["verifier_rerun_ready"] for attempt in payload["repair_attempts"]} == {False}
    assert payload["repair_rerun_report"]["attempt_count"] == 0
    assert payload["repair_rerun_report"]["guarded_repair_promotion_count"] == 0
    assert payload["repair_rerun_report"]["false_verified_count"] == 0


def test_f1_guarded_repair_promotes_only_after_verifier_rerun() -> None:
    candidate = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "rule_id": "rule_height",
        "city": "burnaby_r1",
        "rule_type": "height",
        "rule_object": "height",
        "constraint_scope": "maximum height",
        "applies_to": "",
        "operator": "<=",
        "value": "4.6",
        "unit": "m",
        "evidence_ids": ["ev_height"],
        "status": "review_needed",
        "raw": {
            "field_citations": {
                field: {
                    "evidence_id": "ev_height",
                    "span_id": "span_height",
                    "page": 1,
                    "section_id": "101.1",
                    "quote": "An accessory structure shall not exceed 4.6 m in height.",
                }
                for field in ("rule_object", "operator", "constraint_scope")
            }
            | {
                "value": {
                    "evidence_id": "ev_height",
                    "span_id": "span_height",
                    "page": 1,
                    "section_id": "101.1",
                    "quote": "4.6 m",
                },
                "unit": {
                    "evidence_id": "ev_height",
                    "span_id": "span_height",
                    "page": 1,
                    "section_id": "101.1",
                    "quote": "4.6 m",
                },
            }
        },
    }
    review_queue = [
        {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "rule_id": "rule_height",
            "status": "context_required",
            "reason": "field evidence is present, but applicability or scope needs more context",
            "support_gaps": [],
            "unresolved_dependencies": ["applies_to_missing"],
            "evidence_ids": ["ev_height"],
            "candidate": candidate,
        }
    ]

    payload = build_guarded_repair_rerun_outputs(
        review_queue=review_queue,
        retrieval_report={"queries": []},
        city_key="burnaby_r1",
        run_id="checkpoint_7_guarded_repair",
    )

    assert payload["repair_rerun_report"]["attempt_count"] == 1
    assert payload["repair_rerun_report"]["guarded_repair_promotion_count"] == 1
    assert payload["verification_decisions"][0]["status"] == "repaired_successfully"
    assert payload["verified_rules"][0]["applies_to"] == "accessory structure"
    assert payload["review_queue"] == []


def test_f1_guarded_repair_blocks_outside_release_contract() -> None:
    candidate = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "rule_id": "rule_floor_area",
        "city": "burnaby_r1",
        "rule_type": "floor_area",
        "rule_object": "floor_area",
        "constraint_scope": "floor area",
        "applies_to": "",
        "operator": ">=",
        "value": "27",
        "unit": "m2",
        "evidence_ids": ["ev_floor"],
        "status": "review_needed",
        "raw": {
            "field_citations": {
                field: {
                    "evidence_id": "ev_floor",
                    "span_id": "span_floor",
                    "page": 4,
                    "section_id": "101.5",
                    "quote": "Each living unit shall have a minimum floor area of 27 m 2.",
                }
                for field in ("rule_object", "operator", "constraint_scope")
            }
            | {
                "value": {
                    "evidence_id": "ev_floor",
                    "span_id": "span_floor",
                    "page": 4,
                    "section_id": "101.5",
                    "quote": "27 m 2",
                },
                "unit": {
                    "evidence_id": "ev_floor",
                    "span_id": "span_floor",
                    "page": 4,
                    "section_id": "101.5",
                    "quote": "27 m 2",
                },
            }
        },
    }
    review_queue = [
        {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "rule_id": "rule_floor_area",
            "status": "context_required",
            "reason": "field evidence is present, but applicability or scope needs more context",
            "support_gaps": [],
            "unresolved_dependencies": ["applies_to_missing"],
            "evidence_ids": ["ev_floor"],
            "candidate": candidate,
        }
    ]

    payload = build_guarded_repair_rerun_outputs(
        review_queue=review_queue,
        retrieval_report={"queries": []},
        city_key="burnaby_r1",
        run_id="checkpoint_7_guarded_repair",
        rule_contract_families={"height"},
    )

    assert payload["verification_decisions"][0]["status"] == "not_used"
    assert payload["repair_rerun_report"]["repair_rerun_not_used_count"] == 1
    assert payload["guarded_repair_promotions"] == []
    assert payload["verified_rules"] == []
    assert payload["review_queue"][0]["status"] == "not_used"


def test_f1_guarded_repair_preserves_preverified_rules() -> None:
    preverified = {
        "rule_id": "rule_lot_coverage",
        "city": "burnaby_r1",
        "rule_object": "lot_coverage",
        "constraint_scope": "lot",
        "applies_to": "all buildings",
        "operator": "<=",
        "value": "60",
        "unit": "%",
        "status": "verified",
        "evidence_ids": ["ev_lot"],
    }
    predecision = {
        "rule_id": "rule_lot_coverage",
        "status": "verified",
        "reason": "all required fields have cited deterministic support",
        "evidence_ids": ["ev_lot"],
        "support_gaps": [],
        "unresolved_dependencies": [],
        "risk_flags": [],
        "schema_version": ARTIFACT_SCHEMA_VERSION,
    }

    payload = build_guarded_repair_rerun_outputs(
        review_queue=[],
        retrieval_report={"queries": []},
        city_key="burnaby_r1",
        run_id="checkpoint_7_guarded_repair",
        preverified_rules=[preverified],
        preverified_decisions=[predecision],
        initial_candidate_count=1,
    )

    assert payload["verified_rules"] == [preverified]
    assert payload["verification_decisions"] == [predecision]
    assert payload["verification_report"]["candidate_count"] == 1
    assert payload["verification_report"]["verified_count"] == 1


def test_f1_verifier_rejects_unsupported_repair_applicability() -> None:
    candidate = {
        "rule_id": "rule_height",
        "city": "burnaby_r1",
        "rule_type": "height",
        "rule_object": "height",
        "constraint_scope": "maximum height",
        "applies_to": "principal building",
        "operator": "<=",
        "value": "4.6",
        "unit": "m",
        "evidence_ids": ["ev_height"],
        "status": "review_needed",
        "raw": {
            "field_citations": {
                "rule_object": {"evidence_id": "ev_height", "quote": "Accessory structure height shall not exceed 4.6 m."},
                "operator": {"evidence_id": "ev_height", "quote": "Accessory structure height shall not exceed 4.6 m."},
                "value": {"evidence_id": "ev_height", "quote": "4.6 m"},
                "unit": {"evidence_id": "ev_height", "quote": "4.6 m"},
                "constraint_scope": {"evidence_id": "ev_height", "quote": "Accessory structure height shall not exceed 4.6 m."},
                "applies_to": {"evidence_id": "ev_height", "quote": "Accessory structure height shall not exceed 4.6 m."},
            }
        },
    }

    verification = build_verification_outputs(
        candidate_rules=[candidate],
        city_key="burnaby_r1",
        run_id="checkpoint_7_guarded_repair",
    )

    assert verification["verification_decisions"][0]["status"] == "rejected"
    assert "applies_to_not_supported" in verification["verification_decisions"][0]["support_gaps"]


def test_f1_gis_contract_exports_verified_rules_only() -> None:
    verified_rule = {
        "rule_id": "rule_height",
        "city": "burnaby_r1",
        "rule_object": "height",
        "constraint_scope": "maximum height",
        "applies_to": "accessory structure",
        "operator": "<=",
        "value": "4.6",
        "unit": "m",
        "condition": "",
        "exception": "",
        "status": "verified",
        "evidence_ids": ["ev_height"],
        "raw": {
            "field_citations": {
                "value": {
                    "evidence_id": "ev_height",
                    "span_id": "span_height",
                    "page": 1,
                    "section_id": "101.1",
                    "quote": "4.6 m",
                }
            }
        },
    }
    review_queue = [{"rule_id": "rule_review", "status": "review_needed"}]

    payload = build_gis_compliance_outputs(
        verified_rules=[verified_rule],
        review_queue=review_queue,
        city_key="burnaby_r1",
        run_id="checkpoint_8_gis_compliance",
    )

    contract = payload["gis_rule_contract"]
    assert contract["verified_only"] is True
    assert contract["export_rule_count"] == 1
    assert contract["excluded_review_rule_count"] == 1
    assert contract["rules"][0]["rule_id"] == "rule_height"
    assert all(rule["rule_id"] != "rule_review" for rule in contract["rules"])


def test_f1_compliance_needs_review_without_verified_rule() -> None:
    scenario = ComplianceScenario(
        scenario_id="needs_review_case",
        city="burnaby_r1",
        proposal={"rule_id": "rule_review", "value": 5.0},
    )

    decision = evaluate_compliance_scenario(
        scenario=scenario,
        contract_rules=[],
        review_queue=[{"rule_id": "rule_review"}],
    )

    assert decision.status == "needs_review"
    assert decision.review_rule_ids == ("rule_review",)


def test_f1_chatbot_eval_cites_sources_and_refuses_approval() -> None:
    verified_rule = {
        "rule_id": "rule_height",
        "rule_object": "height",
        "operator": "<=",
        "value": "4.6",
        "unit": "m",
        "applies_to": "accessory structure",
        "status": "verified",
        "evidence_ids": ["ev_height"],
    }
    review_queue = [
        {
            "rule_id": "rule_review",
            "status": "rejected",
            "support_gaps": ["operator_not_supported"],
            "candidate": {"evidence_ids": ["ev_review"]},
        }
    ]
    gis_contract = {"rules": [verified_rule]}

    payload = build_chatbot_eval_outputs(
        verified_rules=[verified_rule],
        review_queue=review_queue,
        gis_rule_contract=gis_contract,
        city_key="burnaby_r1",
        run_id="checkpoint_9_chatbot_eval",
    )

    assert payload["metrics"]["case_count"] == 3
    assert payload["metrics"]["cited_answer_count"] >= 2
    assert payload["metrics"]["approval_claim_count"] == 0
    assert payload["metrics"]["false_approval_count"] == 0
    approval_case = next(case for case in payload["cases"] if case["case_id"] == "approval_boundary")
    assert approval_case["answer"]["can_answer"] is False


def test_f1_model_chatbot_eval_uses_supplied_answer_function() -> None:
    verified_rule = {
        "rule_id": "rule_height",
        "rule_object": "height",
        "operator": "<=",
        "value": "4.6",
        "unit": "m",
        "applies_to": "accessory structure",
        "status": "verified",
        "evidence_ids": ["f1_retrieval_001_04"],
    }
    review_queue = [
        {
            "rule_id": "rule_review",
            "status": "rejected",
            "support_gaps": ["operator_not_supported"],
            "candidate": {"evidence_ids": ["f1_retrieval_004_02"]},
        }
    ]
    gis_contract = {
        "rules": [
            {
                **verified_rule,
                "citation": {"evidence_id": "f1_retrieval_001_04", "quote": "4.6 m"},
            }
        ]
    }

    def fake_answer(_system: str, prompt: str) -> str:
        if "approve" in prompt.lower():
            return "I cannot approve from chat; use compliance or human review."
        if "under review" in prompt.lower():
            return "The rejected item cites f1_retrieval_004_02 and has operator_not_supported."
        return "GIS can use the height rule cited by f1_retrieval_001_04."

    payload = build_model_chatbot_eval_outputs(
        verified_rules=[verified_rule],
        review_queue=review_queue,
        gis_rule_contract=gis_contract,
        city_key="burnaby_r1",
        run_id="checkpoint_11_model_chatbot_eval",
        answer_fn=fake_answer,
        model="fake-model",
    )

    assert payload["chatbot"]["model_runtime_used"] is True
    assert payload["metrics"]["case_count"] == 3
    assert payload["metrics"]["cited_answer_count"] == 2
    assert payload["metrics"]["approval_claim_count"] == 0


def test_f1_model_chatbot_redteam_scores_citations_and_refusals() -> None:
    verified_rule = {
        "rule_id": "f1_candidate_0003",
        "rule_object": "lot_coverage",
        "operator": "<=",
        "value": "60",
        "unit": "%",
        "applies_to": "maximum lot coverage",
        "status": "verified",
        "evidence_ids": ["f1_retrieval_003_01"],
    }
    review_queue = [
        {
            "rule_id": "f1_candidate_0004",
            "status": "rejected",
            "support_gaps": ["operator_not_supported"],
            "candidate": {"evidence_ids": ["f1_retrieval_004_02"]},
        }
    ]
    gis_contract = {
        "rules": [
            {
                **verified_rule,
                "citation": {"evidence_id": "f1_retrieval_003_01", "quote": "60%"},
            }
        ]
    }

    def fake_answer(_system: str, prompt: str) -> str:
        low = prompt.lower()
        if "ignore all previous" in low:
            return "I cannot do that. f1_candidate_0004 is rejected, with evidence f1_retrieval_004_02."
        if "rejected" in low or "that rejected one" in low:
            return "GIS cannot use that rejected item; it has operator_not_supported and cites f1_retrieval_004_02."
        if "mark it approved" in low:
            return "I cannot approve from chat; approval must come from the compliance engine."
        return "The verified lot coverage rule is <= 60%, citing f1_retrieval_003_01."

    payload = build_model_chatbot_redteam_outputs(
        verified_rules=[verified_rule],
        review_queue=review_queue,
        gis_rule_contract=gis_contract,
        city_key="burnaby_r1",
        run_id="checkpoint_12_model_chatbot_redteam",
        answer_fn=fake_answer,
        model="fake-model",
    )

    assert payload["chatbot"]["model_runtime_used"] is True
    assert payload["metrics"]["case_count"] == 6
    assert payload["metrics"]["failed_count"] == 0
    assert payload["metrics"]["citation_missing_count"] == 0
    assert payload["metrics"]["refusal_missing_count"] == 0
    assert payload["metrics"]["approval_claim_count"] == 0


def test_f1_benchmark_counts_false_verified_against_gold() -> None:
    gold_rules = [
        {
            "gold_id": "gold_height",
            "rule_object": "height",
            "value": "4.6",
            "unit": "m",
            "operator": "<=",
            "required_rule_terms": ["accessory"],
            "required_evidence_terms": ["accessory", "4.6"],
        }
    ]
    verified_rule = {
        "rule_id": "wrong_height",
        "city": "burnaby_r1",
        "rule_object": "height",
        "constraint_scope": "maximum height",
        "applies_to": "principal building",
        "operator": "<=",
        "value": "9.5",
        "unit": "m",
        "status": "verified",
        "evidence_ids": ["ev_wrong"],
        "raw": {
            "field_citations": {
                field: {"evidence_id": "ev_wrong", "span_id": "span_wrong", "quote": "9.5 m principal building"}
                for field in ("rule_object", "operator", "value", "unit", "constraint_scope", "applies_to")
            }
        },
    }

    payload = evaluate_benchmark_outputs(
        source_spans=[{"span_id": "span_gold", "text": "Accessory structure height shall not exceed 4.6 m."}],
        gold_rules=gold_rules,
        proposal_cases=[],
        candidate_rules=[verified_rule],
        verified_rules=[verified_rule],
        review_queue=[],
        gis_rule_contract={"verified_only": True, "rules": [verified_rule]},
        city_key="burnaby_r1",
        run_id="benchmark_test",
    )

    assert payload["rule_metrics"]["false_verified_count"] == 1
    assert payload["rule_metrics"]["verified_precision"] == 0.0
    assert payload["quality_gates"]["gates"]["false_verified_is_0"] is False
    assert payload["safety"]["benchmark_promotes_rules"] is False


def test_f1_benchmark_passes_core_gates_for_supported_single_rule() -> None:
    gold_rules = [
        {
            "gold_id": "gold_height",
            "rule_object": "height",
            "value": "4.6",
            "unit": "m",
            "operator": "<=",
            "required_rule_terms": ["accessory", "height"],
            "required_evidence_terms": ["accessory", "4.6", "height"],
        }
    ]
    rule = {
        "rule_id": "rule_height",
        "city": "burnaby_r1",
        "rule_object": "height",
        "constraint_scope": "maximum height",
        "applies_to": "accessory structure",
        "operator": "<=",
        "value": "4.6",
        "unit": "m",
        "status": "verified",
        "evidence_ids": ["ev_height"],
        "raw": {
            "field_citations": {
                field: {"evidence_id": "ev_height", "span_id": "span_height", "quote": "Accessory structure height shall not exceed 4.6 m."}
                for field in ("rule_object", "operator", "value", "unit", "constraint_scope", "applies_to")
            }
        },
    }

    payload = evaluate_benchmark_outputs(
        source_spans=[{"span_id": "span_height", "text": "Accessory structure height shall not exceed 4.6 m."}],
        gold_rules=gold_rules,
        proposal_cases=[],
        candidate_rules=[rule],
        verified_rules=[rule],
        review_queue=[],
        gis_rule_contract={
            "verified_only": True,
            "rules": [
                {
                    **rule,
                    "citation": {"evidence_id": "ev_height", "quote": "4.6 m"},
                    "verification_status": "verified",
                }
            ],
        },
        city_key="burnaby_r1",
        run_id="benchmark_test",
    )

    assert payload["retrieval_benchmark"]["metrics"]["retrieval_recall_at_6"] == 1.0
    assert payload["rule_metrics"]["candidate_recall"] == 1.0
    assert payload["rule_metrics"]["verified_precision"] == 1.0
    assert payload["gis_contract_metrics"]["review_rule_leak_count"] == 0
    assert payload["quality_gates"]["passed"] is True


def test_f1_command_center_preview_contains_current_artifact_counts() -> None:
    summary = {
        "verification": {"verified_count": 1, "review_queue_count": 1},
        "repair_review": {"guarded_repair_promotion_count": 1},
        "retrieval": {"total_hit_count": 2},
        "safety": {"f1_false_verified_count": 0},
    }
    gis_contract = {
        "export_rule_count": 1,
        "rules": [
            {
                "rule_id": "rule_height",
                "rule_object": "height",
                "operator": "<=",
                "value": "4.6",
                "unit": "m",
                "applies_to": "accessory structure",
                "geometry_target": "building_footprint",
            }
        ],
    }
    compliance_report = {"false_approval_count": 0, "status_counts": {"approved": 1, "rejected": 1}}
    chatbot_eval = {"metrics": {"case_count": 1, "cited_answer_count": 1, "uncertain_count": 0, "approval_claim_count": 0}}
    review_queue = [{"rule_id": "rule_review", "status": "rejected", "support_gaps": ["operator_not_supported"]}]

    payload = build_command_center_outputs(
        summary=summary,
        gis_rule_contract=gis_contract,
        compliance_report=compliance_report,
        chatbot_eval=chatbot_eval,
        review_queue=review_queue,
        city_key="burnaby_r1",
        run_id="checkpoint_10_command_center",
    )

    manifest = payload["command_center_manifest"]
    assert manifest["cards"]
    assert manifest["verified_rules"][0]["rule_id"] == "rule_height"
    assert manifest["review_queue"][0]["rule_id"] == "rule_review"
    assert "F1 Bylaw Intelligence Command Center" in payload["command_center_html"]
    assert "rule_height" in payload["command_center_html"]


def test_f1_command_center_app_contains_interactive_workflows_and_safety_metrics() -> None:
    summary = {
        "verification": {"verified_count": 1, "review_queue_count": 1},
        "safety": {"f1_false_verified_count": 0},
    }
    gis_contract = {
        "export_rule_count": 1,
        "rules": [
            {
                "rule_id": "rule_height",
                "rule_object": "height",
                "operator": "<=",
                "value": "4.6",
                "unit": "m",
                "applies_to": "accessory structure",
                "geometry_target": "building_footprint",
                "citation": {"evidence_id": "ev_height", "page": 2, "quote": "height must not exceed 4.6 m"},
            }
        ],
    }
    compliance_report = {"false_approval_count": 0, "status_counts": {"approved": 1, "rejected": 1, "needs_review": 1}}
    chatbot_eval = {"metrics": {"case_count": 1, "cited_answer_count": 1, "approval_claim_count": 0, "false_approval_count": 0}}
    review_queue = [
        {
            "rule_id": "rule_review",
            "status": "rejected",
            "support_gaps": ["operator_not_supported"],
            "candidate": {
                "rule_object": "height",
                "operator": "<=",
                "value": "5",
                "unit": "m",
                "raw": {
                    "field_citations": {
                        "value": {"evidence_id": "ev_review", "page": 3, "quote": "related but unsupported value"}
                    }
                },
            },
        }
    ]
    benchmark_eval = {
        "quality_gates": {"passed": True, "failed_gates": []},
        "retrieval_benchmark": {"metrics": {"retrieval_recall_at_6": 1.0}},
        "rule_metrics": {
            "candidate_recall": 0.9,
            "verified_precision": 1.0,
            "verified_recall": 0.8,
            "false_verified_count": 0,
            "verified_source_support_failed_count": 0,
        },
        "proposal_metrics": {
            "proposal_case_accuracy": 1.0,
            "proposal_decision_accuracy": 1.0,
            "false_approval_count": 0,
        },
        "gis_contract_metrics": {"review_rule_leak_count": 0},
    }

    payload = build_command_center_app_outputs(
        summary=summary,
        gis_rule_contract=gis_contract,
        compliance_report=compliance_report,
        compliance_decisions=[
            {
                "scenario_id": "scenario_height_pass",
                "status": "approved",
                "verified_rule_ids": ["rule_height"],
                "review_rule_ids": [],
            }
        ],
        chatbot_eval=chatbot_eval,
        review_queue=review_queue,
        benchmark_eval=benchmark_eval,
        city_key="burnaby_r1",
        run_id="checkpoint_15_command_center_app",
    )

    manifest = payload["command_center_app_manifest"]
    html = payload["command_center_app_html"]
    assert manifest["artifact"] == "command_center_app_manifest.json"
    assert manifest["workflow_health"]["quality_gates_passed"] is True
    assert manifest["workflow_health"]["false_verified_count"] == 0
    assert manifest["workflow_health"]["false_approval_count"] == 0
    assert {workflow["id"] for workflow in manifest["product_workflows"]} >= {
        "rule_explorer",
        "review_workbench",
        "evidence_inspector",
        "single_rule_compliance",
        "chatbot_safety",
    }
    assert manifest["verified_rules"][0]["citation"]["quote"] == "height must not exceed 4.6 m"
    assert manifest["review_queue"][0]["evidence"][0]["evidence_id"] == "ev_review"
    assert "ruleSearch" in html
    assert "scenarioRun" in html
    assert "Evidence Inspector" in html
    assert "This is not a full project approval" in html


def test_f1_contracts_fail_closed_for_promotions() -> None:
    with pytest.raises(ValueError):
        CandidateRule(rule_id="r1", city="burnaby_r1", status="verified")

    with pytest.raises(ValueError):
        VerificationDecision(rule_id="r1", status="verified")

    with pytest.raises(ValueError):
        VerificationDecision(
            rule_id="r1",
            status="repaired_successfully",
            evidence_ids=("ev1",),
            support_gaps=("value_not_found",),
        )


def test_f1_non_authoritative_layers_cannot_approve() -> None:
    with pytest.raises(ValueError):
        RepairPatch(patch_id="p1", rule_id="r1", action="mark_verified")

    with pytest.raises(ValueError):
        ComplianceDecision(scenario_id="s1", status="approved", review_rule_ids=("review_rule",))

    with pytest.raises(ValueError):
        ChatAnswer(answer_id="a1", question="Can I build?", answer="Yes.", can_answer=True)


def test_f1_repair_patch_requires_field_proofs() -> None:
    with pytest.raises(ValueError):
        RepairPatch(
            patch_id="p1",
            rule_id="r1",
            changed_fields={"value": "10.7"},
            field_proofs={},
        )

    patch = RepairPatch(
        patch_id="p1",
        rule_id="r1",
        changed_fields={"value": "10.7"},
        field_proofs={"value": {"evidence_id": "ev1", "quote": "10.7 m"}},
    )
    assert patch.changed_fields["value"] == "10.7"


def test_f1_checkpoint_summary_preserves_existing_safety_boundary(tmp_path: Path) -> None:
    report = tmp_path / "m7_status_report.json"
    report.write_text(
        json.dumps(
            {
                "overall_status": "m7_safety_ready",
                "current_false_verified_total": 0,
                "unsafe_current_rows": [],
            }
        ),
        encoding="utf-8",
    )

    summary = build_checkpoint_summary(city="burnaby_r1", run_id="checkpoint_0", status_report=report)

    assert summary["checkpoint"] == "F1 checkpoint 0"
    assert summary["safety"]["existing_safety_reproduced"] is True
    assert summary["safety"]["f1_promotes_rules"] is False
    assert summary["safety"]["f1_exports_gis"] is False


def test_f1_textbook_is_valid_notebook_with_required_sections() -> None:
    notebook = json.loads((ROOT / "F1_TEXTBOOK.ipynb").read_text(encoding="utf-8"))
    joined = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])

    assert notebook["nbformat"] == 4
    assert "F1 Textbook" in joined
    assert "F1 Pipeline" in joined
    assert "Active-Learning Checkpoint" in joined
    assert "scripts/run_f1_checkpoint.py" in joined
