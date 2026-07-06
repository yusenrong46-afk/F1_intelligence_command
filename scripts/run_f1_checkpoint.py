#!/usr/bin/env python3
"""F1 checkpoint runner.

Checkpoint 0 is intentionally a product-skeleton validation pass. It writes a
small F1 summary manifest and verifies that the existing M-series safety report
still shows the zero-false-verified boundary before future F1 work begins.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from burnaby_prototype.bylaw_command_center import (  # noqa: E402
    DEFAULT_MULTI_CITY_KEYS,
    OpenRouterChatClient,
    artifact_manifest,
    build_benchmark_eval_outputs,
    build_candidate_rules_from_retrieval,
    build_chatbot_eval_outputs,
    build_command_center_app_outputs,
    build_command_center_outputs,
    build_document_intelligence,
    build_gis_compliance_outputs,
    build_guarded_repair_rerun_outputs,
    build_model_chatbot_eval_outputs,
    build_model_chatbot_redteam_outputs,
    build_product_operations_outputs,
    build_retrieval_report,
    build_repair_review_outputs,
    build_source_registry,
    build_verification_outputs,
    load_openrouter_api_key,
    run_multi_city_checkpoint,
    write_candidate_rules,
    write_benchmark_eval_outputs,
    write_chatbot_eval_outputs,
    write_command_center_app_outputs,
    write_command_center_outputs,
    write_document_intelligence,
    write_gis_compliance_outputs,
    write_multi_city_report,
    write_product_operations_outputs,
    write_retrieval_report,
    write_repair_review_outputs,
    write_source_registry,
    write_verification_outputs,
)
from burnaby_prototype.bylaw_command_center.constitution import F1_CONSTITUTION_RULES  # noqa: E402

DEFAULT_STATUS_REPORT = ROOT / "outputs" / "m7_status_report" / "m7_status_report.json"
DEFAULT_RUN_ID = "checkpoint_0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint",
        choices=[
            "checkpoint_0",
            "source_registry",
            "document_intelligence",
            "proof_rag",
            "structured_extraction",
            "verification",
            "repair_review",
            "guarded_repair",
            "gis_compliance",
            "chatbot_eval",
            "command_center",
            "model_chatbot_eval",
            "model_chatbot_redteam",
            "multi_city",
            "benchmark_eval",
            "command_center_app",
            "product_operations",
        ],
        default="checkpoint_0",
        help="F1 checkpoint to run. source_registry is checkpoint 1; document_intelligence is checkpoint 2; proof_rag is checkpoint 3; structured_extraction is checkpoint 4; verification is checkpoint 5; repair_review is checkpoint 6; guarded_repair is checkpoint 7; gis_compliance is checkpoint 8; chatbot_eval is checkpoint 9; command_center is checkpoint 10; model_chatbot_eval is checkpoint 11; model_chatbot_redteam is checkpoint 12; multi_city is checkpoint 13; benchmark_eval is checkpoint 14; command_center_app is checkpoint 15; product_operations is checkpoint 16.",
    )
    parser.add_argument("--city", default="burnaby_r1")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--status-report", default=str(DEFAULT_STATUS_REPORT))
    parser.add_argument("--output-root", default=str(ROOT / "outputs" / "f1_runs"))
    parser.add_argument("--chat-model", default="openai/gpt-oss-120b", help="OpenRouter chat model for model_chatbot_eval.")
    parser.add_argument(
        "--multi-cities",
        default=",".join(DEFAULT_MULTI_CITY_KEYS),
        help="Comma-separated city keys for the multi_city checkpoint.",
    )
    parser.add_argument("--no-docling", action="store_true", help="Use the deterministic fallback parser for document intelligence.")
    parser.add_argument("--print-only", action="store_true", help="Print the summary JSON instead of writing it.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = args.run_id or default_run_id(args.checkpoint)
    status_report = Path(args.status_report)
    summary_city = "multi_city" if args.checkpoint == "multi_city" else args.city
    summary = build_checkpoint_summary(city=summary_city, run_id=run_id, status_report=status_report)
    source_registry = None
    document_intelligence = None
    retrieval_report = None
    extraction_payload = None
    verification_payload = None
    repair_review_payload = None
    gis_compliance_payload = None
    chatbot_eval_payload = None
    command_center_payload = None
    command_center_app_payload = None
    product_operations_payload = None
    multi_city_payload = None
    benchmark_eval_payload = None
    if args.checkpoint == "source_registry":
        source_registry = build_source_registry(city_key=args.city, run_id=run_id, root=ROOT)
        summary = with_source_registry(summary, source_registry)
    if args.checkpoint == "document_intelligence":
        source_registry = build_source_registry(city_key=args.city, run_id=run_id, root=ROOT)
        summary = with_source_registry(summary, source_registry)
        document_intelligence = build_document_intelligence(
            source_registry=source_registry,
            run_id=run_id,
            root=ROOT,
            prefer_docling=not args.no_docling,
        )
        summary = with_document_intelligence(summary, document_intelligence)
    if args.checkpoint == "proof_rag":
        source_registry = build_source_registry(city_key=args.city, run_id=run_id, root=ROOT)
        summary = with_source_registry(summary, source_registry)
        document_intelligence = build_document_intelligence(
            source_registry=source_registry,
            run_id=run_id,
            root=ROOT,
            prefer_docling=not args.no_docling,
        )
        summary = with_document_intelligence(summary, document_intelligence)
        retrieval_report = build_retrieval_report(
            source_spans=document_intelligence["source_spans"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_retrieval_report(summary, retrieval_report)
    if args.checkpoint == "structured_extraction":
        source_registry = build_source_registry(city_key=args.city, run_id=run_id, root=ROOT)
        summary = with_source_registry(summary, source_registry)
        document_intelligence = build_document_intelligence(
            source_registry=source_registry,
            run_id=run_id,
            root=ROOT,
            prefer_docling=not args.no_docling,
        )
        summary = with_document_intelligence(summary, document_intelligence)
        retrieval_report = build_retrieval_report(
            source_spans=document_intelligence["source_spans"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_retrieval_report(summary, retrieval_report)
        extraction_payload = build_candidate_rules_from_retrieval(
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_extraction_payload(summary, extraction_payload)
    if args.checkpoint == "verification":
        source_registry = build_source_registry(city_key=args.city, run_id=run_id, root=ROOT)
        summary = with_source_registry(summary, source_registry)
        document_intelligence = build_document_intelligence(
            source_registry=source_registry,
            run_id=run_id,
            root=ROOT,
            prefer_docling=not args.no_docling,
        )
        summary = with_document_intelligence(summary, document_intelligence)
        retrieval_report = build_retrieval_report(
            source_spans=document_intelligence["source_spans"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_retrieval_report(summary, retrieval_report)
        extraction_payload = build_candidate_rules_from_retrieval(
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_extraction_payload(summary, extraction_payload)
        verification_payload = build_verification_outputs(
            candidate_rules=extraction_payload["candidate_rules"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_verification_payload(summary, verification_payload)
    if args.checkpoint == "repair_review":
        source_registry = build_source_registry(city_key=args.city, run_id=run_id, root=ROOT)
        summary = with_source_registry(summary, source_registry)
        document_intelligence = build_document_intelligence(
            source_registry=source_registry,
            run_id=run_id,
            root=ROOT,
            prefer_docling=not args.no_docling,
        )
        summary = with_document_intelligence(summary, document_intelligence)
        retrieval_report = build_retrieval_report(
            source_spans=document_intelligence["source_spans"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_retrieval_report(summary, retrieval_report)
        extraction_payload = build_candidate_rules_from_retrieval(
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_extraction_payload(summary, extraction_payload)
        verification_payload = build_verification_outputs(
            candidate_rules=extraction_payload["candidate_rules"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_verification_payload(summary, verification_payload)
        repair_review_payload = build_repair_review_outputs(
            review_queue=verification_payload["review_queue"],
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_repair_review_payload(summary, repair_review_payload)
    if args.checkpoint == "guarded_repair":
        source_registry = build_source_registry(city_key=args.city, run_id=run_id, root=ROOT)
        summary = with_source_registry(summary, source_registry)
        document_intelligence = build_document_intelligence(
            source_registry=source_registry,
            run_id=run_id,
            root=ROOT,
            prefer_docling=not args.no_docling,
        )
        summary = with_document_intelligence(summary, document_intelligence)
        retrieval_report = build_retrieval_report(
            source_spans=document_intelligence["source_spans"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_retrieval_report(summary, retrieval_report)
        extraction_payload = build_candidate_rules_from_retrieval(
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_extraction_payload(summary, extraction_payload)
        verification_payload = build_verification_outputs(
            candidate_rules=extraction_payload["candidate_rules"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_verification_payload(summary, verification_payload)
        repair_review_payload = build_guarded_repair_rerun_outputs(
            review_queue=verification_payload["review_queue"],
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
            rule_contract_families=_rule_contract_families(args.city),
            preverified_rules=verification_payload["verified_rules"],
            preverified_decisions=_promoted_decisions(verification_payload),
            initial_candidate_count=len(extraction_payload["candidate_rules"]),
        )
        summary = with_guarded_repair_payload(summary, repair_review_payload)
    if args.checkpoint == "gis_compliance":
        source_registry = build_source_registry(city_key=args.city, run_id=run_id, root=ROOT)
        summary = with_source_registry(summary, source_registry)
        document_intelligence = build_document_intelligence(
            source_registry=source_registry,
            run_id=run_id,
            root=ROOT,
            prefer_docling=not args.no_docling,
        )
        summary = with_document_intelligence(summary, document_intelligence)
        retrieval_report = build_retrieval_report(
            source_spans=document_intelligence["source_spans"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_retrieval_report(summary, retrieval_report)
        extraction_payload = build_candidate_rules_from_retrieval(
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_extraction_payload(summary, extraction_payload)
        verification_payload = build_verification_outputs(
            candidate_rules=extraction_payload["candidate_rules"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_verification_payload(summary, verification_payload)
        repair_review_payload = build_guarded_repair_rerun_outputs(
            review_queue=verification_payload["review_queue"],
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
            rule_contract_families=_rule_contract_families(args.city),
            preverified_rules=verification_payload["verified_rules"],
            preverified_decisions=_promoted_decisions(verification_payload),
            initial_candidate_count=len(extraction_payload["candidate_rules"]),
        )
        summary = with_guarded_repair_payload(summary, repair_review_payload)
        gis_compliance_payload = build_gis_compliance_outputs(
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_gis_compliance_payload(summary, gis_compliance_payload)
    if args.checkpoint == "chatbot_eval":
        source_registry = build_source_registry(city_key=args.city, run_id=run_id, root=ROOT)
        summary = with_source_registry(summary, source_registry)
        document_intelligence = build_document_intelligence(
            source_registry=source_registry,
            run_id=run_id,
            root=ROOT,
            prefer_docling=not args.no_docling,
        )
        summary = with_document_intelligence(summary, document_intelligence)
        retrieval_report = build_retrieval_report(
            source_spans=document_intelligence["source_spans"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_retrieval_report(summary, retrieval_report)
        extraction_payload = build_candidate_rules_from_retrieval(
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_extraction_payload(summary, extraction_payload)
        verification_payload = build_verification_outputs(
            candidate_rules=extraction_payload["candidate_rules"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_verification_payload(summary, verification_payload)
        repair_review_payload = build_guarded_repair_rerun_outputs(
            review_queue=verification_payload["review_queue"],
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
            rule_contract_families=_rule_contract_families(args.city),
            preverified_rules=verification_payload["verified_rules"],
            preverified_decisions=_promoted_decisions(verification_payload),
            initial_candidate_count=len(extraction_payload["candidate_rules"]),
        )
        summary = with_guarded_repair_payload(summary, repair_review_payload)
        gis_compliance_payload = build_gis_compliance_outputs(
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_gis_compliance_payload(summary, gis_compliance_payload)
        chatbot_eval_payload = build_chatbot_eval_outputs(
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            gis_rule_contract=gis_compliance_payload["gis_rule_contract"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_chatbot_eval_payload(summary, chatbot_eval_payload)
    if args.checkpoint == "command_center":
        source_registry = build_source_registry(city_key=args.city, run_id=run_id, root=ROOT)
        summary = with_source_registry(summary, source_registry)
        document_intelligence = build_document_intelligence(
            source_registry=source_registry,
            run_id=run_id,
            root=ROOT,
            prefer_docling=not args.no_docling,
        )
        summary = with_document_intelligence(summary, document_intelligence)
        retrieval_report = build_retrieval_report(
            source_spans=document_intelligence["source_spans"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_retrieval_report(summary, retrieval_report)
        extraction_payload = build_candidate_rules_from_retrieval(
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_extraction_payload(summary, extraction_payload)
        verification_payload = build_verification_outputs(
            candidate_rules=extraction_payload["candidate_rules"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_verification_payload(summary, verification_payload)
        repair_review_payload = build_guarded_repair_rerun_outputs(
            review_queue=verification_payload["review_queue"],
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
            rule_contract_families=_rule_contract_families(args.city),
            preverified_rules=verification_payload["verified_rules"],
            preverified_decisions=_promoted_decisions(verification_payload),
            initial_candidate_count=len(extraction_payload["candidate_rules"]),
        )
        summary = with_guarded_repair_payload(summary, repair_review_payload)
        gis_compliance_payload = build_gis_compliance_outputs(
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_gis_compliance_payload(summary, gis_compliance_payload)
        chatbot_eval_payload = build_chatbot_eval_outputs(
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            gis_rule_contract=gis_compliance_payload["gis_rule_contract"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_chatbot_eval_payload(summary, chatbot_eval_payload)
        command_center_payload = build_command_center_outputs(
            summary=summary,
            gis_rule_contract=gis_compliance_payload["gis_rule_contract"],
            compliance_report=gis_compliance_payload["compliance_report"],
            chatbot_eval=chatbot_eval_payload,
            review_queue=repair_review_payload["review_queue"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_command_center_payload(summary, command_center_payload)
    if args.checkpoint == "model_chatbot_eval":
        source_registry = build_source_registry(city_key=args.city, run_id=run_id, root=ROOT)
        summary = with_source_registry(summary, source_registry)
        document_intelligence = build_document_intelligence(
            source_registry=source_registry,
            run_id=run_id,
            root=ROOT,
            prefer_docling=not args.no_docling,
        )
        summary = with_document_intelligence(summary, document_intelligence)
        retrieval_report = build_retrieval_report(
            source_spans=document_intelligence["source_spans"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_retrieval_report(summary, retrieval_report)
        extraction_payload = build_candidate_rules_from_retrieval(
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_extraction_payload(summary, extraction_payload)
        verification_payload = build_verification_outputs(
            candidate_rules=extraction_payload["candidate_rules"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_verification_payload(summary, verification_payload)
        repair_review_payload = build_guarded_repair_rerun_outputs(
            review_queue=verification_payload["review_queue"],
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
            rule_contract_families=_rule_contract_families(args.city),
            preverified_rules=verification_payload["verified_rules"],
            preverified_decisions=_promoted_decisions(verification_payload),
            initial_candidate_count=len(extraction_payload["candidate_rules"]),
        )
        summary = with_guarded_repair_payload(summary, repair_review_payload)
        gis_compliance_payload = build_gis_compliance_outputs(
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_gis_compliance_payload(summary, gis_compliance_payload)
        api_key = load_openrouter_api_key(ROOT)
        if not api_key:
            raise SystemExit("OPENROUTER_API_KEY is required for --checkpoint model_chatbot_eval")
        client = OpenRouterChatClient(api_key, model=args.chat_model)
        chatbot_eval_payload = build_model_chatbot_eval_outputs(
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            gis_rule_contract=gis_compliance_payload["gis_rule_contract"],
            city_key=args.city,
            run_id=run_id,
            answer_fn=client.answer,
            model=args.chat_model,
        )
        summary = with_model_chatbot_eval_payload(summary, chatbot_eval_payload)
    if args.checkpoint == "model_chatbot_redteam":
        source_registry = build_source_registry(city_key=args.city, run_id=run_id, root=ROOT)
        summary = with_source_registry(summary, source_registry)
        document_intelligence = build_document_intelligence(
            source_registry=source_registry,
            run_id=run_id,
            root=ROOT,
            prefer_docling=not args.no_docling,
        )
        summary = with_document_intelligence(summary, document_intelligence)
        retrieval_report = build_retrieval_report(
            source_spans=document_intelligence["source_spans"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_retrieval_report(summary, retrieval_report)
        extraction_payload = build_candidate_rules_from_retrieval(
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_extraction_payload(summary, extraction_payload)
        verification_payload = build_verification_outputs(
            candidate_rules=extraction_payload["candidate_rules"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_verification_payload(summary, verification_payload)
        repair_review_payload = build_guarded_repair_rerun_outputs(
            review_queue=verification_payload["review_queue"],
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
            rule_contract_families=_rule_contract_families(args.city),
            preverified_rules=verification_payload["verified_rules"],
            preverified_decisions=_promoted_decisions(verification_payload),
            initial_candidate_count=len(extraction_payload["candidate_rules"]),
        )
        summary = with_guarded_repair_payload(summary, repair_review_payload)
        gis_compliance_payload = build_gis_compliance_outputs(
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_gis_compliance_payload(summary, gis_compliance_payload)
        api_key = load_openrouter_api_key(ROOT)
        if not api_key:
            raise SystemExit("OPENROUTER_API_KEY is required for --checkpoint model_chatbot_redteam")
        client = OpenRouterChatClient(api_key, model=args.chat_model)
        chatbot_eval_payload = build_model_chatbot_redteam_outputs(
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            gis_rule_contract=gis_compliance_payload["gis_rule_contract"],
            city_key=args.city,
            run_id=run_id,
            answer_fn=client.answer,
            model=args.chat_model,
        )
        summary = with_model_chatbot_redteam_payload(summary, chatbot_eval_payload)
    if args.checkpoint == "multi_city":
        city_keys = [city.strip() for city in args.multi_cities.split(",") if city.strip()]
        multi_city_payload = run_multi_city_checkpoint(
            root=ROOT,
            output_root=Path(args.output_root),
            run_id=run_id,
            city_keys=city_keys,
            prefer_docling=not args.no_docling,
        )
        summary = with_multi_city_payload(summary, multi_city_payload)
    if args.checkpoint == "benchmark_eval":
        source_registry = build_source_registry(city_key=args.city, run_id=run_id, root=ROOT)
        summary = with_source_registry(summary, source_registry)
        document_intelligence = build_document_intelligence(
            source_registry=source_registry,
            run_id=run_id,
            root=ROOT,
            prefer_docling=not args.no_docling,
        )
        summary = with_document_intelligence(summary, document_intelligence)
        retrieval_report = build_retrieval_report(
            source_spans=document_intelligence["source_spans"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_retrieval_report(summary, retrieval_report)
        extraction_payload = build_candidate_rules_from_retrieval(
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_extraction_payload(summary, extraction_payload)
        verification_payload = build_verification_outputs(
            candidate_rules=extraction_payload["candidate_rules"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_verification_payload(summary, verification_payload)
        repair_review_payload = build_guarded_repair_rerun_outputs(
            review_queue=verification_payload["review_queue"],
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
            rule_contract_families=_rule_contract_families(args.city),
            preverified_rules=verification_payload["verified_rules"],
            preverified_decisions=_promoted_decisions(verification_payload),
            initial_candidate_count=len(extraction_payload["candidate_rules"]),
        )
        summary = with_guarded_repair_payload(summary, repair_review_payload)
        gis_compliance_payload = build_gis_compliance_outputs(
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_gis_compliance_payload(summary, gis_compliance_payload)
        benchmark_eval_payload = build_benchmark_eval_outputs(
            source_spans=document_intelligence["source_spans"],
            candidate_rules=extraction_payload["candidate_rules"],
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            gis_rule_contract=gis_compliance_payload["gis_rule_contract"],
            city_key=args.city,
            run_id=run_id,
            root=ROOT,
        )
        summary = with_benchmark_eval_payload(summary, benchmark_eval_payload)
    if args.checkpoint == "command_center_app":
        source_registry = build_source_registry(city_key=args.city, run_id=run_id, root=ROOT)
        summary = with_source_registry(summary, source_registry)
        document_intelligence = build_document_intelligence(
            source_registry=source_registry,
            run_id=run_id,
            root=ROOT,
            prefer_docling=not args.no_docling,
        )
        summary = with_document_intelligence(summary, document_intelligence)
        retrieval_report = build_retrieval_report(
            source_spans=document_intelligence["source_spans"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_retrieval_report(summary, retrieval_report)
        extraction_payload = build_candidate_rules_from_retrieval(
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_extraction_payload(summary, extraction_payload)
        verification_payload = build_verification_outputs(
            candidate_rules=extraction_payload["candidate_rules"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_verification_payload(summary, verification_payload)
        repair_review_payload = build_guarded_repair_rerun_outputs(
            review_queue=verification_payload["review_queue"],
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
            rule_contract_families=_rule_contract_families(args.city),
            preverified_rules=verification_payload["verified_rules"],
            preverified_decisions=_promoted_decisions(verification_payload),
            initial_candidate_count=len(extraction_payload["candidate_rules"]),
        )
        summary = with_guarded_repair_payload(summary, repair_review_payload)
        gis_compliance_payload = build_gis_compliance_outputs(
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_gis_compliance_payload(summary, gis_compliance_payload)
        chatbot_eval_payload = build_chatbot_eval_outputs(
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            gis_rule_contract=gis_compliance_payload["gis_rule_contract"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_chatbot_eval_payload(summary, chatbot_eval_payload)
        benchmark_eval_payload = build_benchmark_eval_outputs(
            source_spans=document_intelligence["source_spans"],
            candidate_rules=extraction_payload["candidate_rules"],
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            gis_rule_contract=gis_compliance_payload["gis_rule_contract"],
            city_key=args.city,
            run_id=run_id,
            root=ROOT,
        )
        summary = with_benchmark_eval_payload(summary, benchmark_eval_payload)
        command_center_app_payload = build_command_center_app_outputs(
            summary=summary,
            gis_rule_contract=gis_compliance_payload["gis_rule_contract"],
            compliance_report=gis_compliance_payload["compliance_report"],
            compliance_decisions=gis_compliance_payload["compliance_decisions"],
            chatbot_eval=chatbot_eval_payload,
            review_queue=repair_review_payload["review_queue"],
            benchmark_eval=benchmark_eval_payload,
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_command_center_app_payload(summary, command_center_app_payload)
    if args.checkpoint == "product_operations":
        source_registry = build_source_registry(city_key=args.city, run_id=run_id, root=ROOT)
        summary = with_source_registry(summary, source_registry)
        document_intelligence = build_document_intelligence(
            source_registry=source_registry,
            run_id=run_id,
            root=ROOT,
            prefer_docling=not args.no_docling,
        )
        summary = with_document_intelligence(summary, document_intelligence)
        retrieval_report = build_retrieval_report(
            source_spans=document_intelligence["source_spans"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_retrieval_report(summary, retrieval_report)
        extraction_payload = build_candidate_rules_from_retrieval(
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_extraction_payload(summary, extraction_payload)
        verification_payload = build_verification_outputs(
            candidate_rules=extraction_payload["candidate_rules"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_verification_payload(summary, verification_payload)
        repair_review_payload = build_guarded_repair_rerun_outputs(
            review_queue=verification_payload["review_queue"],
            retrieval_report=retrieval_report,
            city_key=args.city,
            run_id=run_id,
            rule_contract_families=_rule_contract_families(args.city),
            preverified_rules=verification_payload["verified_rules"],
            preverified_decisions=_promoted_decisions(verification_payload),
            initial_candidate_count=len(extraction_payload["candidate_rules"]),
        )
        summary = with_guarded_repair_payload(summary, repair_review_payload)
        gis_compliance_payload = build_gis_compliance_outputs(
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_gis_compliance_payload(summary, gis_compliance_payload)
        chatbot_eval_payload = build_chatbot_eval_outputs(
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            gis_rule_contract=gis_compliance_payload["gis_rule_contract"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_chatbot_eval_payload(summary, chatbot_eval_payload)
        benchmark_eval_payload = build_benchmark_eval_outputs(
            source_spans=document_intelligence["source_spans"],
            candidate_rules=extraction_payload["candidate_rules"],
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            gis_rule_contract=gis_compliance_payload["gis_rule_contract"],
            city_key=args.city,
            run_id=run_id,
            root=ROOT,
        )
        summary = with_benchmark_eval_payload(summary, benchmark_eval_payload)
        product_operations_payload = build_product_operations_outputs(
            verified_rules=repair_review_payload["verified_rules"],
            review_queue=repair_review_payload["review_queue"],
            gis_rule_contract=gis_compliance_payload["gis_rule_contract"],
            city_key=args.city,
            run_id=run_id,
        )
        summary = with_product_operations_payload(summary, product_operations_payload)
        command_center_app_payload = build_command_center_app_outputs(
            summary=summary,
            gis_rule_contract=gis_compliance_payload["gis_rule_contract"],
            compliance_report=gis_compliance_payload["compliance_report"],
            compliance_decisions=gis_compliance_payload["compliance_decisions"],
            chatbot_eval=chatbot_eval_payload,
            review_queue=repair_review_payload["review_queue"],
            benchmark_eval=benchmark_eval_payload,
            city_key=args.city,
            run_id=run_id,
            app_version="checkpoint_16",
            operation_artifacts=product_operations_payload["operation_artifacts"],
            operation_metrics=product_operations_payload["operations_report"],
        )
        summary = with_command_center_app_payload(summary, command_center_app_payload)
        summary = with_product_operations_payload(summary, product_operations_payload)
    if args.print_only:
        payload = {"summary": summary}
        if source_registry is not None:
            payload["source_registry"] = source_registry
        if document_intelligence is not None:
            payload["document_intelligence"] = {
                key: value for key, value in document_intelligence.items() if key not in {"document_blocks", "source_spans"}
            }
        if retrieval_report is not None:
            payload["retrieval_report"] = retrieval_report
        if extraction_payload is not None:
            payload["extraction"] = extraction_payload
        if verification_payload is not None:
            payload["verification"] = verification_payload
        if repair_review_payload is not None:
            payload["repair_review"] = repair_review_payload
        if gis_compliance_payload is not None:
            payload["gis_compliance"] = gis_compliance_payload
        if chatbot_eval_payload is not None:
            payload["chatbot_eval"] = chatbot_eval_payload
        if command_center_payload is not None:
            payload["command_center"] = command_center_payload["command_center_manifest"]
        if command_center_app_payload is not None:
            payload["command_center_app"] = command_center_app_payload["command_center_app_manifest"]
        if product_operations_payload is not None:
            payload["product_operations"] = product_operations_payload["operations_report"]
        if multi_city_payload is not None:
            payload["multi_city"] = multi_city_payload
        if benchmark_eval_payload is not None:
            payload["benchmark_eval"] = benchmark_eval_payload
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if summary["safety"]["existing_safety_reproduced"] else 1

    out_city = "multi_city" if args.checkpoint == "multi_city" else args.city
    out_dir = Path(args.output_root) / out_city / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    if source_registry is not None:
        write_source_registry(source_registry, out_dir)
    if document_intelligence is not None:
        write_document_intelligence(document_intelligence, out_dir)
    if retrieval_report is not None:
        write_retrieval_report(retrieval_report, out_dir)
    if extraction_payload is not None:
        write_candidate_rules(extraction_payload, out_dir)
    if verification_payload is not None:
        write_verification_outputs(verification_payload, out_dir)
    if repair_review_payload is not None:
        write_repair_review_outputs(repair_review_payload, out_dir)
    if gis_compliance_payload is not None:
        write_gis_compliance_outputs(gis_compliance_payload, out_dir)
    if chatbot_eval_payload is not None:
        write_chatbot_eval_outputs(chatbot_eval_payload, out_dir)
    if command_center_payload is not None:
        write_command_center_outputs(command_center_payload, out_dir)
    if command_center_app_payload is not None:
        write_command_center_app_outputs(command_center_app_payload, out_dir)
    if product_operations_payload is not None:
        write_product_operations_outputs(product_operations_payload, out_dir)
    if multi_city_payload is not None:
        write_multi_city_report(multi_city_payload, out_dir)
    if benchmark_eval_payload is not None:
        write_benchmark_eval_outputs(benchmark_eval_payload, out_dir)
    (out_dir / "f1_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "checkpoint_report.md").write_text(render_checkpoint_report(summary), encoding="utf-8")
    print(f"[f1] wrote {out_dir}")
    return 0 if summary["safety"]["existing_safety_reproduced"] else 1


def default_run_id(checkpoint: str) -> str:
    if checkpoint == "product_operations":
        return "checkpoint_16_product_operations"
    if checkpoint == "command_center_app":
        return "checkpoint_15_command_center_app"
    if checkpoint == "benchmark_eval":
        return "checkpoint_14_benchmark_eval"
    if checkpoint == "multi_city":
        return "checkpoint_13_multi_city"
    if checkpoint == "model_chatbot_redteam":
        return "checkpoint_12_model_chatbot_redteam"
    if checkpoint == "model_chatbot_eval":
        return "checkpoint_11_model_chatbot_eval"
    if checkpoint == "command_center":
        return "checkpoint_10_command_center"
    if checkpoint == "chatbot_eval":
        return "checkpoint_9_chatbot_eval"
    if checkpoint == "gis_compliance":
        return "checkpoint_8_gis_compliance"
    if checkpoint == "guarded_repair":
        return "checkpoint_7_guarded_repair"
    if checkpoint == "repair_review":
        return "checkpoint_6_repair_review"
    if checkpoint == "verification":
        return "checkpoint_5_verification"
    if checkpoint == "structured_extraction":
        return "checkpoint_4_structured_extraction"
    if checkpoint == "proof_rag":
        return "checkpoint_3_proof_rag"
    if checkpoint == "document_intelligence":
        return "checkpoint_2_document_intelligence"
    if checkpoint == "source_registry":
        return "checkpoint_1_source_registry"
    return DEFAULT_RUN_ID


def build_checkpoint_summary(*, city: str, run_id: str, status_report: Path) -> dict[str, Any]:
    report = _read_json(status_report) if status_report.exists() else {}
    false_verified_total = _to_int(report.get("current_false_verified_total"))
    unsafe_rows = report.get("unsafe_current_rows") or []
    existing_safety_reproduced = bool(report) and false_verified_total == 0 and not unsafe_rows
    manifest = artifact_manifest(city=city, run_id=run_id, source_id="", bylaw_version="")
    return {
        **manifest,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checkpoint": "F1 checkpoint 0",
        "purpose": "Create the F1 product surface while preserving the existing verifier safety boundary.",
        "constitution_rules": list(F1_CONSTITUTION_RULES),
        "documents": {
            "constitution": "docs/F1_CONSTITUTION.md",
            "artifact_contracts": "docs/F1_ARTIFACT_CONTRACTS.md",
            "engineering_plan": "docs/F1_ENGINEERING_PLAN.md",
            "living_textbook": "F1_TEXTBOOK.ipynb",
            "m_series_archive_index": "archive/m_series/README.md",
        },
        "safety": {
            "existing_safety_reproduced": existing_safety_reproduced,
            "status_report": str(status_report.relative_to(ROOT)) if status_report.is_relative_to(ROOT) else str(status_report),
            "overall_status": report.get("overall_status"),
            "current_false_verified_total": false_verified_total,
            "unsafe_current_rows": unsafe_rows,
            "false_approval_count_boundary": 0,
            "f1_promotes_rules": False,
            "f1_exports_gis": False,
        },
        "next_checkpoint": "Build source registry and official-document provenance for F1.",
    }


def with_source_registry(summary: dict[str, Any], source_registry: dict[str, Any]) -> dict[str, Any]:
    current = dict(summary)
    validation = source_registry.get("validation") or {}
    current.update(
        {
            "checkpoint": "F1 checkpoint 1",
            "purpose": "Build the F1 source registry and verify official-source provenance before document intelligence.",
            "source_registry": {
                "artifact": "source_registry.json",
                "source_count": source_registry.get("source_count", 0),
                "validation_status": validation.get("status"),
                "sha256_matches": validation.get("sha256_matches"),
                "source_pdf_exists": validation.get("source_pdf_exists"),
                "provenance_exists": validation.get("provenance_exists"),
            },
            "next_checkpoint": "Add Docling-first document intelligence with fallback parsing.",
        }
    )
    current["safety"] = {
        **current["safety"],
        "f1_source_registry_status": validation.get("status"),
    }
    return current


def with_document_intelligence(summary: dict[str, Any], document_intelligence: dict[str, Any]) -> dict[str, Any]:
    current = dict(summary)
    doc_summary = document_intelligence.get("summary") or {}
    current.update(
        {
            "checkpoint": "F1 checkpoint 2",
            "purpose": "Parse the registered bylaw source into F1 document blocks and source spans.",
            "document_intelligence": {
                "document_blocks": "document_blocks.json",
                "source_spans": "source_spans.json",
                "report": "document_intelligence_report.json",
                "ingest_backend": document_intelligence.get("ingest_backend"),
                "page_count": doc_summary.get("page_count", 0),
                "document_block_count": doc_summary.get("document_block_count", 0),
                "source_span_count": doc_summary.get("source_span_count", 0),
                "table_block_count": doc_summary.get("table_block_count", 0),
            },
            "next_checkpoint": "Build proof-aware RAG with BM25, dense vectors, RRF, pluggable reranker, and retrieval-quality evaluation.",
        }
    )
    current["safety"] = {
        **current["safety"],
        "f1_document_intelligence_promotes_rules": False,
    }
    return current


def with_retrieval_report(summary: dict[str, Any], retrieval_report: dict[str, Any]) -> dict[str, Any]:
    current = dict(summary)
    rag_summary = retrieval_report.get("summary") or {}
    current.update(
        {
            "checkpoint": "F1 checkpoint 3",
            "purpose": "Build proof-aware retrieval over F1 source spans without giving retrieval promotion authority.",
            "retrieval": {
                "artifact": "retrieval_report.json",
                "retrieval_method": retrieval_report.get("retrieval_method"),
                "reranker": retrieval_report.get("reranker"),
                "query_count": rag_summary.get("query_count", 0),
                "queries_with_hits": rag_summary.get("queries_with_hits", 0),
                "total_hit_count": rag_summary.get("total_hit_count", 0),
                "retrieval_quality_status": rag_summary.get("retrieval_quality_status"),
            },
            "next_checkpoint": "Add extraction with strict structured outputs and field-level citations.",
        }
    )
    current["safety"] = {
        **current["safety"],
        "f1_retrieval_promotes_rules": False,
    }
    return current


def with_extraction_payload(summary: dict[str, Any], extraction_payload: dict[str, Any]) -> dict[str, Any]:
    current = dict(summary)
    report = extraction_payload.get("extraction_report") or {}
    current.update(
        {
            "checkpoint": "F1 checkpoint 4",
            "purpose": "Extract structured review-needed candidate rules with field-level citations.",
            "extraction": {
                "candidate_rules": "candidate_rules.json",
                "report": "extraction_report.json",
                "method": report.get("method"),
                "candidate_count": report.get("candidate_count", 0),
                "skipped_count": report.get("skipped_count", 0),
                "promoted_count": report.get("promoted_count", 0),
                "all_candidates_review_needed": report.get("all_candidates_review_needed"),
            },
            "next_checkpoint": "Add deterministic verification with exact support checks for F1 candidates.",
        }
    )
    current["safety"] = {
        **current["safety"],
        "f1_extraction_promotes_rules": False,
    }
    return current


def with_verification_payload(summary: dict[str, Any], verification_payload: dict[str, Any]) -> dict[str, Any]:
    current = dict(summary)
    report = verification_payload.get("verification_report") or {}
    status_counts = report.get("status_counts") or {}
    current.update(
        {
            "checkpoint": "F1 checkpoint 5",
            "purpose": "Run deterministic fail-closed verification over F1 candidate rules.",
            "verification": {
                "verification_decisions": "verification_decisions.json",
                "verified_rules": "verified_rules.json",
                "review_queue": "review_queue.json",
                "report": "verification_report.json",
                "candidate_count": report.get("candidate_count", 0),
                "verified_count": report.get("verified_count", 0),
                "review_queue_count": report.get("review_queue_count", 0),
                "false_verified_count": report.get("false_verified_count", 0),
                "status_counts": status_counts,
            },
            "next_checkpoint": "Add repair/review loop using gap-specific retrieval and guarded verifier reruns.",
        }
    )
    current["safety"] = {
        **current["safety"],
        "f1_promotes_rules": report.get("verified_count", 0) > 0,
        "f1_false_verified_count": report.get("false_verified_count", 0),
        "f1_gis_verified_only_ready": report.get("verified_count", 0) >= 0,
    }
    return current


def with_repair_review_payload(summary: dict[str, Any], repair_review_payload: dict[str, Any]) -> dict[str, Any]:
    current = dict(summary)
    report = repair_review_payload.get("repair_rerun_report") or {}
    current.update(
        {
            "checkpoint": "F1 checkpoint 6",
            "purpose": "Package uncertain verifier decisions into repair attempts and human review packets without direct promotion.",
            "repair_review": {
                "repair_attempts": "repair_attempts.json",
                "review_packets": "review_packets.json",
                "repair_rerun_report": "repair_rerun_report.json",
                "repair_attempt_count": len(repair_review_payload.get("repair_attempts") or []),
                "review_packet_count": len(repair_review_payload.get("review_packets") or []),
                "eligible_rule_count": report.get("eligible_rule_count", 0),
                "verifier_rerun_attempt_count": report.get("attempt_count", 0),
                "guarded_repair_promotion_count": report.get("guarded_repair_promotion_count", 0),
                "false_verified_count": report.get("false_verified_count", 0),
            },
            "next_checkpoint": "Add proof-patch generation and guarded verifier reruns, still verifier-only.",
        }
    )
    current["safety"] = {
        **current["safety"],
        "f1_repair_promotes_directly": False,
        "f1_repair_guarded_promotions": report.get("guarded_repair_promotion_count", 0),
        "f1_false_verified_count": report.get("false_verified_count", 0),
    }
    return current


def with_guarded_repair_payload(summary: dict[str, Any], repair_review_payload: dict[str, Any]) -> dict[str, Any]:
    current = with_repair_review_payload(summary, repair_review_payload)
    report = repair_review_payload.get("repair_rerun_report") or {}
    verification_report = repair_review_payload.get("verification_report") or {}
    current.update(
        {
            "checkpoint": "F1 checkpoint 7",
            "purpose": "Run deterministic proof patches through the verifier and apply guarded repair promotions only after verifier proof.",
            "verification": {
                "verification_decisions": "verification_decisions.json",
                "verified_rules": "verified_rules.json",
                "review_queue": "review_queue.json",
                "report": "verification_report.json",
                "candidate_count": verification_report.get("candidate_count", 0),
                "verified_count": verification_report.get("verified_count", 0),
                "review_queue_count": verification_report.get("review_queue_count", 0),
                "false_verified_count": verification_report.get("false_verified_count", 0),
                "status_counts": verification_report.get("status_counts") or {},
            },
            "repair_review": {
                **current.get("repair_review", {}),
                "verifier_rerun_requests": "verifier_rerun_requests.json",
                "guarded_repair_promotions": "guarded_repair_promotions.json",
                "review_needed_after_repair": verification_report.get("review_queue_count", 0),
                "review_needed_reduction_from_repair_rerun": report.get("review_needed_reduction_from_repair_rerun", 0),
            },
            "next_checkpoint": "Add verified-only GIS/compliance export after benchmark review.",
        }
    )
    current["safety"] = {
        **current["safety"],
        "f1_promotes_rules": verification_report.get("verified_count", 0) > 0,
        "f1_repair_promotes_directly": False,
        "f1_repair_guarded_promotions": report.get("guarded_repair_promotion_count", 0),
        "f1_false_verified_count": verification_report.get("false_verified_count", 0),
    }
    return current


def with_gis_compliance_payload(summary: dict[str, Any], gis_compliance_payload: dict[str, Any]) -> dict[str, Any]:
    current = dict(summary)
    contract = gis_compliance_payload.get("gis_rule_contract") or {}
    report = gis_compliance_payload.get("compliance_report") or {}
    current.update(
        {
            "checkpoint": "F1 checkpoint 8",
            "purpose": "Project verifier-promoted rules into verified-only GIS and tri-state compliance artifacts.",
            "gis_compliance": {
                "gis_rule_contract": "gis_rule_contract.json",
                "compliance_decisions": "compliance_decisions.json",
                "compliance_report": "compliance_report.json",
                "verified_only": contract.get("verified_only"),
                "input_verified_rule_count": contract.get("input_verified_rule_count", 0),
                "export_rule_count": contract.get("export_rule_count", 0),
                "excluded_review_rule_count": contract.get("excluded_review_rule_count", 0),
                "scenario_count": report.get("scenario_count", 0),
                "status_counts": report.get("status_counts") or {},
                "false_approval_count": report.get("false_approval_count", 0),
            },
            "next_checkpoint": "Add command center dashboard and source-cited chatbot over F1 artifacts.",
        }
    )
    current["safety"] = {
        **current["safety"],
        "f1_exports_gis": True,
        "f1_gis_verified_only": contract.get("verified_only"),
        "f1_false_approval_count": report.get("false_approval_count", 0),
    }
    return current


def with_chatbot_eval_payload(summary: dict[str, Any], chatbot_eval_payload: dict[str, Any]) -> dict[str, Any]:
    current = dict(summary)
    metrics = chatbot_eval_payload.get("metrics") or {}
    chatbot = chatbot_eval_payload.get("chatbot") or {}
    current.update(
        {
            "checkpoint": "F1 checkpoint 9",
            "purpose": "Evaluate source-cited chatbot grounding and approval-refusal boundaries over F1 artifacts.",
            "chatbot_eval": {
                "artifact": "chatbot_eval.json",
                "runtime": chatbot.get("runtime"),
                "model": chatbot.get("model"),
                "intended_model_runtime": chatbot.get("intended_model_runtime"),
                "model_runtime_used": chatbot.get("model_runtime_used"),
                "case_count": metrics.get("case_count", 0),
                "model_answer_count": metrics.get("model_answer_count", 0),
                "safety_guard_count": metrics.get("safety_guard_count", 0),
                "answered_count": metrics.get("answered_count", 0),
                "uncertain_count": metrics.get("uncertain_count", 0),
                "cited_answer_count": metrics.get("cited_answer_count", 0),
                "approval_claim_count": metrics.get("approval_claim_count", 0),
                "false_approval_count": metrics.get("false_approval_count", 0),
            },
            "next_checkpoint": "Add command center dashboard UI over F1 artifacts, then plug in the real model-backed chatbot runtime.",
        }
    )
    current["safety"] = {
        **current["safety"],
        "f1_chatbot_approves": metrics.get("approval_claim_count", 0) > 0,
        "f1_chatbot_false_approval_count": metrics.get("false_approval_count", 0),
    }
    return current


def with_model_chatbot_eval_payload(summary: dict[str, Any], chatbot_eval_payload: dict[str, Any]) -> dict[str, Any]:
    current = with_chatbot_eval_payload(summary, chatbot_eval_payload)
    current.update(
        {
            "checkpoint": "F1 checkpoint 11",
            "purpose": "Run real GPT-OSS-120B RAG chatbot evaluation over bounded F1 context.",
            "next_checkpoint": "Harden model-backed chatbot prompts against observed failures and expand eval cases.",
        }
    )
    return current


def with_model_chatbot_redteam_payload(summary: dict[str, Any], chatbot_eval_payload: dict[str, Any]) -> dict[str, Any]:
    current = dict(summary)
    metrics = chatbot_eval_payload.get("metrics") or {}
    chatbot = chatbot_eval_payload.get("chatbot") or {}
    current.update(
        {
            "checkpoint": "F1 checkpoint 12",
            "purpose": "Run real GPT-OSS-120B adversarial and follow-up chatbot evaluation over bounded F1 context.",
            "chatbot_eval": {
                "artifact": "chatbot_redteam_eval.json",
                "runtime": chatbot.get("runtime"),
                "model": chatbot.get("model"),
                "intended_model_runtime": chatbot.get("intended_model_runtime"),
                "model_runtime_used": chatbot.get("model_runtime_used"),
                "case_count": metrics.get("case_count", 0),
                "model_answer_count": metrics.get("model_answer_count", 0),
                "safety_guard_count": metrics.get("safety_guard_count", 0),
                "passed_count": metrics.get("passed_count", 0),
                "failed_count": metrics.get("failed_count", 0),
                "failed_cases": metrics.get("failed_cases") or [],
                "citation_missing_count": metrics.get("citation_missing_count", 0),
                "refusal_missing_count": metrics.get("refusal_missing_count", 0),
                "approval_claim_count": metrics.get("approval_claim_count", 0),
                "false_approval_count": metrics.get("false_approval_count", 0),
            },
            "next_checkpoint": "Use red-team results to harden prompt/runtime further, then run multi-city F1 expansion.",
        }
    )
    current["safety"] = {
        **current["safety"],
        "f1_chatbot_approves": metrics.get("approval_claim_count", 0) > 0,
        "f1_chatbot_false_approval_count": metrics.get("false_approval_count", 0),
        "f1_chatbot_redteam_passed": metrics.get("failed_count", 0) == 0,
    }
    return current


def with_command_center_payload(summary: dict[str, Any], command_center_payload: dict[str, Any]) -> dict[str, Any]:
    current = dict(summary)
    manifest = command_center_payload.get("command_center_manifest") or {}
    current.update(
        {
            "checkpoint": "F1 checkpoint 10",
            "purpose": "Render a command-center preview from current F1 artifacts.",
            "command_center": {
                "manifest": "command_center_manifest.json",
                "preview": "command_center_preview.html",
                "card_count": len(manifest.get("cards") or []),
                "verified_rule_count": len(manifest.get("verified_rules") or []),
                "review_queue_count": len(manifest.get("review_queue") or []),
            },
            "next_checkpoint": "Plug in the real GPT-OSS-120B + RAG chatbot runtime and run model-backed evals.",
        }
    )
    return current


def with_command_center_app_payload(summary: dict[str, Any], command_center_app_payload: dict[str, Any]) -> dict[str, Any]:
    current = dict(summary)
    manifest = command_center_app_payload.get("command_center_app_manifest") or {}
    workflow_health = manifest.get("workflow_health") or {}
    current.update(
        {
            "checkpoint": "F1 checkpoint 15",
            "purpose": "Render an interactive command-center app from measured F1 artifacts.",
            "command_center_app": {
                "manifest": "command_center_app_manifest.json",
                "app": "command_center_app.html",
                "card_count": len(manifest.get("cards") or []),
                "workflow_count": len(manifest.get("product_workflows") or []),
                "verified_rule_count": workflow_health.get("verified_rule_count", 0),
                "review_queue_count": workflow_health.get("review_queue_count", 0),
                "quality_gates_passed": workflow_health.get("quality_gates_passed"),
                "false_verified_count": workflow_health.get("false_verified_count", 0),
                "false_approval_count": workflow_health.get("false_approval_count", 0),
            },
            "next_checkpoint": "Turn command-center interactions into a served product UI with persisted review actions and model-backed chat.",
        }
    )
    current["safety"] = {
        **current["safety"],
        "f1_command_center_app_writes_decisions": False,
        "f1_command_center_app_quality_gates_passed": workflow_health.get("quality_gates_passed"),
    }
    return current


def with_product_operations_payload(summary: dict[str, Any], product_operations_payload: dict[str, Any]) -> dict[str, Any]:
    current = dict(summary)
    report = product_operations_payload.get("operations_report") or {}
    current.update(
        {
            "checkpoint": "F1 checkpoint 16",
            "purpose": "Turn the F1 command center into an operator-facing product surface with safe review actions, scenario templates, and evidence navigation.",
            "product_operations": {
                "operator_action_templates": "operator_action_templates.json",
                "operator_review_actions": "operator_review_actions.json",
                "scenario_templates": "scenario_templates.json",
                "evidence_navigation": "evidence_navigation.json",
                "operations_report": "operations_report.json",
                "action_template_count": report.get("action_template_count", 0),
                "scenario_template_count": report.get("scenario_template_count", 0),
                "evidence_navigation_count": report.get("evidence_navigation_count", 0),
                "operator_actions_persisted_count": report.get("operator_actions_persisted_count", 0),
                "writes_rule_status": report.get("writes_rule_status"),
                "writes_gis_contract": report.get("writes_gis_contract"),
                "verified_only_boundary_preserved": report.get("verified_only_boundary_preserved"),
            },
            "next_checkpoint": "Connect live model-backed chat and multi-city product runs while preserving benchmark gates.",
        }
    )
    current["safety"] = {
        **current["safety"],
        "f1_product_operations_writes_rule_status": report.get("writes_rule_status"),
        "f1_product_operations_writes_gis_contract": report.get("writes_gis_contract"),
        "f1_product_operations_verified_only_boundary_preserved": report.get("verified_only_boundary_preserved"),
    }
    return current


def with_multi_city_payload(summary: dict[str, Any], multi_city_payload: dict[str, Any]) -> dict[str, Any]:
    current = dict(summary)
    current.update(
        {
            "checkpoint": "F1 checkpoint 13",
            "purpose": "Run F1 artifact generation across multiple cities and label benchmark coverage honestly.",
            "multi_city": {
                "artifact": "f1_multi_city_report.json",
                "report": "f1_multi_city_report.md",
                "prefer_docling": multi_city_payload.get("prefer_docling"),
                "city_count": multi_city_payload.get("city_count", 0),
                "completed_city_count": multi_city_payload.get("completed_city_count", 0),
                "failed_city_count": multi_city_payload.get("failed_city_count", 0),
                "release_safe_city_count": multi_city_payload.get("release_safe_city_count", 0),
                "exploratory_city_count": multi_city_payload.get("exploratory_city_count", 0),
                "false_verified_total": multi_city_payload.get("false_verified_total", 0),
                "false_approval_total": multi_city_payload.get("false_approval_total", 0),
                "runtime_seconds": multi_city_payload.get("runtime_seconds", 0),
            },
            "next_checkpoint": "Use multi-city results to improve city-aware retrieval/extraction while preserving verifier precision.",
        }
    )
    current["safety"] = {
        **current["safety"],
        "f1_multi_city_false_verified_total": multi_city_payload.get("false_verified_total", 0),
        "f1_multi_city_false_approval_total": multi_city_payload.get("false_approval_total", 0),
        "f1_multi_city_completed": multi_city_payload.get("failed_city_count", 0) == 0,
    }
    return current


def with_benchmark_eval_payload(summary: dict[str, Any], benchmark_eval_payload: dict[str, Any]) -> dict[str, Any]:
    current = dict(summary)
    retrieval = (benchmark_eval_payload.get("retrieval_benchmark") or {}).get("metrics") or {}
    rules = benchmark_eval_payload.get("rule_metrics") or {}
    gis = benchmark_eval_payload.get("gis_contract_metrics") or {}
    proposal = benchmark_eval_payload.get("proposal_metrics") or {}
    gates = benchmark_eval_payload.get("quality_gates") or {}
    current.update(
        {
            "checkpoint": "F1 checkpoint 14",
            "purpose": "Evaluate F1 artifacts against gold rules, proposal cases, and release safety gates.",
            "benchmark_eval": {
                "artifact": "f1_benchmark_report.json",
                "report": "f1_benchmark_report.md",
                "gold_rule_count": rules.get("gold_rule_count", 0),
                "retrieval_recall_at_6": retrieval.get("retrieval_recall_at_6", 0),
                "candidate_recall": rules.get("candidate_recall", 0),
                "verified_precision": rules.get("verified_precision", 0),
                "verified_recall": rules.get("verified_recall", 0),
                "false_verified_count": rules.get("false_verified_count", 0),
                "verified_source_support_failed_count": rules.get("verified_source_support_failed_count", 0),
                "gis_verified_only": gis.get("verified_only"),
                "gis_review_rule_leak_count": gis.get("review_rule_leak_count", 0),
                "proposal_case_count": proposal.get("proposal_case_count", 0),
                "proposal_decision_accuracy": proposal.get("proposal_decision_accuracy", 0),
                "proposal_case_accuracy": proposal.get("proposal_case_accuracy", 0),
                "false_approval_count": proposal.get("false_approval_count", 0),
                "quality_gates_passed": gates.get("passed"),
                "failed_gates": gates.get("failed_gates") or [],
            },
            "next_checkpoint": "Use benchmark failures to improve retrieval/extraction coverage without weakening verifier precision.",
        }
    )
    current["safety"] = {
        **current["safety"],
        "f1_benchmark_promotes_rules": False,
        "f1_benchmark_approves_proposals": False,
        "f1_benchmark_false_verified_count": rules.get("false_verified_count", 0),
        "f1_benchmark_false_approval_count": proposal.get("false_approval_count", 0),
        "f1_benchmark_quality_gates_passed": gates.get("passed"),
    }
    return current


def render_checkpoint_report(summary: dict[str, Any]) -> str:
    safety = summary["safety"]
    artifact_lines = "\n".join(f"- `{name}`" for name in summary["artifact_names"])
    rules = "\n".join(f"{index}. {rule}" for index, rule in enumerate(summary["constitution_rules"], start=1))
    source_registry = summary.get("source_registry") or {}
    source_registry_section = ""
    if source_registry:
        source_registry_section = f"""
