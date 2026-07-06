from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_m8_5_pipeline_writes_required_outputs(tmp_path: Path) -> None:
    input_dir = tmp_path / "m8_input"
    output_dir = tmp_path / "m8_5_output"
    input_dir.mkdir()
    source_span = {
        "city": "burnaby_r1",
        "document_id": "R1.pdf",
        "page": 2,
        "section_id": "101.4",
        "block_type": "table",
        "char_start": 0,
        "char_end": 27,
        "text": "Zone | Height\nR1 | 10.7 m",
        "source_url": "",
        "metadata": {"evidence_id": "ev_height", "table_id": "t1"},
        "span_id": "span_test",
    }
    _write_json(input_dir / "source_spans.json", [source_span])
    _write_json(
        input_dir / "structured_rules.json",
        [
            {
                "rule_id": "rule_height",
                "city": "burnaby_r1",
                "zone": "R1",
                "rule_type": "height",
                "subject": "building",
                "comparator": "<=",
                "value": "10.7",
                "unit": "m",
                "conditions": [],
                "exceptions": [],
                "dependencies": [],
                "evidence_pointers": [
                    {
                        "evidence_id": "ev_height",
                        "span_id": "span_test",
                        "field_name": "rule",
                        "quote": "10.7 m",
                        "source_span": source_span,
                    }
                ],
                "status": "review_needed",
                "raw": {"rule_sentence": "Maximum height is 10.7 m subject to Section 6.4."},
            }
        ],
    )
    _write_json(
        input_dir / "verification_decisions.json",
        [
            {
                "rule_id": "rule_height",
                "status": "review_needed",
                "reason": "needs context",
                "evidence_ids": ["ev_height"],
                "unresolved_dependencies": [],
                "support_gaps": [],
                "repair_history": [],
            }
        ],
    )
    _write_json(input_dir / "repair_attempts.json", [])
    _write_json(input_dir / "m7_m8_comparison.json", {"m8": {"verified_like_count": 0}, "safety": {"m7_safety_preserved": True}})
    _write_json(input_dir / "m8_summary.json", {"city": "burnaby_r1", "status_counts": {"review_needed": 1}})

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_m8_5_pipeline.py",
            "--city",
            "burnaby_r1",
            "--config",
            "configs/burnaby_r1.json",
            "--m8-input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--enable-table-parsing",
            "--enable-dependency-graph",
            "--enable-review-packets",
            "--dry-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    for name in [
        "table_blocks.json",
        "table_cell_lineage.json",
        "table_derived_rules.json",
        "dependency_graph.json",
        "dependency_resolutions.json",
        "repair_evaluations.json",
        "llm_repair_cases.json",
        "llm_repair_raw_outputs.json",
        "llm_repair_patches.json",
        "llm_repair_field_proofs.json",
        "llm_repair_evaluations.json",
        "repair_rerun_report.json",
        "repair_rerun_report.md",
        "guarded_repair_promotions.json",
        "review_packets.json",
        "verifier_rerun_requests.json",
        "m8_5_structured_rules.json",
        "m8_5_verification_decisions.json",
        "m8_m8_5_comparison.json",
        "m8_5_summary.json",
        "m8_5_chatbot_context.json",
    ]:
        assert (output_dir / name).exists(), name

    summary = json.loads((output_dir / "m8_5_summary.json").read_text(encoding="utf-8"))

    assert summary["city"] == "burnaby_r1"
    assert summary["safety"]["m7_safety_preserved"] is True
    assert summary["safety"]["repair_can_promote_directly"] is False
    assert summary["safety"]["reviewer_can_promote_directly"] is False
    assert summary["m8_5_metrics"]["table_derived_rules_count"] == 1
    assert summary["m8_5_metrics"]["reviewer_packets_count"] == 1
    assert summary["m8_5_metrics"]["llm_repair_case_count"] == 0
    assert summary["m8_5_metrics"]["repair_rerun_attempt_count"] == 0


def test_m8_5_pipeline_missing_input_fails_clearly(tmp_path: Path) -> None:
    input_dir = tmp_path / "missing"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_m8_5_pipeline.py",
            "--m8-input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--dry-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "missing required files" in result.stderr


