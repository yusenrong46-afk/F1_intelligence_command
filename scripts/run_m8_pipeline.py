#!/usr/bin/env python3
"""Run the additive M8 pipeline over existing M7 artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from burnaby_prototype.config import load_config, write_json
from burnaby_prototype.m8.analytics.m7_m8_compare import compare_m7_m8
from burnaby_prototype.m8.chatbot.analyst_tools import build_chatbot_context
from burnaby_prototype.m8.extraction.rule_decomposer import decompose_m7_rule
from burnaby_prototype.m8.extraction.rule_schema import M8RunSummary, RepairAttempt, SourceSpan, StructuredRule, VerificationDecision
from burnaby_prototype.m8.ingestion.source_blocks import spans_by_evidence_id, spans_from_evidence_units
from burnaby_prototype.m8.repair.repair_loop import run_repair_loop
from burnaby_prototype.m8.retrieval.hybrid_index import HybridM8Index
from burnaby_prototype.m8.verification.m8_verifier import verify_candidate_with_m7, verify_structured_rule
from burnaby_prototype.m8.verification.verification_report import summarize_decisions


REQUIRED_INPUTS = (
    "evidence_units.json",
    "verified_rules.json",
    "review_needed.json",
    "rejected_rules.json",
    "not_used.json",
    "benchmark_report.json",
    "slim_summary.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(ROOT / "configs" / "burnaby_r1.json"))
    parser.add_argument("--city", default="burnaby_r1")
    parser.add_argument(
        "--input-dir",
        default=str(ROOT / "outputs" / "m7_runs" / "burnaby_r1" / "google_gemini_3_1_flash_lite"),
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "outputs" / "m8_runs" / "burnaby_r1" / "local_m8"),
    )
    parser.add_argument("--max-repair-attempts", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true", help="Run deterministic M8 MVP without external calls.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    missing = [name for name in REQUIRED_INPUTS if not (input_dir / name).exists()]
    if missing:
        print(f"M8 input directory is missing required files: {', '.join(missing)}", file=sys.stderr)
        return 2

    config = load_config(args.config)
    evidence_units = read_json(input_dir / "evidence_units.json", [])
    verified_rules = read_json(input_dir / "verified_rules.json", [])
    review_rules = read_json(input_dir / "review_needed.json", [])
    rejected_rules = read_json(input_dir / "rejected_rules.json", [])
    not_used_rules = read_json(input_dir / "not_used.json", [])
    benchmark = read_json(input_dir / "benchmark_report.json", {})
    m7_summary = read_json(input_dir / "slim_summary.json", {})
    bundle_promoted_ids = {
        str(row.get("rule_id"))
        for row in read_json(input_dir / "bundle_promoted_rules.json", [])
        if row.get("rule_id")
    }

    spans = spans_from_evidence_units(
        evidence_units,
        city=args.city,
        document_id=str(config.get("source_document") or "source.pdf"),
    )
    span_lookup = spans_by_evidence_id(spans)
    index = HybridM8Index(spans)

    structured_rules: list[StructuredRule] = []
    decisions: list[VerificationDecision] = []
    repair_attempts: list[RepairAttempt] = []
    evidence_bundles: list[dict[str, Any]] = []

    for row in verified_rules:
        status = "repaired_successfully" if str(row.get("rule_id")) in bundle_promoted_ids else "verified"
        if status == "repaired_successfully":
            row = {**row, "m8_repair_source": "m7_guarded_bundle_promotion"}
        structured, decision = evaluate_existing_rule(row, args.city, config, span_lookup, status=status)
        structured_rules.append(structured)
        decisions.append(decision)

    def verifier(candidate: dict[str, Any], history: tuple[RepairAttempt, ...]) -> VerificationDecision:
        return verify_candidate_with_m7(
            config=config,
            evidence_units=evidence_units,
            candidate=candidate,
            repair_history=history,
        )

    for row in review_rules:
        repair = run_repair_loop(
            {**row, "city": args.city},
            index=index,
            verifier=verifier,
            max_attempts=args.max_repair_attempts,
        )
        decision = repair["best_decision"]
        attempts = list(repair["attempts"])
        repair_attempts.extend(attempts)
        evidence_bundles.extend(bundle.to_dict() for bundle in repair["evidence_bundles"])
        best_candidate = repair["best_candidate"]
        status = decision.status
        synthetic = {
            **row,
            **best_candidate,
            "rule_id": row.get("rule_id") or best_candidate.get("candidate_id"),
            "verification_decision": status,
            "support_gaps": list(decision.support_gaps),
            "m8_repair_attempt_count": repair["attempt_count"],
            "m8_stopped_reason": repair["stopped_reason"],
        }
        span = span_lookup.get(str(best_candidate.get("evidence_id") or row.get("evidence_id") or ""))
        structured = decompose_m7_rule(
            synthetic,
            city=args.city,
            zone=str(config.get("zone") or ""),
            span=span,
            status=status,
        )
        structured_rules.append(structured)
        decisions.append(decision)

    for row in rejected_rules:
        structured, decision = evaluate_existing_rule(row, args.city, config, span_lookup, status="rejected")
        structured_rules.append(structured)
        decisions.append(decision)
    for row in not_used_rules:
        structured, decision = evaluate_existing_rule(row, args.city, config, span_lookup, status="not_used")
        structured_rules.append(structured)
        decisions.append(decision)

    decision_report = summarize_decisions(decisions)
    for index_, rule in enumerate(structured_rules):
        structured_rules[index_] = replace(rule, status=decisions[index_].status)

    comparison = compare_m7_m8(
        city=args.city,
        m7_benchmark=benchmark,
        m7_summary=m7_summary,
        structured_rules=structured_rules,
        decisions=decisions,
        attempts=repair_attempts,
    )
    status_counts = Counter(decision.status for decision in decisions)
    summary = M8RunSummary(
        city=args.city,
        input_dir=str(input_dir),
        output_dir=str(output_dir),
        status_counts=dict(sorted(status_counts.items())),
        m7_metrics=comparison["m7"],
        m8_metrics=comparison["m8"],
        safety=comparison["safety"],
        artifacts={
            "structured_rules": str(output_dir / "structured_rules.json"),
            "verification_decisions": str(output_dir / "verification_decisions.json"),
            "repair_attempts": str(output_dir / "repair_attempts.json"),
            "m7_m8_comparison": str(output_dir / "m7_m8_comparison.json"),
        },
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "source_spans.json", [span.to_dict() for span in spans])
    write_json(output_dir / "structured_rules.json", [rule.to_dict() for rule in structured_rules])
    write_json(output_dir / "verification_decisions.json", [decision.to_dict() for decision in decisions])
    write_json(output_dir / "repair_attempts.json", [attempt.to_dict() for attempt in repair_attempts])
    write_json(output_dir / "evidence_bundles.json", evidence_bundles)
    write_json(output_dir / "verification_report.json", decision_report)
    write_json(output_dir / "m7_m8_comparison.json", comparison)
    write_json(output_dir / "m8_summary.json", summary.to_dict())
    build_chatbot_context(output_dir)
    (output_dir / "m8_summary.md").write_text(render_summary(summary.to_dict(), comparison), encoding="utf-8")

    print("M8 pipeline complete")
    print(f"Output: {output_dir}")
    print(f"Status counts: {dict(sorted(status_counts.items()))}")
    print(f"M7 safety preserved: {comparison['safety']['m7_safety_preserved']}")
    return 0 if comparison["safety"]["m7_safety_preserved"] else 1


def evaluate_existing_rule(
    row: dict[str, Any],
    city: str,
    config: dict[str, Any],
    span_lookup: dict[str, Any],
    *,
    status: str,
) -> tuple[StructuredRule, VerificationDecision]:
    evidence_id = str(row.get("evidence_id") or (row.get("candidate") or {}).get("evidence_id") or "")
    span = span_lookup.get(evidence_id) or source_span_from_rule(row, city=city, config=config, evidence_id=evidence_id)
    raw = {**row, "verification_decision": status}
    if status in {"verified", "repaired_successfully"} and span is None:
        raw["verification_decision"] = "review_needed"
        status = "review_needed"
    structured = decompose_m7_rule(raw, city=city, zone=str(config.get("zone") or ""), span=span, status=status)
    return structured, verify_structured_rule(structured)


def source_span_from_rule(row: dict[str, Any], *, city: str, config: dict[str, Any], evidence_id: str = "") -> SourceSpan | None:
    source = row.get("source") or {}
    quote = str(
        source.get("evidence_quote")
        or source.get("evidence_text")
        or source.get("source_context")
        or row.get("evidence_quote")
        or ""
    )
    if not quote.strip():
        return None
    return SourceSpan(
        city=city,
        document_id=str(source.get("document") or config.get("source_document") or "source.pdf"),
        page=source.get("page"),
        section_id=str(source.get("section") or row.get("section") or ""),
        block_type="m7_rule_source",
        char_start=0,
        char_end=len(quote),
        text=quote,
        source_url=str(source.get("url") or config.get("source_url") or ""),
        metadata={"evidence_id": evidence_id, "rule_id": row.get("rule_id"), "source": "verified_rule_source"},
    )


def render_summary(summary: dict[str, Any], comparison: dict[str, Any]) -> str:
    m7 = comparison["m7"]
    m8 = comparison["m8"]
    return "\n".join(
        [
            "# M8 Summary",
            "",
            f"City: `{summary['city']}`",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| M7 verified | {m7['verified_count']} |",
            f"| M8 verified | {m8['verified_count']} |",
            f"| M8 repaired successfully | {m8['repaired_successfully_count']} |",
            f"| M8 review needed | {m8['review_needed_count']} |",
            f"| M8 context required | {m8['context_required_count']} |",
            f"| False verified | {m8['false_verified_count']} |",
            "",
            f"Safety preserved: `{comparison['safety']['m7_safety_preserved']}`",
            "",
        ]
    )


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


if __name__ == "__main__":
    raise SystemExit(main())