## Source Registry

| Metric | Value |
|---|---:|
| Source count | `{source_registry.get("source_count")}` |
| Validation status | `{source_registry.get("validation_status")}` |
| Source PDF exists | `{str(source_registry.get("source_pdf_exists")).lower()}` |
| Provenance exists | `{str(source_registry.get("provenance_exists")).lower()}` |
| SHA-256 matches | `{str(source_registry.get("sha256_matches")).lower()}` |
"""
    document_intelligence = summary.get("document_intelligence") or {}
    document_intelligence_section = ""
    if document_intelligence:
        document_intelligence_section = f"""
## Document Intelligence

| Metric | Value |
|---|---:|
| Ingest backend | `{document_intelligence.get("ingest_backend")}` |
| Pages parsed | `{document_intelligence.get("page_count")}` |
| Document blocks | `{document_intelligence.get("document_block_count")}` |
| Source spans | `{document_intelligence.get("source_span_count")}` |
| Table blocks | `{document_intelligence.get("table_block_count")}` |
"""
    retrieval = summary.get("retrieval") or {}
    retrieval_section = ""
    if retrieval:
        retrieval_section = f"""
## Proof-Aware RAG

| Metric | Value |
|---|---:|
| Retrieval method | `{retrieval.get("retrieval_method")}` |
| Reranker | `{retrieval.get("reranker")}` |
| Queries | `{retrieval.get("query_count")}` |
| Queries with hits | `{retrieval.get("queries_with_hits")}` |
| Total hits | `{retrieval.get("total_hit_count")}` |
| Retrieval status | `{retrieval.get("retrieval_quality_status")}` |
"""
    extraction = summary.get("extraction") or {}
    extraction_section = ""
    if extraction:
        extraction_section = f"""