def test_m8_5_pipeline_repair_rerun_writes_guarded_artifacts(tmp_path: Path) -> None:
    input_dir = tmp_path / "m8_input"
    m7_dir = tmp_path / "m7_input"
    output_dir = tmp_path / "m8_5_output"
    input_dir.mkdir()
    m7_dir.mkdir()
    _write_repair_rerun_fixture(input_dir, m7_dir)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_m8_5_pipeline.py",
            "--city",
            "burnaby_r1",
            "--config",
            "configs/burnaby_r1.json",
            "--m8-input-dir",
            str(input_dir),
            "--m7-input-dir",
            str(m7_dir),
            "--output-dir",
            str(output_dir),
            "--enable-repair-rerun",
            "--apply-guarded-repair-promotions",
            "--dry-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads((output_dir / "repair_rerun_report.json").read_text(encoding="utf-8"))
    requests = json.loads((output_dir / "verifier_rerun_requests.json").read_text(encoding="utf-8"))
    summary = json.loads((output_dir / "m8_5_summary.json").read_text(encoding="utf-8"))

    assert report["eligible_rule_count"] == 1
    assert report["attempt_count"] == 1
    assert len(requests) == 1
    assert requests[0]["status"] in {"complete", "failed"}
    assert summary["m8_5_metrics"]["repair_rerun_eligible_rule_count"] == 1
    assert summary["m8_5_metrics"]["repair_rerun_attempt_count"] == 1


def test_m8_5_pipeline_repair_rerun_requires_m7_evidence_units(tmp_path: Path) -> None:
    input_dir = tmp_path / "m8_input"
    output_dir = tmp_path / "m8_5_output"
    input_dir.mkdir()
    _write_json(input_dir / "source_spans.json", [])
    _write_json(input_dir / "structured_rules.json", [])
    _write_json(input_dir / "verification_decisions.json", [])
    _write_json(input_dir / "repair_attempts.json", [])
    _write_json(input_dir / "m7_m8_comparison.json", {})
    _write_json(input_dir / "m8_summary.json", {})

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_m8_5_pipeline.py",
            "--m8-input-dir",
            str(input_dir),
            "--m7-input-dir",
            str(tmp_path / "missing_m7"),
            "--output-dir",
            str(output_dir),
            "--enable-repair-rerun",
            "--dry-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "repair rerun requires original M7 evidence_units.json" in result.stderr


