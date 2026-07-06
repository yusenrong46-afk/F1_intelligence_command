#!/usr/bin/env python3
"""Run the additive M8.5 workbench pipeline over existing M8 artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from burnaby_prototype.config import load_config, write_json
from burnaby_prototype.native_extraction import load_openrouter_api_key
from burnaby_prototype.m8.extraction.rule_schema import SourceSpan
from burnaby_prototype.m8_5.analytics import compare_m8_to_m8_5
from burnaby_prototype.m8_5.dependencies import CrossReferenceIndex, DependencyGraph, DependencyResolver
from burnaby_prototype.m8_5.llm_repair import (
    FixtureRepairClient,
    OpenRouterRepairClient,
    build_llm_repair_cases,
    disabled_llm_repair_outputs,
    llm_repair_metrics,
    merge_repair_outputs,
    run_llm_repair,
    run_local_table_proof_repair,
)
from burnaby_prototype.m8_5.repair_evaluation import evaluate_repair
from burnaby_prototype.m8_5.repair_evaluation.repair_evaluation import RepairEvaluation
from burnaby_prototype.m8_5.repair_rerun import (
    apply_guarded_repair_promotions,
    disabled_repair_rerun_report,
    repair_rerun_markdown,
    repair_rerun_metrics,
    run_repair_reruns,
)
from burnaby_prototype.m8_5.review import ReviewPacket, VerifierRerunRequest
from burnaby_prototype.m8_5.tables import TableBlock, TableDerivedRule, build_table_cell_lineage, map_table_derived_rules, parse_table_block


REQUIRED_M8_INPUTS = (
    "source_spans.json",
    "structured_rules.json",
    "verification_decisions.json",
    "repair_attempts.json",
    "m7_m8_comparison.json",
    "m8_summary.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", default="burnaby_r1")
    parser.add_argument("--config", default=str(ROOT / "configs" / "burnaby_r1.json"))
    parser.add_argument("--m8-input-dir", default=str(ROOT / "outputs" / "m8_runs" / "burnaby_r1" / "local_m8"))
    parser.add_argument("--m7-input-dir", default=str(ROOT / "outputs" / "m7_runs" / "burnaby_r1" / "google_gemini_3_1_flash_lite"))
    parser.add_argument("--output-dir", default=str(ROOT / "outputs" / "m8_5_runs" / "burnaby_r1" / "local_m8_5"))
    parser.add_argument("--max-repair-attempts", type=int, default=3)
    parser.add_argument("--enable-table-parsing", action="store_true")
    parser.add_argument("--enable-dependency-graph", action="store_true")
    parser.add_argument("--enable-review-packets", action="store_true")
    parser.add_argument("--enable-repair-rerun", action="store_true")
    parser.add_argument("--apply-guarded-repair-promotions", action="store_true")
    parser.add_argument("--enable-llm-repair", action="store_true")
    parser.add_argument("--repair-model", default="google/gemini-3.1-flash-lite")
    parser.add_argument("--repair-llm-max-tokens", type=int, default=1200)
    parser.add_argument("--max-llm-repair-cases", type=int, default=0, help="0 means all review/context rules.")
    parser.add_argument("--llm-repair-max-evidence-snippets", type=int, default=8)
    parser.add_argument("--llm-repair-fixture", default=None, help="Local JSON fixture for deterministic LLM repair tests.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    m8_input_dir = Path(args.m8_input_dir)
    m7_input_dir = Path(args.m7_input_dir)
    output_dir = Path(args.output_dir)
    missing = [name for name in REQUIRED_M8_INPUTS if not (m8_input_dir / name).exists()]
    if missing:
        print(f"M8.5 input directory is missing required files: {', '.join(missing)}", file=sys.stderr)
        return 2
    if args.enable_repair_rerun and not (m7_input_dir / "evidence_units.json").exists():
        print(
            f"M8.5 repair rerun requires original M7 evidence_units.json in: {m7_input_dir}",
            file=sys.stderr,
        )
        return 2
    if args.enable_llm_repair and not args.dry_run and not args.llm_repair_fixture:
        api_key = load_openrouter_api_key(ROOT / ".env")
        if not api_key:
            print(
                "M8.5 LLM repair requires OPENROUTER_API_KEY for non-dry runs "
                "unless --llm-repair-fixture is supplied.",
                file=sys.stderr,
            )
            return 2

    config = load_config(args.config)
    evidence_units = read_json(m7_input_dir / "evidence_units.json", []) if args.enable_repair_rerun else []
    m7_candidates = read_json(m7_input_dir / "rule_candidates.json", []) if args.enable_repair_rerun else []
    source_spans = [SourceSpan.from_dict(row) for row in read_json(m8_input_dir / "source_spans.json", [])]
    structured_rules = read_json(m8_input_dir / "structured_rules.json", [])
    verification_decisions = read_json(m8_input_dir / "verification_decisions.json", [])
    repair_attempts = read_json(m8_input_dir / "repair_attempts.json", [])
    m8_comparison = read_json(m8_input_dir / "m7_m8_comparison.json", {})
    m8_summary = read_json(m8_input_dir / "m8_summary.json", {})

    table_blocks = build_table_blocks(source_spans, city=args.city, zone=str(config.get("zone") or ""), enabled=args.enable_table_parsing)
    table_lineage = [lineage for block in table_blocks for lineage in build_table_cell_lineage(block)]
    table_derived_rules = [rule for block in table_blocks for rule in map_table_derived_rules(block)]

    cross_reference_index = build_cross_reference_index(source_spans)
    resolver = DependencyResolver(cross_reference_index=cross_reference_index)
    dependency_resolutions = [
        resolver.resolve_rule(rule_to_dependency_payload(rule))
        for rule in structured_rules
    ] if args.enable_dependency_graph else []
    dependency_graph = DependencyGraph(
        dependency
        for resolution in dependency_resolutions
        for dependency in resolution.dependencies
    )

    evidence_by_id = evidence_index(source_spans, repair_attempts)
    evidence_by_id.update(evidence_unit_index(evidence_units, config=config))
    rules_by_id = {str(rule.get("rule_id")): rule for rule in structured_rules}
    repair_evaluations = evaluate_repair_attempts(repair_attempts, rules_by_id, evidence_by_id)
    dependencies_by_rule = {
        resolution.rule_id: tuple(resolution.dependencies)
        for resolution in dependency_resolutions
    }
    m8_5_decisions = build_m8_5_decisions(verification_decisions, dependency_resolutions)
    if args.enable_repair_rerun:
        base_repair_rerun_report = run_repair_reruns(
            config=config,
            structured_rules=structured_rules,
            repair_evaluations=repair_evaluations,
            evidence_units=evidence_units,
        )
    else:
        base_repair_rerun_report = disabled_repair_rerun_report()

    llm_repair_outputs = disabled_llm_repair_outputs()
    llm_repair_attempts: list[dict[str, Any]] = []
    llm_repair_evaluations: list[RepairEvaluation] = []
    if args.enable_llm_repair:
        llm_cases = build_llm_repair_cases(
            city=args.city,
            structured_rules=structured_rules,
            verification_decisions=m8_5_decisions,
            source_spans=list(evidence_by_id.values()),
            repair_rerun_report=base_repair_rerun_report,
            max_cases=args.max_llm_repair_cases,
            max_evidence_snippets=args.llm_repair_max_evidence_snippets,
        )
        client = llm_repair_client(args)
        llm_repair_outputs = run_llm_repair(
            cases=llm_cases,
            evidence_by_id=evidence_by_id,
            client=client,
            dry_run=bool(args.dry_run and not args.llm_repair_fixture),
        )
        local_table_repair_outputs = run_local_table_proof_repair(
            cases=llm_cases,
            evidence_by_id=evidence_by_id,
            m7_candidates=m7_candidates,
        )
        llm_repair_outputs = merge_repair_outputs(llm_repair_outputs, local_table_repair_outputs)
        llm_repair_attempts = [dict(row) for row in llm_repair_outputs.get("attempts", [])]
        llm_repair_evaluations = evaluate_repair_attempts(llm_repair_attempts, rules_by_id, evidence_by_id)
        llm_repair_outputs["evaluations"] = [evaluation.to_dict() for evaluation in llm_repair_evaluations]

    repair_evaluations = [*repair_evaluations, *llm_repair_evaluations]
    repair_attempts_for_context = [*repair_attempts, *llm_repair_attempts]
    repair_evaluations_by_rule = group_by_rule_id(repair_evaluations)
    attempts_by_rule = group_attempts_by_rule_id(repair_attempts_for_context)

    if args.enable_repair_rerun:
        repair_rerun_report = run_repair_reruns(
            config=config,
            structured_rules=structured_rules,
            repair_evaluations=repair_evaluations,
            evidence_units=evidence_units,
        )
    else:
        repair_rerun_report = base_repair_rerun_report
    m8_5_decisions, structured_rules, guarded_repair_promotions = apply_guarded_repair_promotions(
        verification_decisions=m8_5_decisions,
        structured_rules=structured_rules,
        repair_rerun_report=repair_rerun_report,
        apply=bool(args.apply_guarded_repair_promotions),
    )
    verifier_rerun_requests = verifier_requests_from_report(repair_rerun_report)
    decisions_by_rule = {str(row.get("rule_id")): row for row in m8_5_decisions}
    review_packets = build_review_packets(
        structured_rules=structured_rules,
        decisions_by_rule=decisions_by_rule,
        dependencies_by_rule=dependencies_by_rule,
        attempts_by_rule=attempts_by_rule,
        repair_evaluations_by_rule=repair_evaluations_by_rule,
        enabled=args.enable_review_packets,
    )

    comparison = build_comparison(
        city=args.city,
        m8_comparison=m8_comparison,
        m8_summary=m8_summary,
        m8_5_decisions=m8_5_decisions,
        table_blocks=table_blocks,
        table_derived_rules=table_derived_rules,
        dependency_graph=dependency_graph,
        repair_evaluations=repair_evaluations,
        review_packets=review_packets,
        structured_rules=structured_rules,
    )
    add_repair_rerun_metrics(comparison, repair_rerun_report, guarded_repair_promotions)
    add_llm_repair_metrics(comparison, llm_repair_outputs, guarded_repair_promotions)
    summary = {
        "city": args.city,
        "m8_input_dir": str(m8_input_dir),
        "m7_input_dir": str(m7_input_dir),
        "output_dir": str(output_dir),
        "enabled": {
            "table_parsing": bool(args.enable_table_parsing),
            "dependency_graph": bool(args.enable_dependency_graph),
            "review_packets": bool(args.enable_review_packets),
            "repair_rerun": bool(args.enable_repair_rerun),
            "guarded_repair_promotions": bool(args.apply_guarded_repair_promotions),
            "llm_repair": bool(args.enable_llm_repair),
            "dry_run": bool(args.dry_run),
        },
        "m8_baseline": comparison["m8"],
        "m8_5_metrics": comparison["m8_5"],
        "safety": comparison["safety"],
        "artifacts": artifact_manifest(output_dir),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "table_blocks.json", [block.to_dict() for block in table_blocks])
    write_json(output_dir / "table_cell_lineage.json", [lineage.to_dict() for lineage in table_lineage])
    write_json(output_dir / "table_derived_rules.json", [rule.to_dict() for rule in table_derived_rules])
    write_json(output_dir / "dependency_graph.json", dependency_graph.to_dict())
    write_json(output_dir / "dependency_resolutions.json", [resolution.to_dict() for resolution in dependency_resolutions])
    write_json(output_dir / "repair_evaluations.json", [evaluation.to_dict() for evaluation in repair_evaluations])
    write_json(output_dir / "llm_repair_cases.json", llm_repair_outputs.get("cases", []))
    write_json(output_dir / "llm_repair_raw_outputs.json", llm_repair_outputs.get("raw_outputs", []))
    write_json(output_dir / "llm_repair_patches.json", llm_repair_outputs.get("patches", []))
    write_json(output_dir / "llm_repair_field_proofs.json", llm_repair_outputs.get("field_proofs", []))
    write_json(output_dir / "llm_repair_evaluations.json", llm_repair_outputs.get("evaluations", []))
    write_json(output_dir / "repair_rerun_report.json", repair_rerun_report)
    write_json(output_dir / "guarded_repair_promotions.json", guarded_repair_promotions)
    write_json(output_dir / "review_packets.json", [packet.to_dict() for packet in review_packets])
    write_json(output_dir / "verifier_rerun_requests.json", verifier_rerun_requests)
    write_json(output_dir / "m8_5_structured_rules.json", [*structured_rules, *[rule.to_verifier_candidate() for rule in table_derived_rules]])
    write_json(output_dir / "m8_5_verification_decisions.json", m8_5_decisions)
    write_json(output_dir / "m8_m8_5_comparison.json", comparison)
    write_json(output_dir / "m8_5_summary.json", summary)
    write_json(
        output_dir / "m8_5_chatbot_context.json",
        build_chatbot_context(
            summary,
            comparison,
            table_lineage=table_lineage,
            table_derived_rules=table_derived_rules,
            dependency_graph=dependency_graph,
            repair_evaluations=repair_evaluations,
            llm_repair_outputs=llm_repair_outputs,
            repair_rerun_report=repair_rerun_report,
            guarded_repair_promotions=guarded_repair_promotions,
            review_packets=review_packets,
        ),
    )
    (output_dir / "m8_5_summary.md").write_text(render_summary(summary), encoding="utf-8")
    (output_dir / "repair_rerun_report.md").write_text(
        repair_rerun_markdown(repair_rerun_report, guarded_repair_promotions),
        encoding="utf-8",
    )

    print("M8.5 pipeline complete")
    print(f"Output: {output_dir}")
    print(f"Table-derived rules: {comparison['m8_5']['table_derived_rules_count']}")
    print(f"Dependencies: {comparison['m8_5']['dependency_total_count']}")
    print(f"Review packets: {comparison['m8_5']['reviewer_packets_count']}")
    print(f"Repair rerun attempts: {comparison['m8_5']['repair_rerun_attempt_count']}")
    print(f"LLM repair cases: {comparison['m8_5']['llm_repair_case_count']}")
    print(f"LLM safe proof patches: {comparison['m8_5']['llm_repair_safe_patch_count']}")
    print(f"Guarded repair promotions: {comparison['m8_5']['guarded_repair_promotion_count']}")
    print(f"M7/M8 safety preserved: {comparison['safety']['m7_safety_preserved']}")
    return 0 if comparison["safety"]["m7_safety_preserved"] else 1


def llm_repair_client(args: argparse.Namespace) -> Any | None:
    if args.llm_repair_fixture:
        return FixtureRepairClient(read_json(Path(args.llm_repair_fixture), {}))
    if args.dry_run:
        return None
    return OpenRouterRepairClient(
        load_openrouter_api_key(ROOT / ".env"),
        model=str(args.repair_model),
        max_tokens=int(args.repair_llm_max_tokens),
    )


def build_table_blocks(source_spans: list[SourceSpan], *, city: str, zone: str, enabled: bool) -> list[TableBlock]:
    if not enabled:
        return []
    blocks: list[TableBlock] = []
    for span in source_spans:
        rows = rows_from_span(span)
        if len(rows) < 2 or len(rows[0]) < 2:
            continue
        table_id = str(span.metadata.get("table_id") or span.metadata.get("chunk_id") or span.span_id)
        try:
            blocks.append(
                parse_table_block(
                    city=city,
                    zone=zone,
                    document_id=span.document_id,
                    page=span.page,
                    section_id=span.section_id,
                    table_id=table_id,
                    rows=rows,
                    title=str(span.metadata.get("title") or ""),
                )
            )
        except ValueError:
            continue
    return blocks


def rows_from_span(span: SourceSpan) -> list[list[str]]:
    lines = [line.strip() for line in span.text.splitlines() if line.strip()]
    if not lines:
        return []
    if any("|" in line for line in lines):
        return [[" ".join(cell.split()) for cell in line.split("|")] for line in lines if "|" in line]
    return []


def build_cross_reference_index(source_spans: list[SourceSpan]) -> CrossReferenceIndex:
    index = CrossReferenceIndex()
    for span in source_spans:
        section = str(span.section_id or "").strip()
        evidence_id = str(span.metadata.get("evidence_id") or span.span_id)
        if section:
            index.add(f"Section {section}", evidence_id=evidence_id, text=span.text)
    return index


def rule_to_dependency_payload(rule: dict[str, Any]) -> dict[str, Any]:
    raw = rule.get("raw") or {}
    text_parts = [
        raw.get("rule_sentence"),
        raw.get("review_reason"),
        raw.get("condition"),
        raw.get("exception"),
        " ".join(str(item) for item in raw.get("support_gaps", []) or []),
        " ".join(str(item) for item in rule.get("conditions", []) or []),
        " ".join(str(item) for item in rule.get("exceptions", []) or []),
    ]
    return {
        "rule_id": rule.get("rule_id"),
        "rule_sentence": " ".join(str(item or "") for item in text_parts),
        "verification_decision": rule.get("status"),
        "support_gaps": raw.get("support_gaps", []),
    }


def evidence_index(source_spans: list[SourceSpan], repair_attempts: list[dict[str, Any]]) -> dict[str, SourceSpan]:
    index: dict[str, SourceSpan] = {}
    for span in source_spans:
        evidence_id = str(span.metadata.get("evidence_id") or span.span_id)
        index[evidence_id] = span
    for attempt in repair_attempts:
        patch = attempt.get("patch") or {}
        for pointer in patch.get("evidence_pointers") or []:
            evidence_id = str(pointer.get("evidence_id") or "")
            span_data = pointer.get("source_span")
            if evidence_id and isinstance(span_data, dict):
                try:
                    index[evidence_id] = SourceSpan.from_dict(span_data)
                except ValueError:
                    continue
    return index


def evidence_unit_index(evidence_units: list[dict[str, Any]], *, config: dict[str, Any]) -> dict[str, SourceSpan]:
    index: dict[str, SourceSpan] = {}
    for unit in evidence_units:
        evidence_id = str(unit.get("evidence_id") or "")
        if not evidence_id:
            continue
        text = str(unit.get("evidence_text") or "")
        context = str(unit.get("source_context") or "")
        combined = text if not context or context == text else f"{text}\n{context}"
        if not combined.strip():
            continue
        index[evidence_id] = SourceSpan(
            city=str(config.get("city") or ""),
            document_id=str(config.get("source_document") or "source.pdf"),
            page=unit.get("page"),
            section_id=str(unit.get("section") or ""),
            block_type=str(unit.get("evidence_type") or "evidence"),
            char_start=0,
            char_end=len(combined),
            text=combined,
            source_url=str(config.get("source_url") or ""),
            metadata={
                "evidence_id": evidence_id,
                "zone": str(config.get("zone") or ""),
                "table_title": unit.get("table_title"),
                "row_header": unit.get("row_header"),
                "column_header": unit.get("column_header"),
                "cell_value": unit.get("cell_value"),
            },
        )
    return index


def evaluate_repair_attempts(
    repair_attempts: list[dict[str, Any]],
    rules_by_id: dict[str, dict[str, Any]],
    evidence_by_id: dict[str, SourceSpan],
) -> list[RepairEvaluation]:
    evaluations: list[RepairEvaluation] = []
    for attempt in repair_attempts:
        critique = attempt.get("critique") or {}
        patch = attempt.get("patch") or {}
        rule_id = str(critique.get("rule_id") or patch.get("rule_id") or "")
        original = rules_by_id.get(rule_id, {})
        raw = original.get("raw") if isinstance(original.get("raw"), dict) else {}
        original_rule = {**original, **raw, "rule_id": rule_id}
        changes = dict(patch.get("changes") or {})
        patched_rule = {**original_rule, **changes, "rule_id": rule_id}
        if "evidence_id" not in patched_rule and changes.get("evidence_id"):
            patched_rule["evidence_id"] = changes["evidence_id"]
        evaluation = evaluate_repair(
            original_rule=original_rule,
            patched_rule=patched_rule,
            evidence_by_id=evidence_by_id,
            repair_history=(attempt,),
            verifier_result={"decision_status": attempt.get("decision_status"), "reason": attempt.get("reason")},
        )
        attempt_metadata = dict(attempt.get("metadata") or {})
        if attempt_metadata:
            metadata = dict(evaluation.metadata or {})
            metadata.update(attempt_metadata)
            evaluation = replace(evaluation, metadata=metadata)
        evaluations.append(evaluation)
    return evaluations


def group_by_rule_id(evaluations: list[RepairEvaluation]) -> dict[str, tuple[RepairEvaluation, ...]]:
    grouped: dict[str, list[RepairEvaluation]] = defaultdict(list)
    for evaluation in evaluations:
        grouped[evaluation.rule_id].append(evaluation)
    return {key: tuple(value) for key, value in grouped.items()}


def group_attempts_by_rule_id(attempts: list[dict[str, Any]]) -> dict[str, tuple[dict[str, Any], ...]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        critique = attempt.get("critique") or {}
        rule_id = str(critique.get("rule_id") or (attempt.get("patch") or {}).get("rule_id") or "")
        grouped[rule_id].append(attempt)
    return {key: tuple(value) for key, value in grouped.items()}


def build_review_packets(
    *,
    structured_rules: list[dict[str, Any]],
    decisions_by_rule: dict[str, dict[str, Any]],
    dependencies_by_rule: dict[str, tuple[Any, ...]],
    attempts_by_rule: dict[str, tuple[dict[str, Any], ...]],
    repair_evaluations_by_rule: dict[str, tuple[RepairEvaluation, ...]],
    enabled: bool,
) -> list[ReviewPacket]:
    if not enabled:
        return []
    packets: list[ReviewPacket] = []
    for rule in structured_rules:
        status = str(rule.get("status") or "")
        if status not in {"review_needed", "context_required"}:
            continue
        rule_id = str(rule.get("rule_id") or "")
        decision = decisions_by_rule.get(rule_id, {})
        evidence_spans = evidence_spans_for_rule(rule)
        repair_evaluations = repair_evaluations_by_rule.get(rule_id, ())
        packets.append(
            ReviewPacket(
                rule_id=rule_id,
                current_status=status,
                failure_reason=str(decision.get("reason") or (rule.get("raw") or {}).get("review_reason") or "requires review"),
                candidate_rule_fields={
                    "rule_object": rule.get("rule_type"),
                    "subject": rule.get("subject"),
                    "operator": rule.get("comparator"),
                    "value": rule.get("value"),
                    "unit": rule.get("unit"),
                    "conditions": rule.get("conditions") or [],
                    "exceptions": rule.get("exceptions") or [],
                },
                evidence_spans=tuple(evidence_spans),
                table_lineage=None,
                dependency_graph_slice=dependencies_by_rule.get(rule_id, ()),
                repair_attempts=attempts_by_rule.get(rule_id, ()),
                repair_evaluations=repair_evaluations,
                recommended_reviewer_action=recommended_action(status, repair_evaluations, dependencies_by_rule.get(rule_id, ())),
                reviewer_notes=(),
            )
        )
    return packets


def evidence_spans_for_rule(rule: dict[str, Any]) -> list[SourceSpan]:
    spans = []
    for pointer in rule.get("evidence_pointers") or []:
        span_data = pointer.get("source_span")
        if isinstance(span_data, dict):
            try:
                spans.append(SourceSpan.from_dict(span_data))
            except ValueError:
                continue
    return spans


def recommended_action(status: str, repair_evaluations: tuple[RepairEvaluation, ...], dependencies: tuple[Any, ...]) -> str:
    if any(evaluation.verifier_ready for evaluation in repair_evaluations):
        return "send_to_verifier"
    if dependencies:
        return "mark_dependency_resolved" if status == "context_required" else "mark_needs_legal_review"
    return "request_more_retrieval"


def build_m8_5_decisions(verification_decisions: list[dict[str, Any]], dependency_resolutions: list[Any]) -> list[dict[str, Any]]:
    resolutions_by_rule = {resolution.rule_id: resolution for resolution in dependency_resolutions}
    rows = []
    for decision in verification_decisions:
        rule_id = str(decision.get("rule_id") or "")
        resolution = resolutions_by_rule.get(rule_id)
        row = dict(decision)
        if resolution is not None:
            row["m8_5_recommended_status"] = resolution.recommended_status
            row["m8_5_dependency_ids"] = [dependency.dependency_id for dependency in resolution.dependencies]
        else:
            row["m8_5_recommended_status"] = decision.get("status")
            row["m8_5_dependency_ids"] = []
        rows.append(row)
    return rows


def build_comparison(
    *,
    city: str,
    m8_comparison: dict[str, Any],
    m8_summary: dict[str, Any],
    m8_5_decisions: list[dict[str, Any]],
    table_blocks: list[TableBlock],
    table_derived_rules: list[TableDerivedRule],
    dependency_graph: DependencyGraph,
    repair_evaluations: list[RepairEvaluation],
    review_packets: list[ReviewPacket],
    structured_rules: list[dict[str, Any]],
) -> dict[str, Any]:
    return compare_m8_to_m8_5(
        city=city,
        m8_comparison=m8_comparison,
        m8_summary=m8_summary,
        m8_5_decisions=m8_5_decisions,
        table_blocks=table_blocks,
        table_derived_rules=table_derived_rules,
        dependency_graph=dependency_graph,
        repair_evaluations=repair_evaluations,
        review_packets=review_packets,
        structured_rules=structured_rules,
    )


def verifier_requests_from_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for attempt in report.get("attempts", []):
        patched_candidate = dict(attempt.get("patched_candidate") or {})
        requests.append(
            VerifierRerunRequest(
                rule_id=str(attempt.get("rule_id") or ""),
                source_action_id=f"m8_5_repair_rerun:{attempt.get('rule_id')}:{','.join(attempt.get('retry_evidence_ids') or [])}",
                candidate_rule_fields={
                    "rule_object": patched_candidate.get("rule_object"),
                    "subject": patched_candidate.get("applies_to") or patched_candidate.get("constraint_scope"),
                    "operator": patched_candidate.get("operator"),
                    "value": patched_candidate.get("value"),
                    "unit": patched_candidate.get("unit"),
                    "condition": patched_candidate.get("condition"),
                    "exception": patched_candidate.get("exception"),
                    "evidence_id": patched_candidate.get("evidence_id"),
                },
                reason="m8_5_repair_rerun",
                approved_evidence_ids=tuple(str(item) for item in attempt.get("retry_evidence_ids") or []),
                reviewer_note=str(attempt.get("retry_reason") or ""),
                status="complete" if attempt.get("promotion_ready") else "failed",
                metadata={
                    "retry_decision": attempt.get("retry_decision"),
                    "promotion_ready": bool(attempt.get("promotion_ready")),
                    "promotion_risk_flags": list(attempt.get("promotion_risk_flags") or []),
                    "retry_support_gaps": list(attempt.get("retry_support_gaps") or []),
                },
            ).to_dict()
        )
    return requests


def add_repair_rerun_metrics(
    comparison: dict[str, Any],
    repair_rerun_report: dict[str, Any],
    guarded_repair_promotions: dict[str, Any],
) -> None:
    metrics = repair_rerun_metrics(repair_rerun_report, guarded_repair_promotions)
    m8_5 = comparison.setdefault("m8_5", {})
    m8_5.update(metrics)
    states = m8_5.setdefault("metric_states", {})
    states.update(
        {
            "repair_rerun_eligible_rule_count": {
                "state": "measured",
                "value": metrics["repair_rerun_eligible_rule_count"],
                "source": "repair_rerun_report.json",
                "note": "",
            },
            "repair_rerun_attempt_count": {
                "state": "measured",
                "value": metrics["repair_rerun_attempt_count"],
                "source": "repair_rerun_report.json",
                "note": "",
            },
            "repair_rerun_promotion_ready_count": {
                "state": "measured",
                "value": metrics["repair_rerun_promotion_ready_count"],
                "source": "repair_rerun_report.json",
                "note": "",
            },
            "guarded_repair_promotion_count": {
                "state": "measured",
                "value": metrics["guarded_repair_promotion_count"],
                "source": "guarded_repair_promotions.json",
                "note": "",
            },
            "review_needed_reduction_from_repair_rerun": {
                "state": "measured",
                "value": metrics["review_needed_reduction_from_repair_rerun"],
                "source": "guarded_repair_promotions.json",
                "note": "",
            },
        }
    )
    if metrics["repair_rerun_attempt_count"]:
        m8_5["measured_scope"] = "m8_5_pipeline_artifacts_plus_guarded_repair_rerun"


def add_llm_repair_metrics(
    comparison: dict[str, Any],
    llm_repair_outputs: dict[str, Any],
    guarded_repair_promotions: dict[str, Any],
) -> None:
    llm_rule_ids = {
        str(attempt.get("rule_id") or (attempt.get("critique") or {}).get("rule_id") or "")
        for attempt in llm_repair_outputs.get("attempts", [])
    }
    llm_promoted = [
        rule_id
        for rule_id in guarded_repair_promotions.get("promoted_rule_ids", [])
        if str(rule_id) in llm_rule_ids
    ]
    adjusted_promotions = dict(guarded_repair_promotions)
    adjusted_promotions["review_removed_count"] = len(llm_promoted)
    metrics = llm_repair_metrics(llm_repair_outputs, guarded_repair_promotions=adjusted_promotions)
    m8_5 = comparison.setdefault("m8_5", {})
    m8_5.update(metrics)
    states = m8_5.setdefault("metric_states", {})
    for key, source in {
        "llm_repair_case_count": "llm_repair_cases.json",
        "llm_repair_patch_count": "llm_repair_patches.json",
        "llm_repair_no_patch_count": "llm_repair_raw_outputs.json",
        "llm_repair_safe_patch_count": "llm_repair_evaluations.json",
        "llm_repair_rejected_patch_count": "llm_repair_patches.json",
        "field_proof_completion_rate": "llm_repair_field_proofs.json",
        "llm_repair_latency_ms": "llm_repair_raw_outputs.json",
        "llm_repair_estimated_cost_usd": "llm_repair_raw_outputs.json",
        "review_needed_reduction_from_llm_repair": "guarded_repair_promotions.json",
    }.items():
        states[key] = {
            "state": "measured",
            "value": metrics.get(key),
            "source": source,
            "note": "",
        }
    if metrics["llm_repair_case_count"]:
        m8_5["measured_scope"] = "m8_5_pipeline_artifacts_plus_llm_repair"


def artifact_manifest(output_dir: Path) -> dict[str, str]:
    names = [
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
        "guarded_repair_promotions.json",
        "review_packets.json",
        "verifier_rerun_requests.json",
        "m8_5_structured_rules.json",
        "m8_5_verification_decisions.json",
        "m8_m8_5_comparison.json",
        "m8_5_summary.json",
        "m8_5_chatbot_context.json",
    ]
    manifest = {name.removesuffix(".json"): str(output_dir / name) for name in names}
    manifest["repair_rerun_report_markdown"] = str(output_dir / "repair_rerun_report.md")
    return manifest


def build_chatbot_context(
    summary: dict[str, Any],
    comparison: dict[str, Any],
    *,
    table_lineage: list[Any],
    table_derived_rules: list[TableDerivedRule],
    dependency_graph: DependencyGraph,
    repair_evaluations: list[RepairEvaluation],
    llm_repair_outputs: dict[str, Any],
    repair_rerun_report: dict[str, Any],
    guarded_repair_promotions: dict[str, Any],
    review_packets: list[ReviewPacket],
) -> dict[str, Any]:
    return {
        "summary": summary,
        "comparison": comparison,
        "table_cell_lineage": [lineage.to_dict() for lineage in table_lineage],
        "table_derived_rules": [rule.to_dict() for rule in table_derived_rules],
        "dependency_graph": dependency_graph.to_dict(),
        "repair_evaluations": [evaluation.to_dict() for evaluation in repair_evaluations],
        "llm_repair": {
            "metrics": llm_repair_outputs.get("metrics", {}),
            "cases": llm_repair_outputs.get("cases", []),
            "patches": llm_repair_outputs.get("patches", []),
            "field_proofs": llm_repair_outputs.get("field_proofs", []),
        },
        "repair_rerun_report": repair_rerun_report,
        "guarded_repair_promotions": guarded_repair_promotions,
        "review_packets": [packet.to_dict() for packet in review_packets],
    }


def render_summary(summary: dict[str, Any]) -> str:
    metrics = summary["m8_5_metrics"]
    lines = [
        "# M8.5 Summary",
        "",
        f"City: `{summary['city']}`",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Table-derived rules | {metrics['table_derived_rules_count']} |",
        f"| Dependencies | {metrics['dependency_total_count']} |",
        f"| Repair evaluations | {metrics['repair_evaluations_count']} |",
        f"| Verifier-ready patches | {metrics['verifier_ready_patches_count']} |",
        f"| LLM repair cases | {metrics['llm_repair_case_count']} |",
        f"| LLM repair patches | {metrics['llm_repair_patch_count']} |",
        f"| LLM safe proof patches | {metrics['llm_repair_safe_patch_count']} |",
        f"| Field proof completion rate | {metrics['field_proof_completion_rate']} |",
        f"| LLM repair latency ms | {metrics['llm_repair_latency_ms']} |",
        f"| LLM repair estimated cost USD | {metrics['llm_repair_estimated_cost_usd']} |",
        f"| Repair rerun eligible rules | {metrics['repair_rerun_eligible_rule_count']} |",
        f"| Repair rerun attempts | {metrics['repair_rerun_attempt_count']} |",
        f"| Promotion-ready repairs | {metrics['repair_rerun_promotion_ready_count']} |",
        f"| Guarded repair promotions | {metrics['guarded_repair_promotion_count']} |",
        f"| Review reduction from LLM repair | {metrics['review_needed_reduction_from_llm_repair']} |",
        f"| Review reduction from repair rerun | {metrics['review_needed_reduction_from_repair_rerun']} |",
        f"| Review packets | {metrics['reviewer_packets_count']} |",
        f"| False verified | {metrics['false_verified_count']} |",
        f"| False approvals | {metrics['false_approval_count']} |",
        "",
        f"M7/M8 safety preserved: `{summary['safety']['m7_safety_preserved']}`",
        "Repair can promote directly: `False`",
        "Reviewer can promote directly: `False`",
        "",
    ]
    return "\n".join(lines)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