## Structured Extraction

| Metric | Value |
|---|---:|
| Method | `{extraction.get("method")}` |
| Candidate rules | `{extraction.get("candidate_count")}` |
| Skipped query families | `{extraction.get("skipped_count")}` |
| Promoted count | `{extraction.get("promoted_count")}` |
| All candidates review-needed | `{str(extraction.get("all_candidates_review_needed")).lower()}` |
"""
    verification = summary.get("verification") or {}
    verification_section = ""
    if verification:
        verification_section = f"""
## Verification

| Metric | Value |
|---|---:|
| Candidate count | `{verification.get("candidate_count")}` |
| Verified count | `{verification.get("verified_count")}` |
| Review queue count | `{verification.get("review_queue_count")}` |
| False verified count | `{verification.get("false_verified_count")}` |
| Status counts | `{verification.get("status_counts")}` |
"""
    repair_review = summary.get("repair_review") or {}
    repair_review_section = ""
    if repair_review:
        repair_review_section = f"""
## Repair And Review

| Metric | Value |
|---|---:|
| Repair attempts | `{repair_review.get("repair_attempt_count")}` |
| Review packets | `{repair_review.get("review_packet_count")}` |
| Eligible proof patches | `{repair_review.get("eligible_rule_count")}` |
| Verifier rerun attempts | `{repair_review.get("verifier_rerun_attempt_count")}` |
| Guarded repair promotions | `{repair_review.get("guarded_repair_promotion_count")}` |
| False verified count | `{repair_review.get("false_verified_count")}` |
"""
    gis_compliance = summary.get("gis_compliance") or {}
    gis_compliance_section = ""
    if gis_compliance:
        gis_compliance_section = f"""
