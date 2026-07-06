"""Checkpoint 16 product-operations artifacts for F1.

The operations layer makes the command center usable without changing the trust
model. It creates reviewer action drafts, scenario templates, and evidence
navigation indexes, but it never edits rule status or GIS exports.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import ARTIFACT_SCHEMA_VERSION


OPERATION_ARTIFACTS = {
    "operator_action_templates": "operator_action_templates.json",
    "operator_review_actions": "operator_review_actions.json",
    "scenario_templates": "scenario_templates.json",
    "evidence_navigation": "evidence_navigation.json",
    "operations_report": "operations_report.json",
}


def build_product_operations_outputs(
    *,
    verified_rules: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
    gis_rule_contract: dict[str, Any],
    city_key: str,
    run_id: str,
) -> dict[str, Any]:
    action_templates = [_action_template(item, index) for index, item in enumerate(review_queue, start=1)]
    scenario_templates = [
        template for rule in gis_rule_contract.get("rules") or [] if (template := _scenario_template(rule)) is not None
    ]
    evidence_navigation = _evidence_navigation(
        verified_rules=verified_rules,
        review_queue=review_queue,
        gis_rule_contract=gis_rule_contract,
        city_key=city_key,
        run_id=run_id,
    )
    generated_at = datetime.now(timezone.utc).isoformat()
    report = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "operations_report.json",
        "city_key": city_key,
        "run_id": run_id,
        "generated_at": generated_at,
        "action_template_count": len(action_templates),
        "scenario_template_count": len(scenario_templates),
        "evidence_navigation_count": len(evidence_navigation["items"]),
        "operator_actions_persisted_count": 0,
        "writes_rule_status": False,
        "writes_verified_rules": False,
        "writes_gis_contract": False,
        "verified_only_boundary_preserved": True,
        "note": "Checkpoint 16 adds operator-facing drafts and scenario templates. It does not promote, approve, or edit verified outputs.",
    }
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "product_operations_outputs",
        "city_key": city_key,
        "run_id": run_id,
        "generated_at": generated_at,
        "operation_artifacts": dict(OPERATION_ARTIFACTS),
        "operator_action_templates": action_templates,
        "operator_review_actions": _empty_action_log(city_key=city_key, run_id=run_id, generated_at=generated_at),
        "scenario_templates": scenario_templates,
        "evidence_navigation": evidence_navigation,
        "operations_report": report,
    }


def write_product_operations_outputs(payload: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "operator_action_templates": output_dir / "operator_action_templates.json",
        "operator_review_actions": output_dir / "operator_review_actions.json",
        "scenario_templates": output_dir / "scenario_templates.json",
        "evidence_navigation": output_dir / "evidence_navigation.json",
        "operations_report": output_dir / "operations_report.json",
    }
    paths["operator_action_templates"].write_text(
        json.dumps(payload["operator_action_templates"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not paths["operator_review_actions"].exists():
        paths["operator_review_actions"].write_text(
            json.dumps(payload["operator_review_actions"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    paths["scenario_templates"].write_text(
        json.dumps(payload["scenario_templates"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["evidence_navigation"].write_text(
        json.dumps(payload["evidence_navigation"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["operations_report"].write_text(
        json.dumps(payload["operations_report"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return paths


def _action_template(item: dict[str, Any], index: int) -> dict[str, Any]:
    rule_id = str(item.get("rule_id") or f"review_{index:03d}")
    candidate = item.get("candidate") if isinstance(item.get("candidate"), dict) else item
    gaps = [str(gap) for gap in item.get("support_gaps") or item.get("unresolved_dependencies") or []]
    evidence_ids = [str(eid) for eid in candidate.get("evidence_ids") or [] if eid]
    recommended_action = _recommended_action(gaps, candidate)
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "action_template_id": f"f1_op_{rule_id}",
        "rule_id": rule_id,
        "current_status": str(item.get("status") or candidate.get("status") or "review_needed"),
        "rule_object": str(candidate.get("rule_object") or ""),
        "candidate_limit": _limit_text(candidate),
        "support_gaps": gaps,
        "evidence_ids": evidence_ids,
        "recommended_action": recommended_action,
        "allowed_actions": [
            "needs_source_research",
            "ready_for_repair_candidate",
            "request_legal_review",
            "mark_duplicate_candidate",
            "defer",
        ],
        "default_note": _default_note(recommended_action, gaps),
        "writes_to": "operator_review_actions.json",
        "blocked_outputs": ["verified_rules.json", "verification_decisions.json", "gis_rule_contract.json"],
        "cannot_promote": True,
    }


def _scenario_template(rule: dict[str, Any]) -> dict[str, Any] | None:
    value = _value_numeric(rule.get("value"))
    if value is None:
        return None
    operator = str(rule.get("operator") or "")
    passing = _passing_value(value, operator)
    failing = _failing_value(value, operator)
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "scenario_template_id": f"f1_scenario_{rule.get('rule_id')}",
        "rule_id": str(rule.get("rule_id") or ""),
        "rule_object": str(rule.get("rule_object") or ""),
        "operator": operator,
        "threshold": value,
        "unit": str(rule.get("unit") or ""),
        "passing_example_value": passing,
        "failing_example_value": failing,
        "status_if_unselected_rule": "needs_review",
        "approval_boundary": "A single-rule pass is not a permit approval.",
    }


def _evidence_navigation(
    *,
    verified_rules: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
    gis_rule_contract: dict[str, Any],
    city_key: str,
    run_id: str,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for rule in gis_rule_contract.get("rules") or verified_rules:
        citation = rule.get("citation") if isinstance(rule.get("citation"), dict) else {}
        items.append(
            {
                "source": "verified",
                "rule_id": str(rule.get("rule_id") or ""),
                "status": "verified",
                "rule_object": str(rule.get("rule_object") or ""),
                "evidence_id": str(citation.get("evidence_id") or ""),
                "span_id": str(citation.get("span_id") or ""),
                "section_id": str(citation.get("section_id") or ""),
                "page": citation.get("page"),
                "quote": _clip(citation.get("quote"), 700),
            }
        )
    for item in review_queue:
        candidate = item.get("candidate") if isinstance(item.get("candidate"), dict) else item
        field_citations = candidate.get("raw", {}).get("field_citations") if isinstance(candidate.get("raw"), dict) else {}
        citations = [value for value in (field_citations or {}).values() if isinstance(value, dict)]
        if not citations:
            citations = [{"evidence_id": eid} for eid in candidate.get("evidence_ids") or [] if eid]
        for citation in citations[:3]:
            items.append(
                {
                    "source": "review",
                    "rule_id": str(item.get("rule_id") or candidate.get("rule_id") or ""),
                    "status": str(item.get("status") or candidate.get("status") or "review_needed"),
                    "rule_object": str(candidate.get("rule_object") or ""),
                    "evidence_id": str(citation.get("evidence_id") or ""),
                    "span_id": str(citation.get("span_id") or ""),
                    "section_id": str(citation.get("section_id") or ""),
                    "page": citation.get("page"),
                    "quote": _clip(citation.get("quote"), 700),
                }
            )
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "evidence_navigation.json",
        "city_key": city_key,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verified_only_gis_rule_count": len(gis_rule_contract.get("rules") or []),
        "review_item_count": len(review_queue),
        "items": items,
    }


def _empty_action_log(*, city_key: str, run_id: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "operator_review_actions.json",
        "city_key": city_key,
        "run_id": run_id,
        "generated_at": generated_at,
        "actions": [],
        "writes_rule_status": False,
        "note": "Append-only local operator notes. These do not verify, approve, promote, or export rules.",
    }


def _recommended_action(gaps: list[str], candidate: dict[str, Any]) -> str:
    gap_text = " ".join(gaps).lower()
    if "dependency" in gap_text or candidate.get("condition") or candidate.get("exception"):
        return "request_legal_review"
    if "value" in gap_text or "operator" in gap_text or "scope" in gap_text or "object" in gap_text:
        return "needs_source_research"
    if candidate.get("evidence_ids"):
        return "ready_for_repair_candidate"
    return "defer"


def _default_note(action: str, gaps: list[str]) -> str:
    if action == "needs_source_research":
        return "Find exact quoted source support for the blocked field before rerunning repair."
    if action == "request_legal_review":
        return "Confirm condition, exception, or dependency interpretation before any verifier rerun."
    if action == "ready_for_repair_candidate":
        return "Prepare a proof patch and rerun deterministic verification."
    if gaps:
        return f"Review unresolved gaps: {', '.join(gaps[:3])}."
    return "Keep this item in review until more evidence is available."


def _limit_text(rule: dict[str, Any]) -> str:
    return " ".join(str(part) for part in (rule.get("operator"), rule.get("value"), rule.get("unit")) if part not in (None, ""))


def _value_numeric(value: Any) -> float | None:
    numbers = re.findall(r"-?\d+(?:\.\d+)?", str(value or "").replace(",", ""))
    if len(numbers) != 1:
        return None
    try:
        return float(numbers[0])
    except ValueError:
        return None


def _passing_value(value: float, operator: str) -> float:
    if operator in {"<=", "<", "="}:
        return value
    if operator in {">=", ">"}:
        return value
    return value


def _failing_value(value: float, operator: str) -> float | None:
    if operator in {"<=", "<", "="}:
        return value + 1.0
    if operator in {">=", ">"}:
        return value - 1.0
    return None


def _clip(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."