def test_m8_5_pipeline_llm_repair_fixture_can_feed_guarded_rerun(tmp_path: Path) -> None:
    input_dir = tmp_path / "m8_input"
    m7_dir = tmp_path / "m7_input"
    output_dir = tmp_path / "m8_5_output"
    fixture_path = tmp_path / "llm_repair_fixture.json"
    input_dir.mkdir()
    m7_dir.mkdir()
    _write_repair_rerun_fixture(input_dir, m7_dir)
    _write_json(
        fixture_path,
        {
            "rule_height": {
                "action": "patch",
                "changes": {
                    "evidence_id": "ev_new",
                    "rule_object": "height",
                    "constraint_scope": "height",
                    "applies_to": "building",
                    "operator": "<=",
                    "value": "10.7",
                    "unit": "m",
                },
                "field_proofs": [
                    _llm_proof("evidence_id", "ev_new"),
                    _llm_proof("rule_object", "ev_new"),
                    _llm_proof("constraint_scope", "ev_new"),
                    _llm_proof("applies_to", "ev_new"),
                    _llm_proof("operator", "ev_new"),
                    _llm_proof("value", "ev_new"),
                    _llm_proof("unit", "ev_new"),
                ],
                "confidence": 1.0,
                "risk_flags": [],
                "no_patch_reason": "",
            }
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_m8_5_pipeline.py",
            "--city",
            "burnaby_r1",
            "--config",
            "configs/burnaby_r1.json",
            "--m8-input-dir",
            str(input_dir),
            "--m7-input-dir",
            str(m7_dir),
            "--output-dir",
            str(output_dir),
            "--enable-repair-rerun",
            "--apply-guarded-repair-promotions",
            "--enable-llm-repair",
            "--llm-repair-fixture",
            str(fixture_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads((output_dir / "m8_5_summary.json").read_text(encoding="utf-8"))
    llm_evaluations = json.loads((output_dir / "llm_repair_evaluations.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "repair_rerun_report.json").read_text(encoding="utf-8"))

    assert summary["m8_5_metrics"]["llm_repair_case_count"] == 1
    assert summary["m8_5_metrics"]["llm_repair_safe_patch_count"] == 1
    assert summary["m8_5_metrics"]["guarded_repair_promotion_count"] == 1
    assert summary["m8_5_metrics"]["review_needed_reduction_from_llm_repair"] == 1
    assert llm_evaluations[0]["metadata"]["repair_source"] == "llm_repair"
    assert report["attempts"][0]["selected_repair"]["metadata"]["repair_source"] == "llm_repair"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_repair_rerun_fixture(input_dir: Path, m7_dir: Path) -> None:
    old_span = {
        "city": "burnaby_r1",
        "document_id": "R1.pdf",
        "page": 2,
        "section_id": "101.4",
        "block_type": "clause",
        "char_start": 0,
        "char_end": 20,
        "text": "height needs review",
        "source_url": "",
        "metadata": {"evidence_id": "ev_old"},
        "span_id": "span_old",
    }
    new_span = {
        "city": "burnaby_r1",
        "document_id": "R1.pdf",
        "page": 2,
        "section_id": "101.4",
        "block_type": "clause",
        "char_start": 0,
        "char_end": 28,
        "text": "R1 maximum building height 10.7 m",
        "source_url": "",
        "metadata": {"evidence_id": "ev_new"},
        "span_id": "span_new",
    }
    _write_json(input_dir / "source_spans.json", [old_span])
    _write_json(
        input_dir / "structured_rules.json",
        [
            {
                "rule_id": "rule_height",
                "city": "burnaby_r1",
                "zone": "R1",
                "rule_type": "height",
                "subject": "building",
                "comparator": "<=",
                "value": "10.7",
                "unit": "m",
                "conditions": [],
                "exceptions": [],
                "dependencies": [],
                "evidence_pointers": [
                    {
                        "evidence_id": "ev_old",
                        "span_id": "span_old",
                        "field_name": "rule",
                        "quote": "height needs review",
                        "source_span": old_span,
                    }
                ],
                "status": "review_needed",
                "raw": {
                    "rule_id": "rule_height",
                    "evidence_id": "ev_old",
                    "candidate": {
                        "candidate_id": "candidate_height",
                        "rule_object": "height",
                        "constraint_scope": "height",
                        "applies_to": "building",
                        "operator": "<=",
                        "value": "10.7",
                        "unit": "m",
                        "condition": "",
                        "exception": "",
                        "evidence_id": "ev_old",
                        "source_stream": "native_rag_llm",
                    },
                },
            }
        ],
    )
    _write_json(
        input_dir / "verification_decisions.json",
        [
            {
                "rule_id": "rule_height",
                "status": "review_needed",
                "reason": "needs stronger evidence",
                "evidence_ids": ["ev_old"],
                "unresolved_dependencies": [],
                "support_gaps": ["text_candidate_requires_review"],
                "repair_history": [],
            }
        ],
    )
    repair_attempt = {
        "attempt_index": 1,
        "critique": {
            "rule_id": "rule_height",
            "category": "general_review",
            "reason": "needs stronger evidence",
            "fields": [],
            "support_gaps": ["text_candidate_requires_review"],
        },
        "query": "height 10.7 m",
        "patch": {
            "rule_id": "rule_height",
            "changes": {"evidence_id": "ev_new"},
            "evidence_pointers": [
                {
                    "evidence_id": "ev_new",
                    "span_id": "span_new",
                    "field_name": "retrieved_context",
                    "quote": "R1 maximum building height 10.7 m",
                    "source_span": new_span,
                    "confidence": 1.0,
                }
            ],
            "reason": "test repair",
            "category": "general_review",
        },
        "decision_status": "review_needed",
        "reason": "needs verifier",
        "evidence_bundle_id": "bundle_1",
    }
    duplicate = {**repair_attempt, "attempt_index": 2}
    _write_json(input_dir / "repair_attempts.json", [repair_attempt, duplicate])
    _write_json(input_dir / "m7_m8_comparison.json", {"m8": {"verified_like_count": 0}, "safety": {"m7_safety_preserved": True}})
    _write_json(input_dir / "m8_summary.json", {"city": "burnaby_r1", "status_counts": {"review_needed": 1}})
    _write_json(
        m7_dir / "evidence_units.json",
        [
            {
                "evidence_id": "ev_new",
                "page": 2,
                "evidence_type": "table_cell",
                "evidence_text": "R1 maximum building height 10.7 m",
                "source_context": "Maximum Building Height | Small-Scale Multi-Unit Housing | 10.7 m",
                "table_title": "R1 Small-Scale Multi-Unit Housing District regulations",
                "row_header": "Maximum Building Height",
                "column_header": "Small-Scale Multi-Unit Housing",
                "cell_value": "10.7 m",
            }
        ],
    )


def _llm_proof(field: str, evidence_id: str) -> dict:
    return {
        "field": field,
        "evidence_id": evidence_id,
        "span_id": "span_new",
        "quote": "R1 maximum building height 10.7 m",
        "rationale": "quote supports the repaired field",
    }