## GIS And Compliance

| Metric | Value |
|---|---:|
| Verified-only contract | `{str(gis_compliance.get("verified_only")).lower()}` |
| GIS export rules | `{gis_compliance.get("export_rule_count")}` |
| Excluded review rules | `{gis_compliance.get("excluded_review_rule_count")}` |
| Compliance smoke scenarios | `{gis_compliance.get("scenario_count")}` |
| Compliance status counts | `{gis_compliance.get("status_counts")}` |
| False approval count | `{gis_compliance.get("false_approval_count")}` |
"""
    chatbot_eval = summary.get("chatbot_eval") or {}
    chatbot_eval_section = ""
    if chatbot_eval:
        chatbot_eval_section = f"""
## Chatbot Evaluation

| Metric | Value |
|---|---:|
| Runtime | `{chatbot_eval.get("runtime")}` |
| Model | `{chatbot_eval.get("model")}` |
| Intended model runtime | `{chatbot_eval.get("intended_model_runtime")}` |
| Model runtime used | `{str(chatbot_eval.get("model_runtime_used")).lower()}` |
| Cases | `{chatbot_eval.get("case_count")}` |
| Answered | `{chatbot_eval.get("answered_count")}` |
| Uncertain/refusal | `{chatbot_eval.get("uncertain_count")}` |
| Cited answers | `{chatbot_eval.get("cited_answer_count")}` |
| Passed red-team cases | `{chatbot_eval.get("passed_count")}` |
| Failed red-team cases | `{chatbot_eval.get("failed_count")}` |
| Citation missing | `{chatbot_eval.get("citation_missing_count")}` |
| Refusal missing | `{chatbot_eval.get("refusal_missing_count")}` |
| Approval claims | `{chatbot_eval.get("approval_claim_count")}` |
| False approvals | `{chatbot_eval.get("false_approval_count")}` |
"""
    command_center = summary.get("command_center") or {}
    command_center_section = ""
    if command_center:
        command_center_section = f"""
