"""Artifact-backed M8 analytic chatbot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .answer_policy import UNSUPPORTED_RESPONSE, refuses_mutation
from .citation_builder import citations_for_rules, citation_for_rule


def load_chatbot_context(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    return {
        "summary": _read_json(output / "m8_summary.json", {}),
        "comparison": _read_json(output / "m7_m8_comparison.json", {}),
        "rules": _read_json(output / "structured_rules.json", []),
        "decisions": _read_json(output / "verification_decisions.json", []),
        "repair_attempts": _read_json(output / "repair_attempts.json", []),
    }


def build_chatbot_context(output_dir: str | Path) -> dict[str, Any]:
    context = load_chatbot_context(output_dir)
    output = Path(output_dir)
    (output / "m8_chatbot_context.json").write_text(json.dumps(context, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return context


def answer_m8_question(question: str, context: dict[str, Any]) -> str:
    if refuses_mutation(question):
        return UNSUPPORTED_RESPONSE
    text = str(question or "").lower()
    comparison = context.get("comparison") or {}
    summary = context.get("summary") or {}
    rules = list(context.get("rules") or [])
    attempts = list(context.get("repair_attempts") or [])
    if "changed from m7 to m8" in text or "what changed" in text:
        m8 = comparison.get("m8") or {}
        return (
            "M8 adds structured source-span contracts, retrieval-backed repair attempts, "
            "dependency-aware statuses, comparison analytics, and artifact-backed chatbot analysis. "
            f"Measured M8 status counts: {m8.get('status_counts', summary.get('status_counts', {}))}."
        )
    if "which rules were repaired" in text or "repaired" in text:
        repaired = [rule for rule in rules if rule.get("status") == "repaired_successfully"]
        if not repaired:
            return f"M8 measured 0 repaired_successfully rules. Repair attempts recorded: {len(attempts)}."
        cites = "; ".join(citations_for_rules(repaired))
        ids = ", ".join(str(rule.get("rule_id")) for rule in repaired[:5])
        return (
            f"M8 marked these rules as repaired_successfully: {ids}. "
            f"Repair attempts recorded: {len(attempts)}. Citations: {cites}."
        )
    if "why" in text and "review" in text:
        review = [rule for rule in rules if rule.get("status") in {"review_needed", "context_required"}]
        if not review:
            return "M8 has no review_needed or context_required rules in the loaded artifacts."
        rule = review[0]
        raw = rule.get("raw") or {}
        reason = raw.get("review_reason") or raw.get("blocking_reason") or "unresolved support gaps remain"
        return f"Rule `{rule.get('rule_id')}` remains under review because {reason}. Citation: {citation_for_rule(rule)}."
    if "weakest coverage" in text or "rule types" in text:
        rows = ((comparison.get("m8") or {}).get("coverage_by_rule_type") or [])
        if not rows:
            return UNSUPPORTED_RESPONSE
        weakest = sorted(rows, key=lambda row: (row.get("coverage", 0), -row.get("total", 0)))[:3]
        return "Weakest M8 rule-type coverage: " + "; ".join(
            f"{row['rule_type']} {row['verified_like']}/{row['total']}" for row in weakest
        )
    if "most unresolved dependencies" in text or "unresolved dependencies" in text:
        status_counts = (comparison.get("m8") or {}).get("status_counts") or summary.get("status_counts") or {}
        return f"Current city `{summary.get('city', comparison.get('city'))}` has {status_counts.get('context_required', 0)} context_required rules."
    if "evidence supports" in text or "supports this verified rule" in text:
        verified = [rule for rule in rules if rule.get("status") in {"verified", "repaired_successfully"}]
        if not verified:
            return "No verified-like M8 rules are loaded."
        rule = verified[0]
        return f"Rule `{rule.get('rule_id')}` is supported by {citation_for_rule(rule)}."
    if "review-needed" in text or "review needed" in text or "reduced by repair" in text:
        m8 = comparison.get("m8") or {}
        return (
            f"M8 review_needed changed from {comparison.get('m7', {}).get('review_needed_count')} "
            f"to {m8.get('review_needed_count')}; measured reduction is {m8.get('review_needed_reduction')}."
        )
    if "zero-false-verified" in text or "false verified" in text or "safety" in text:
        safety = comparison.get("safety") or summary.get("safety") or {}
        return f"M8 preserves the M7 safety gate: {bool(safety.get('m7_safety_preserved'))}. False verified count: {(comparison.get('m8') or {}).get('false_verified_count', 0)}."
    if "inspect next" in text or "reviewer" in text:
        review = [rule for rule in rules if rule.get("status") in {"context_required", "review_needed"}]
        if not review:
            return "No M8 review items are loaded for reviewer inspection."
        rule = review[0]
        return f"Inspect `{rule.get('rule_id')}` next. Start with {citation_for_rule(rule)} and check unresolved support gaps in the rule raw payload."
    return UNSUPPORTED_RESPONSE


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
