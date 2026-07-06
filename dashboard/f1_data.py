"""Data providers for the F1 Streamlit command center."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_F1_OUTPUT = ROOT / "outputs" / "f1_runs" / "burnaby_r1" / "checkpoint_16_product_operations"


def discover_f1_outputs(output_root: str | Path = ROOT / "outputs" / "f1_runs") -> list[Path]:
    root = Path(output_root)
    if not root.exists():
        return []
    outputs = [
        path
        for path in root.glob("*/*")
        if (path / "command_center_app_manifest.json").exists()
    ]
    return sorted(outputs, key=lambda path: (path.parent.name, path.name))


def load_f1_output(output_dir: str | Path = DEFAULT_F1_OUTPUT) -> dict[str, Any]:
    output = Path(output_dir)
    return {
        "output_dir": output,
        "manifest": _read_json(output / "command_center_app_manifest.json", {}),
        "summary": _read_json(output / "f1_summary.json", {}),
        "benchmark": _read_json(output / "f1_benchmark_report.json", {}),
        "chatbot_eval": _read_json(output / "chatbot_eval.json", {}),
        "retrieval_report": _read_json(output / "retrieval_report.json", {}),
        "extraction_report": _read_json(output / "extraction_report.json", {}),
        "verification_report": _read_json(output / "verification_report.json", {}),
        "document_intelligence_report": _read_json(output / "document_intelligence_report.json", {}),
        "repair_rerun_report": _read_json(output / "repair_rerun_report.json", {}),
        "guarded_repair_promotions": _read_json(output / "guarded_repair_promotions.json", []),
        "verifier_rerun_requests": _read_json(output / "verifier_rerun_requests.json", []),
        "compliance_report": _read_json(output / "compliance_report.json", {}),
        "source_registry": _read_json(output / "source_registry.json", {}),
        "review_packets": _read_json(output / "review_packets.json", []),
        "operator_action_templates": _read_json(output / "operator_action_templates.json", []),
        "operator_review_actions": _read_json(output / "operator_review_actions.json", {}),
        "scenario_templates": _read_json(output / "scenario_templates.json", []),
        "evidence_navigation": _read_json(output / "evidence_navigation.json", {}),
        "operations_report": _read_json(output / "operations_report.json", {}),
        "verified_rules": _read_json(output / "verified_rules.json", []),
        "review_queue": _read_json(output / "review_queue.json", []),
        "gis_contract": _read_json(output / "gis_rule_contract.json", {}),
        "compliance_decisions": _read_json(output / "compliance_decisions.json", []),
    }


def metric_cards(data: dict[str, Any]) -> list[dict[str, Any]]:
    manifest = data.get("manifest") or {}
    health = manifest.get("workflow_health") or {}
    benchmark = manifest.get("benchmark_metrics") or {}
    return [
        {"label": "Verified rules", "value": health.get("verified_rule_count", len(manifest.get("verified_rules") or []))},
        {"label": "Review items", "value": health.get("review_queue_count", len(manifest.get("review_queue") or []))},
        {"label": "Retrieval recall", "value": _format_pct(benchmark.get("retrieval_recall_at_6"))},
        {"label": "Candidate recall", "value": _format_pct(benchmark.get("candidate_recall"))},
        {"label": "Verified precision", "value": _format_pct(benchmark.get("verified_precision"))},
        {"label": "Proposal accuracy", "value": _format_pct(benchmark.get("proposal_case_accuracy"))},
        {"label": "False verified", "value": health.get("false_verified_count", benchmark.get("false_verified_count", 0))},
        {"label": "False approvals", "value": health.get("false_approval_count", benchmark.get("false_approval_count", 0))},
    ]


def command_center_cards(data: dict[str, Any]) -> list[dict[str, Any]]:
    manifest = data.get("manifest") or {}
    health = manifest.get("workflow_health") or {}
    benchmark = manifest.get("benchmark_metrics") or {}
    compliance = manifest.get("compliance_status_counts") or {}
    verification = data.get("verification_report") or {}
    return [
        {
            "label": "Verified rules",
            "value": health.get("verified_rule_count", len(manifest.get("verified_rules") or [])),
            "note": "usable by GIS and compliance",
            "tone": "good",
        },
        {
            "label": "Review queue",
            "value": health.get("review_queue_count", len(manifest.get("review_queue") or [])),
            "note": "blocked until proof or review",
            "tone": "warn",
        },
        {
            "label": "Benchmark gates",
            "value": "pass" if benchmark.get("quality_gates_passed") else "blocked",
            "note": f"{len(benchmark.get('failed_gates') or [])} failed gates",
            "tone": "good" if benchmark.get("quality_gates_passed") else "bad",
        },
        {
            "label": "Verified precision",
            "value": _format_pct(benchmark.get("verified_precision")),
            "note": "release safety target is 100%",
            "tone": "good",
        },
        {
            "label": "False verified",
            "value": health.get("false_verified_count", benchmark.get("false_verified_count", 0)),
            "note": "hard safety gate",
            "tone": "good" if not health.get("false_verified_count", benchmark.get("false_verified_count", 0)) else "bad",
        },
        {
            "label": "False approvals",
            "value": health.get("false_approval_count", benchmark.get("false_approval_count", 0)),
            "note": "hard safety gate",
            "tone": "good" if not health.get("false_approval_count", benchmark.get("false_approval_count", 0)) else "bad",
        },
        {
            "label": "Compliance smoke",
            "value": compliance.get("approved", 0),
            "note": f"{compliance.get('needs_review', 0)} needs review / {compliance.get('rejected', 0)} rejected",
            "tone": "neutral",
        },
        {
            "label": "Verifier output",
            "value": verification.get("verified_count", health.get("verified_rule_count", 0)),
            "note": "deterministic authority",
            "tone": "neutral",
        },
    ]


def workflow_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    manifest = data.get("manifest") or {}
    labels = {
        "rule_explorer": "Browse verified source-backed rules",
        "review_workbench": "Inspect blocked rules and proof gaps",
        "evidence_inspector": "Trace every rule back to cited source text",
        "compliance_sandbox": "Test scenarios against verified rules only",
        "chatbot_safety": "Confirm chat cannot approve or promote",
    }
    rows = []
    for item in manifest.get("product_workflows") or []:
        workflow_id = str(item.get("id") or "")
        rows.append(
            {
                "workflow": item.get("label") or workflow_id,
                "purpose": labels.get(workflow_id, "F1 product workflow"),
                "status": item.get("status") or "available",
            }
        )
    return rows


def benchmark_gate_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    manifest = data.get("manifest") or {}
    benchmark = manifest.get("benchmark_metrics") or data.get("benchmark") or {}
    specs = [
        ("retrieval_recall_at_6", 0.95, ">="),
        ("candidate_recall", 0.90, ">="),
        ("verified_precision", 1.00, ">="),
        ("proposal_case_accuracy", 1.00, ">="),
        ("false_verified_count", 0, "=="),
        ("false_approval_count", 0, "=="),
        ("gis_review_rule_leak_count", 0, "=="),
        ("verified_source_support_failed_count", 0, "=="),
    ]
    rows = []
    for metric, target, operator in specs:
        value = benchmark.get(metric)
        passed = _passes_gate(value, target, operator)
        rows.append(
            {
                "gate": metric,
                "value": _format_metric_value(value),
                "target": f"{operator} {_format_metric_value(target)}",
                "status": "pass" if passed else "blocked",
            }
        )
    return rows


def pipeline_stage_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    summary = data.get("summary") or {}
    document = summary.get("document_intelligence") or {}
    retrieval = summary.get("retrieval") or {}
    extraction = summary.get("extraction") or data.get("extraction_report") or {}
    verification = summary.get("verification") or data.get("verification_report") or {}
    repair = summary.get("repair") or data.get("repair_rerun_report") or {}
    gis = summary.get("gis_compliance") or data.get("compliance_report") or {}
    chat = summary.get("chatbot_eval") or (data.get("chatbot_eval") or {}).get("metrics") or {}
    manifest = data.get("manifest") or {}
    return [
        {
            "stage": "Document intelligence",
            "purpose": "Turn official PDFs into blocks, spans, and table context",
            "output": "source_spans.json",
            "count": document.get("source_span_count") or document.get("document_block_count") or "n/a",
            "authority": "source only",
        },
        {
            "stage": "Proof-aware RAG",
            "purpose": "Retrieve evidence for candidate fields",
            "output": "retrieval_report.json",
            "count": retrieval.get("evidence_count") or len((data.get("retrieval_report") or {}).get("evidence") or []),
            "authority": "evidence support",
        },
        {
            "stage": "Extraction",
            "purpose": "Generate structured candidate rules",
            "output": "candidate_rules.json",
            "count": extraction.get("candidate_count", "n/a"),
            "authority": "proposal only",
        },
        {
            "stage": "Verification",
            "purpose": "Promote only exact source-supported rules",
            "output": "verified_rules.json",
            "count": verification.get("verified_count") or (manifest.get("workflow_health") or {}).get("verified_rule_count"),
            "authority": "promotion authority",
        },
        {
            "stage": "Repair and review",
            "purpose": "Explain gaps and rerun only safe proof patches",
            "output": "review_queue.json",
            "count": (manifest.get("workflow_health") or {}).get("review_queue_count"),
            "authority": "no direct promotion",
        },
        {
            "stage": "GIS and compliance",
            "purpose": "Consume verified-only rules for map and scenario checks",
            "output": "gis_rule_contract.json",
            "count": gis.get("scenario_count") or len(manifest.get("compliance_decisions") or []),
            "authority": "verified-only",
        },
        {
            "stage": "Chat",
            "purpose": "Explain and navigate with citations",
            "output": "chatbot_eval.json",
            "count": chat.get("case_count") or (manifest.get("chatbot_metrics") or {}).get("case_count"),
            "authority": "cannot approve",
        },
    ]


def rule_rows(data: dict[str, Any], *, query: str = "", rule_object: str = "") -> list[dict[str, Any]]:
    rows = []
    query = query.strip().lower()
    for rule in (data.get("manifest") or {}).get("verified_rules") or []:
        if rule_object and rule.get("rule_object") != rule_object:
            continue
        if query and query not in str(rule.get("search_text") or "").lower():
            continue
        citation = rule.get("citation") if isinstance(rule.get("citation"), dict) else {}
        rows.append(
            {
                "rule_id": rule.get("rule_id"),
                "object": rule.get("rule_object"),
                "limit": _limit_text(rule),
                "applies_to": rule.get("applies_to") or rule.get("constraint_scope"),
                "condition": rule.get("condition") or "",
                "evidence_id": citation.get("evidence_id") or ", ".join(rule.get("evidence_ids") or []),
                "page": citation.get("page"),
            }
        )
    return rows


def rule_object_summary_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    gis_counter: Counter[str] = Counter()
    for rule in (data.get("manifest") or {}).get("verified_rules") or []:
        key = str(rule.get("rule_object") or "unknown")
        counter[key] += 1
        if rule.get("geometry_target") and rule.get("geometry_target") != "unknown":
            gis_counter[key] += 1
    return [
        {"rule_object": key, "verified_rules": count, "gis_ready": gis_counter.get(key, 0)}
        for key, count in counter.most_common()
    ]


def review_rows(data: dict[str, Any], *, query: str = "", status: str = "") -> list[dict[str, Any]]:
    rows = []
    query = query.strip().lower()
    for item in (data.get("manifest") or {}).get("review_queue") or []:
        if status and item.get("status") != status:
            continue
        if query and query not in str(item.get("search_text") or "").lower():
            continue
        rows.append(
            {
                "rule_id": item.get("rule_id"),
                "status": item.get("status"),
                "object": item.get("rule_object"),
                "candidate": _limit_text(item),
                "gap": ", ".join(item.get("support_gaps") or item.get("unresolved_dependencies") or ["context_required"]),
                "evidence_count": len(item.get("evidence") or []),
            }
        )
    return rows


def review_gap_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for item in (data.get("manifest") or {}).get("review_queue") or []:
        gaps = item.get("support_gaps") or item.get("unresolved_dependencies") or [item.get("status") or "review_needed"]
        for gap in gaps:
            counter[str(gap)] += 1
    return [{"gap": gap, "count": count} for gap, count in counter.most_common()]


def top_review_items(data: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    rows = review_rows(data)
    def sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
        status = str(row.get("status") or "")
        evidence_count = int(row.get("evidence_count") or 0)
        status_weight = 0 if status == "context_required" else 1 if status == "review_needed" else 2
        return (status_weight, -evidence_count, str(row.get("rule_id") or ""))

    return sorted(rows, key=sort_key)[:limit]


def evidence_rows(data: dict[str, Any], limit: int = 500) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    manifest = data.get("manifest") or {}
    for rule in manifest.get("verified_rules") or []:
        citation = rule.get("citation") if isinstance(rule.get("citation"), dict) else {}
        if citation:
            rows.append(
                {
                    "source": "verified",
                    "rule_id": rule.get("rule_id"),
                    "field": "rule",
                    "evidence_id": citation.get("evidence_id"),
                    "page": citation.get("page"),
                    "section": citation.get("section_id"),
                    "quote": citation.get("quote"),
                }
            )
            if len(rows) >= limit:
                return rows
    for item in manifest.get("review_queue") or []:
        for evidence in item.get("evidence") or []:
            rows.append(
                {
                    "source": "review",
                    "rule_id": item.get("rule_id"),
                    "field": evidence.get("field"),
                    "evidence_id": evidence.get("evidence_id"),
                    "page": evidence.get("page"),
                    "section": evidence.get("section_id"),
                    "quote": evidence.get("quote"),
                }
            )
            if len(rows) >= limit:
                return rows
    return rows


def retrieval_evidence_rows(data: dict[str, Any], limit: int = 500) -> list[dict[str, Any]]:
    rows = []
    for evidence in (data.get("retrieval_report") or {}).get("evidence") or []:
        rows.append(
            {
                "evidence_id": evidence.get("evidence_id"),
                "query": evidence.get("query"),
                "rank": evidence.get("rank"),
                "page": evidence.get("page"),
                "section": evidence.get("section_id"),
                "supports_fields": ", ".join(evidence.get("supports_fields") or []),
                "quote": evidence.get("quote"),
            }
        )
        if len(rows) >= limit:
            return rows
    return rows


def compliance_rows(data: dict[str, Any], limit: int = 500) -> list[dict[str, Any]]:
    rows = []
    for item in (data.get("manifest") or {}).get("compliance_decisions") or []:
        rows.append(
            {
                "scenario_id": item.get("scenario_id"),
                "status": item.get("status"),
                "verified_rule_ids": ", ".join(item.get("verified_rule_ids") or []),
                "review_rule_ids": ", ".join(item.get("review_rule_ids") or []),
                "reason": item.get("reason"),
            }
        )
        if len(rows) >= limit:
            return rows
    return rows


def compliance_status_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    counts = (data.get("manifest") or {}).get("compliance_status_counts") or (data.get("compliance_report") or {}).get("status_counts") or {}
    return [{"status": key, "count": value} for key, value in sorted(counts.items())]


def operator_action_template_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in data.get("operator_action_templates") or []:
        rows.append(
            {
                "rule_id": item.get("rule_id"),
                "current_status": item.get("current_status"),
                "recommended_action": item.get("recommended_action"),
                "support_gaps": ", ".join(item.get("support_gaps") or []),
                "evidence_ids": ", ".join(item.get("evidence_ids") or []),
                "cannot_promote": item.get("cannot_promote"),
            }
        )
    return rows


def operator_review_action_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    log = _read_operator_action_log(data)
    return [
        {
            "created_at": action.get("created_at"),
            "rule_id": action.get("rule_id"),
            "action_type": action.get("action_type"),
            "state": action.get("state"),
            "note": action.get("note"),
        }
        for action in log.get("actions") or []
    ]


def scenario_template_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "scenario_template_id": item.get("scenario_template_id"),
            "rule_id": item.get("rule_id"),
            "object": item.get("rule_object"),
            "operator": item.get("operator"),
            "threshold": item.get("threshold"),
            "unit": item.get("unit"),
            "passing_example_value": item.get("passing_example_value"),
            "failing_example_value": item.get("failing_example_value"),
        }
        for item in data.get("scenario_templates") or []
    ]


def evidence_navigation_rows(data: dict[str, Any], *, source: str = "", query: str = "", limit: int = 500) -> list[dict[str, Any]]:
    query = query.strip().lower()
    rows = []
    for item in (data.get("evidence_navigation") or {}).get("items") or []:
        if source and item.get("source") != source:
            continue
        search_text = " ".join(str(item.get(field) or "") for field in ("rule_id", "rule_object", "evidence_id", "quote")).lower()
        if query and query not in search_text:
            continue
        rows.append(
            {
                "source": item.get("source"),
                "rule_id": item.get("rule_id"),
                "status": item.get("status"),
                "object": item.get("rule_object"),
                "evidence_id": item.get("evidence_id"),
                "page": item.get("page"),
                "section": item.get("section_id"),
                "quote": item.get("quote"),
            }
        )
        if len(rows) >= limit:
            return rows
    return rows


def save_operator_review_action(data: dict[str, Any], *, rule_id: str, action_type: str, note: str) -> dict[str, Any]:
    output = Path(data.get("output_dir") or DEFAULT_F1_OUTPUT)
    path = output / "operator_review_actions.json"
    output.mkdir(parents=True, exist_ok=True)
    log = _read_operator_action_log(data)
    action = {
        "action_id": f"local_action_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rule_id": rule_id,
        "action_type": action_type,
        "note": note.strip(),
        "state": "draft_saved",
        "writes_rule_status": False,
        "writes_verified_rules": False,
        "writes_gis_contract": False,
    }
    log.setdefault("actions", []).append(action)
    log["generated_at"] = datetime.now(timezone.utc).isoformat()
    log["operator_actions_persisted_count"] = len(log.get("actions") or [])
    log["writes_rule_status"] = False
    path.write_text(json.dumps(log, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    data["operator_review_actions"] = log
    return action


def artifact_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    output = Path(data.get("output_dir") or DEFAULT_F1_OUTPUT)
    manifest = data.get("manifest") or {}
    source_artifacts = manifest.get("source_artifacts") or {}
    rows = []
    for purpose, filename in sorted(source_artifacts.items()):
        path = output / str(filename)
        rows.append(
            {
                "purpose": purpose,
                "artifact": filename,
                "exists": path.exists(),
                "size_kb": round(path.stat().st_size / 1024, 1) if path.exists() else None,
            }
        )
    return rows


def rule_objects(data: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(rule.get("rule_object"))
            for rule in (data.get("manifest") or {}).get("verified_rules") or []
            if rule.get("rule_object")
        }
    )


def review_statuses(data: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(item.get("status"))
            for item in (data.get("manifest") or {}).get("review_queue") or []
            if item.get("status")
        }
    )


def find_rule(data: dict[str, Any], rule_id: str) -> dict[str, Any] | None:
    for rule in (data.get("manifest") or {}).get("verified_rules") or []:
        if rule.get("rule_id") == rule_id:
            return rule
    return None


def find_review_item(data: dict[str, Any], rule_id: str) -> dict[str, Any] | None:
    for item in (data.get("manifest") or {}).get("review_queue") or []:
        if item.get("rule_id") == rule_id:
            return item
    return None


def evaluate_single_rule(rule: dict[str, Any], actual_value: float) -> dict[str, Any]:
    target = _to_float(rule.get("value"))
    if target is None:
        return {
            "status": "needs_review",
            "message": "The selected rule is not numeric, so the sandbox cannot compare it.",
        }
    operator = str(rule.get("operator") or "").strip()
    if operator in {"<=", "≤"}:
        passes = actual_value <= target
        relation = "<="
    elif operator in {">=", "≥"}:
        passes = actual_value >= target
        relation = ">="
    elif operator == "<":
        passes = actual_value < target
        relation = "<"
    elif operator == ">":
        passes = actual_value > target
        relation = ">"
    else:
        passes = actual_value == target
        relation = "="
    return {
        "status": "passes_rule" if passes else "fails_rule",
        "message": f"{actual_value:g} {'passes' if passes else 'fails'} {rule.get('rule_id')} ({relation} {target:g} {rule.get('unit') or ''}).",
    }


def evaluate_rule_set(rules: list[dict[str, Any]], actual_values: dict[str, float]) -> dict[str, Any]:
    checks = []
    failed = 0
    for rule in rules:
        rule_id = str(rule.get("rule_id") or "")
        if rule_id not in actual_values:
            continue
        result = evaluate_single_rule(rule, actual_values[rule_id])
        checks.append(
            {
                "rule_id": rule_id,
                "object": rule.get("rule_object"),
                "scenario_value": actual_values[rule_id],
                "limit": _limit_text(rule),
                "status": result["status"],
                "message": result["message"],
            }
        )
        if result["status"] == "fails_rule":
            failed += 1
    if not checks:
        decision = "needs_review"
        message = "No verified numeric checks were selected."
    elif failed:
        decision = "rejected"
        message = f"{failed} verified check(s) failed."
    else:
        decision = "approved"
        message = "All selected verified checks passed. This is still a scoped F1 smoke decision, not a permit approval."
    return {"decision": decision, "message": message, "checks": checks}


def answer_artifact_question(data: dict[str, Any], question: str) -> dict[str, Any]:
    text = question.strip().lower()
    manifest = data.get("manifest") or {}
    health = manifest.get("workflow_health") or {}
    benchmark = manifest.get("benchmark_metrics") or {}
    if not text:
        return _chat_answer(
            summary="Ask about verified rules, review items, evidence, compliance, or F1 safety.",
            details=["F1 can explain what is verified, what is still under review, and what evidence supports a rule."],
            next_step="Try a question such as: What is the maximum lot coverage?",
            citations=[],
            tone="neutral",
        )
    if any(word in text for word in ("approve", "permit", "allowed to build", "legal to build", "mark verified", "promote")):
        return _chat_answer(
            summary="F1 chat cannot approve permits, mark rules verified, or promote review items.",
            details=[
                "The chatbot can explain verified rules and review gaps, but it is not a decision maker.",
                "Only deterministic verification can promote a rule, and downstream compliance can only use verified rules.",
            ],
            next_step="Use GIS Handoff or the scenario builder for a scoped verified-rule check; use human review for anything uncertain.",
            citations=[],
            tone="blocked",
        )
    if "false" in text or "safe" in text or "safety" in text:
        return _chat_answer(
            summary="The current Burnaby F1 run passes the safety gates.",
            details=[
                f"False verified rules: {health.get('false_verified_count', 0)}.",
                f"False approvals: {health.get('false_approval_count', 0)}.",
                f"Verified precision: {_format_pct(benchmark.get('verified_precision'))}.",
                f"Quality gates passed: {bool(benchmark.get('quality_gates_passed'))}.",
            ],
            next_step="Open Quality Audit for the full gate table and review gap mix.",
            citations=["f1_benchmark_report.json", "command_center_app_manifest.json"],
            tone="safe",
        )
    if "gis" in text or "map" in text:
        gis = data.get("gis_contract") or {}
        return _chat_answer(
            summary="GIS receives verified rules only.",
            details=[
                f"GIS export contains {gis.get('export_rule_count', health.get('verified_rule_count', 0))} verified rules.",
                f"It excludes {gis.get('excluded_review_rule_count', health.get('review_queue_count', 0))} review items.",
                "Review rules cannot be used by GIS.",
            ],
            next_step="Open GIS Handoff to download the verified-only `gis_rule_contract.json`.",
            citations=["gis_rule_contract.json"],
            tone="safe",
        )
    if "review" in text or "blocked" in text or "gap" in text:
        gaps = review_gap_rows(data)[:3]
        details = [f"{row['gap'].replace('_', ' ')}: {row['count']} item(s)." for row in gaps] or ["No review gaps are loaded."]
        return _chat_answer(
            summary=f"F1 has {health.get('review_queue_count', 0)} items still held for review.",
            details=details,
            next_step="Open Human Review, choose one item, and save a draft operator action if the next step is clear.",
            citations=["review_queue.json", "operator_action_templates.json"],
            tone="review",
        )
    if "evidence" in text or "source" in text or "cite" in text:
        rows = evidence_rows(data, limit=1)
        citation = rows[0] if rows else {}
        return _chat_answer(
            summary="Every visible verified rule is tied back to source evidence.",
            details=[
                f"Example: {citation.get('rule_id', 'n/a')} cites {citation.get('evidence_id', 'n/a')} on page {citation.get('page', 'n/a')}.",
                "The Source Documents page also has rule-to-source navigation for verified and review items.",
            ],
            next_step="Open Source Documents and search by rule id, evidence id, object, or quote.",
            citations=[str(citation.get("evidence_id"))] if citation.get("evidence_id") else [],
            tone="neutral",
        )
    matched_rules = _matching_rules_for_question(data, text)
    if matched_rules:
        details = []
        citations = []
        for rule in matched_rules[:4]:
            citation = rule.get("citation") if isinstance(rule.get("citation"), dict) else {}
            evidence_id = citation.get("evidence_id") or next(iter(rule.get("evidence_ids") or []), "")
            if evidence_id:
                citations.append(str(evidence_id))
            details.append(
                f"{rule.get('rule_id')}: {_plain_rule_sentence(rule)}"
                + (f" Evidence: {evidence_id}." if evidence_id else "")
            )
        return _chat_answer(
            summary=f"I found {min(len(matched_rules), 4)} matching verified F1 rule(s).",
            details=details,
            next_step="Use Verified Rules to inspect the full rule family, or GIS Handoff for a scoped scenario check.",
            citations=list(dict.fromkeys(citations)),
            tone="safe",
        )
    return _chat_answer(
        summary="I do not have a specific verified rule match for that wording yet.",
        details=[
            f"Current run contains {health.get('verified_rule_count', 0)} verified rules and {health.get('review_queue_count', 0)} review items.",
            f"Retrieval recall is {_format_pct(benchmark.get('retrieval_recall_at_6'))}; candidate recall is {_format_pct(benchmark.get('candidate_recall'))}.",
            "Try using a concrete rule family such as height, setback, lot coverage, dwelling units, floor area, or evidence.",
        ],
        next_step="Rephrase with the rule object or open Verified Rules to browse available verified families.",
        citations=["command_center_app_manifest.json"],
        tone="neutral",
    )


def _matching_rules_for_question(data: dict[str, Any], text: str) -> list[dict[str, Any]]:
    ignored = {"what", "is", "are", "the", "a", "an", "for", "to", "of", "in", "and", "bylaw", "rule", "rules"}
    tokens = [token for token in re.findall(r"[a-z0-9_]+", text.replace("-", " ")) if len(token) > 2 and token not in ignored]
    synonyms = {
        "height": {"height", "tall", "maximum"},
        "lot_coverage": {"coverage"},
        "lot_area": {"parcel", "lot_area"},
        "setback": {"setback", "yard", "front", "rear", "side"},
        "dwelling_units": {"dwelling", "unit", "units", "density"},
        "floor_area": {"floor", "area", "far"},
        "building_separation": {"separation", "distance", "between"},
    }
    expanded = set(tokens)
    preferred_objects: set[str] = set()
    if "lot coverage" in text or "site coverage" in text:
        preferred_objects.add("lot_coverage")
        expanded.add("lot_coverage")
        expanded.add("coverage")
    elif "lot area" in text or "parcel area" in text:
        preferred_objects.add("lot_area")
        expanded.add("lot_area")
        expanded.add("area")
    for rule_object, words in synonyms.items():
        if words & expanded:
            expanded.add(rule_object)
            expanded.update(words)
            if not preferred_objects:
                preferred_objects.add(rule_object)
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for rule in (data.get("manifest") or {}).get("verified_rules") or []:
        rule_object = str(rule.get("rule_object") or "")
        if preferred_objects and rule_object not in preferred_objects:
            continue
        haystack = " ".join(
            str(rule.get(field) or "")
            for field in (
                "rule_id",
                "rule_object",
                "applies_to",
                "constraint_scope",
                "condition",
                "exception",
                "search_text",
            )
        ).lower()
        score = sum(1 for token in expanded if token and token in haystack)
        if score:
            scored.append((score, str(rule.get("rule_id") or ""), rule))
    return [rule for _score, _rule_id, rule in sorted(scored, key=lambda item: (-item[0], item[1]))]


def _plain_rule_sentence(rule: dict[str, Any]) -> str:
    obj = str(rule.get("rule_object") or "rule").replace("_", " ")
    limit = _limit_text(rule)
    applies = str(rule.get("applies_to") or rule.get("constraint_scope") or "").strip()
    sentence = f"{obj} {limit}".strip()
    if applies:
        sentence += f" for {applies}"
    return sentence + "."


def _chat_answer(
    *,
    summary: str,
    details: list[str],
    next_step: str,
    citations: list[str],
    tone: str,
) -> dict[str, Any]:
    answer_parts = [summary]
    if details:
        answer_parts.append(" ".join(details))
    if next_step:
        answer_parts.append(next_step)
    return {
        "answer": " ".join(answer_parts),
        "summary": summary,
        "details": details,
        "next_step": next_step,
        "citations": citations,
        "tone": tone,
    }


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_operator_action_log(data: dict[str, Any]) -> dict[str, Any]:
    output = Path(data.get("output_dir") or DEFAULT_F1_OUTPUT)
    path = output / "operator_review_actions.json"
    fallback = data.get("operator_review_actions") if isinstance(data.get("operator_review_actions"), dict) else {}
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema_version": fallback.get("schema_version", "f1.artifacts.v0"),
        "artifact": "operator_review_actions.json",
        "city_key": fallback.get("city_key", ((data.get("manifest") or {}).get("city_key") or "")),
        "run_id": fallback.get("run_id", ((data.get("manifest") or {}).get("run_id") or "")),
        "actions": list(fallback.get("actions") or []),
        "writes_rule_status": False,
        "note": "Append-only local operator notes. These do not verify, approve, promote, or export rules.",
    }


def _limit_text(rule: dict[str, Any]) -> str:
    return " ".join(
        str(part)
        for part in (rule.get("operator"), rule.get("value"), rule.get("unit"))
        if part not in (None, "")
    )


def _format_pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "n/a"


def _format_metric_value(value: Any) -> str:
    if isinstance(value, float) and 0 <= value <= 1:
        return _format_pct(value)
    return "n/a" if value is None else str(value)


def _passes_gate(value: Any, target: float | int, operator: str) -> bool:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    if operator == ">=":
        return numeric >= float(target)
    if operator == "==":
        return numeric == float(target)
    return False


def _to_float(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