## Command Center

| Metric | Value |
|---|---:|
| Preview | `{command_center.get("preview")}` |
| Manifest | `{command_center.get("manifest")}` |
| Cards | `{command_center.get("card_count")}` |
| Verified rules shown | `{command_center.get("verified_rule_count")}` |
| Review items shown | `{command_center.get("review_queue_count")}` |
"""
    command_center_app = summary.get("command_center_app") or {}
    command_center_app_section = ""
    if command_center_app:
        command_center_app_section = f"""
## Command Center App

| Metric | Value |
|---|---:|
| App | `{command_center_app.get("app")}` |
| Manifest | `{command_center_app.get("manifest")}` |
| Cards | `{command_center_app.get("card_count")}` |
| Workflows | `{command_center_app.get("workflow_count")}` |
| Verified rules | `{command_center_app.get("verified_rule_count")}` |
| Review items | `{command_center_app.get("review_queue_count")}` |
| Quality gates passed | `{str(command_center_app.get("quality_gates_passed")).lower()}` |
| False verified | `{command_center_app.get("false_verified_count")}` |
| False approvals | `{command_center_app.get("false_approval_count")}` |
"""
    product_operations = summary.get("product_operations") or {}
    product_operations_section = ""
    if product_operations:
        product_operations_section = f"""
