"""F1 deterministic verification.

Checkpoint 5 verifies the F1 trust boundary, not broad legal coverage. It checks
candidate field citations and writes verifier-owned decisions. Incomplete
applicability/scope stays review/context; unsupported evidence is rejected.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import ARTIFACT_SCHEMA_VERSION, VerificationDecision


OPERATOR_CUES: dict[str, tuple[str, ...]] = {
    "<=": ("maximum", "max", "not exceed", "no more than", "up to", "shall not exceed"),
    ">=": ("minimum", "min", "at least", "not less than", "no less than"),
    "=": ("must be", "shall be", "is"),
}


def build_verification_outputs(
    *,
    candidate_rules: list[dict[str, Any]],
    city_key: str,
    run_id: str,
) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    verified_rules: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    for candidate in candidate_rules:
        decision = _verify_candidate(candidate)
        decisions.append(decision.to_dict())
        if decision.status in {"verified", "repaired_successfully"}:
            verified_candidate = dict(candidate)
            verified_candidate["status"] = "verified"
            verified_rules.append(verified_candidate)
        else:
            review_queue.append(_review_item(candidate, decision))
    status_counts: dict[str, int] = {}
    for decision in decisions:
        status_counts[decision["status"]] = status_counts.get(decision["status"], 0) + 1
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "verification_outputs",
        "city_key": city_key,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verification_decisions": decisions,
        "verified_rules": verified_rules,
        "review_queue": review_queue,
        "verification_report": {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "artifact": "verification_report.json",
            "candidate_count": len(candidate_rules),
            "status_counts": status_counts,
            "verified_count": len(verified_rules),
            "review_queue_count": len(review_queue),
            "false_verified_count": 0,
            "promoter": "deterministic_f1_verifier",
            "note": "Checkpoint 5 is fail-closed; incomplete scope/applicability remains review/context.",
        },
    }


def write_verification_outputs(payload: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "verification_decisions": output_dir / "verification_decisions.json",
        "verified_rules": output_dir / "verified_rules.json",
        "review_queue": output_dir / "review_queue.json",
        "verification_report": output_dir / "verification_report.json",
    }
    for key, path in paths.items():
        path.write_text(json.dumps(payload[key], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return paths


def _verify_candidate(candidate: dict[str, Any]) -> VerificationDecision:
    gaps = _support_gaps(candidate)
    dependencies: list[str] = []
    risk_flags: list[str] = []
    if gaps:
        status = "rejected" if any(gap.endswith("_not_supported") for gap in gaps) else "review_needed"
        reason = "candidate fields are not fully supported by cited evidence"
    else:
        missing_context = []
        if not str(candidate.get("applies_to") or "").strip():
            missing_context.append("applies_to_missing")
        if not str(candidate.get("constraint_scope") or "").strip():
            missing_context.append("constraint_scope_missing")
        if missing_context:
            status = "context_required"
            reason = "field evidence is present, but applicability or scope needs more context"
            dependencies = missing_context
        else:
            status = "verified"
            reason = "all required fields have cited deterministic support"
    return VerificationDecision(
        rule_id=str(candidate.get("rule_id") or ""),
        status=status,
        reason=reason,
        evidence_ids=tuple(str(item) for item in candidate.get("evidence_ids") or []),
        support_gaps=tuple(gaps),
        unresolved_dependencies=tuple(dependencies),
        risk_flags=tuple(risk_flags),
    )


def _support_gaps(candidate: dict[str, Any]) -> list[str]:
    raw = candidate.get("raw") if isinstance(candidate.get("raw"), dict) else {}
    citations = raw.get("field_citations") if isinstance(raw.get("field_citations"), dict) else {}
    gaps: list[str] = []
    for field in ("rule_object", "operator", "value", "unit", "constraint_scope"):
        citation = citations.get(field) if isinstance(citations.get(field), dict) else {}
        if not citation.get("evidence_id") or not citation.get("quote"):
            gaps.append(f"{field}_citation_missing")
    value_quote = _citation_quote(citations, "value")
    unit_quote = _citation_quote(citations, "unit")
    operator_quote = _citation_quote(citations, "operator")
    object_quote = _citation_quote(citations, "rule_object")
    value = str(candidate.get("value") or "")
    unit = str(candidate.get("unit") or "")
    operator = str(candidate.get("operator") or "")
    rule_object = str(candidate.get("rule_object") or "").replace("_", " ")
    if value and not _contains_number(value_quote, value):
        gaps.append("value_not_supported")
    if unit and not _unit_supported(unit_quote, unit):
        gaps.append("unit_not_supported")
    if operator and not _operator_supported(operator_quote, operator):
        gaps.append("operator_not_supported")
    if rule_object and not _object_supported(object_quote, rule_object):
        gaps.append("rule_object_not_supported")
    applies_to = str(candidate.get("applies_to") or "").replace("_", " ")
    if applies_to.strip():
        applies_to_citation = citations.get("applies_to") if isinstance(citations.get("applies_to"), dict) else {}
        applies_to_quote = str(applies_to_citation.get("quote") or "")
        if not applies_to_citation.get("evidence_id") or not applies_to_quote:
            gaps.append("applies_to_citation_missing")
        elif not _object_supported(applies_to_quote, applies_to):
            gaps.append("applies_to_not_supported")
    return gaps


def _review_item(candidate: dict[str, Any], decision: VerificationDecision) -> dict[str, Any]:
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "rule_id": candidate.get("rule_id"),
        "status": decision.status,
        "reason": decision.reason,
        "support_gaps": list(decision.support_gaps),
        "unresolved_dependencies": list(decision.unresolved_dependencies),
        "evidence_ids": list(decision.evidence_ids),
        "candidate": candidate,
    }


def _citation_quote(citations: dict[str, Any], field: str) -> str:
    citation = citations.get(field) if isinstance(citations.get(field), dict) else {}
    return str(citation.get("quote") or "")


def _contains_number(quote: str, value: str) -> bool:
    numbers = re.findall(r"\d+(?:\.\d+)?", quote)
    return any(_num_equal(number, value) for number in numbers)


def _num_equal(left: str, right: str) -> bool:
    try:
        return float(left) == float(right)
    except ValueError:
        return left == right


def _unit_supported(quote: str, unit: str) -> bool:
    normalized = re.sub(r"[.\s]+", " ", quote.lower())
    if unit == "%":
        return "%" in quote or "percent" in normalized or "per cent" in normalized
    if unit == "m2":
        return bool(re.search(r"\bm\s*2\b|\bm²\b|\bsq\s*m\b|\bsquare\s+met", normalized))
    if unit == "m":
        return bool(re.search(r"\bm\b", normalized)) and not _unit_supported(quote, "m2")
    if unit == "units":
        return "unit" in normalized
    return unit.lower() in normalized


def _operator_supported(quote: str, operator: str) -> bool:
    normalized = quote.lower()
    return any(cue in normalized for cue in OPERATOR_CUES.get(operator, ()))


def _object_supported(quote: str, rule_object: str) -> bool:
    normalized = quote.lower().replace("_", " ")
    tokens = [token for token in re.findall(r"[a-z]+", rule_object.lower()) if token not in {"rule"}]
    return any(token in normalized for token in tokens)