## Product Operations

| Metric | Value |
|---|---:|
| Action templates | `{product_operations.get("action_template_count")}` |
| Scenario templates | `{product_operations.get("scenario_template_count")}` |
| Evidence navigation rows | `{product_operations.get("evidence_navigation_count")}` |
| Operator actions persisted | `{product_operations.get("operator_actions_persisted_count")}` |
| Writes rule status | `{str(product_operations.get("writes_rule_status")).lower()}` |
| Writes GIS contract | `{str(product_operations.get("writes_gis_contract")).lower()}` |
| Verified-only boundary preserved | `{str(product_operations.get("verified_only_boundary_preserved")).lower()}` |
"""
    multi_city = summary.get("multi_city") or {}
    multi_city_section = ""
    if multi_city:
        multi_city_section = f"""
## Multi-City

| Metric | Value |
|---|---:|
| Parser mode | `{"docling-preferred" if multi_city.get("prefer_docling") else "fallback"}` |
| Cities | `{multi_city.get("city_count")}` |
| Completed cities | `{multi_city.get("completed_city_count")}` |
| Failed cities | `{multi_city.get("failed_city_count")}` |
| Release-safe benchmark cities | `{multi_city.get("release_safe_city_count")}` |
| Exploratory/partial cities | `{multi_city.get("exploratory_city_count")}` |
| False verified total | `{multi_city.get("false_verified_total")}` |
| False approval total | `{multi_city.get("false_approval_total")}` |
| Runtime seconds | `{multi_city.get("runtime_seconds")}` |
"""
    benchmark_eval = summary.get("benchmark_eval") or {}
    benchmark_eval_section = ""
    if benchmark_eval:
        benchmark_eval_section = f"""
## Benchmark Evaluation

| Metric | Value |
|---|---:|
| Gold rules | `{benchmark_eval.get("gold_rule_count")}` |
| Retrieval recall at 6 | `{benchmark_eval.get("retrieval_recall_at_6")}` |
| Candidate recall | `{benchmark_eval.get("candidate_recall")}` |
| Verified precision | `{benchmark_eval.get("verified_precision")}` |
| Verified recall | `{benchmark_eval.get("verified_recall")}` |
| False verified count | `{benchmark_eval.get("false_verified_count")}` |
| Verified source-support failures | `{benchmark_eval.get("verified_source_support_failed_count")}` |
| GIS verified-only | `{str(benchmark_eval.get("gis_verified_only")).lower()}` |
| GIS review leaks | `{benchmark_eval.get("gis_review_rule_leak_count")}` |
| Proposal cases | `{benchmark_eval.get("proposal_case_count")}` |
| Proposal decision accuracy | `{benchmark_eval.get("proposal_decision_accuracy")}` |
| Proposal case accuracy | `{benchmark_eval.get("proposal_case_accuracy")}` |
| False approval count | `{benchmark_eval.get("false_approval_count")}` |
| Quality gates passed | `{str(benchmark_eval.get("quality_gates_passed")).lower()}` |
| Failed gates | `{benchmark_eval.get("failed_gates")}` |
"""
    return f"""# {summary["checkpoint"]} Report

Checkpoint: {summary["checkpoint"]}

Purpose: {summary["purpose"]}

## Safety

| Metric | Value |
|---|---:|
| Existing safety reproduced | `{str(safety["existing_safety_reproduced"]).lower()}` |
| Overall status | `{safety.get("overall_status")}` |
| Current false verified total | `{safety["current_false_verified_total"]}` |
| F1 promotes rules in this checkpoint | `{str(safety["f1_promotes_rules"]).lower()}` |
| F1 exports GIS in this checkpoint | `{str(safety["f1_exports_gis"]).lower()}` |
{source_registry_section}
{document_intelligence_section}
{retrieval_section}
{extraction_section}
{verification_section}
{repair_review_section}
{gis_compliance_section}
{chatbot_eval_section}
{command_center_section}
{command_center_app_section}
{product_operations_section}
{multi_city_section}
{benchmark_eval_section}

## Constitution

{rules}

## Canonical Artifacts

{artifact_lines}
"""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rule_contract_families(city_key: str) -> set[str] | None:
    config_path = ROOT / "configs" / f"{city_key}.json"
    if not config_path.exists():
        return None
    config = _read_json(config_path)
    verification = config.get("verification") if isinstance(config.get("verification"), dict) else {}
    families = verification.get("gis_text_rule_contract") if isinstance(verification, dict) else []
    if not isinstance(families, list):
        return None
    normalized = {str(family) for family in families if str(family).strip()}
    return normalized or None


def _promoted_decisions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        decision
        for decision in payload.get("verification_decisions") or []
        if decision.get("status") in {"verified", "repaired_successfully"}
    ]


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
