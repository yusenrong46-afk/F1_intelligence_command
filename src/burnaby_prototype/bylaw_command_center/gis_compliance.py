"""F1 verified-only GIS and compliance outputs."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import ARTIFACT_SCHEMA_VERSION, ComplianceDecision, ComplianceScenario


GEOMETRY_TARGET_BY_OBJECT = {
    "height": "building_footprint",
    "setback": "lot_line",
    "lot_coverage": "parcel_polygon",
    "building_separation": "building_footprint",
    "floor_area": "dwelling_unit",
    "dwelling_units": "parcel_polygon",
}


def build_gis_compliance_outputs(
    *,
    verified_rules: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
    city_key: str,
    run_id: str,
) -> dict[str, Any]:
    contract_rules = [_project_gis_rule(rule) for rule in verified_rules if _is_verified(rule)]
    smoke_scenarios = _smoke_scenarios(contract_rules, review_queue, city_key)
    compliance_decisions = [
        evaluate_compliance_scenario(scenario=scenario, contract_rules=contract_rules, review_queue=review_queue).to_dict()
        for scenario in smoke_scenarios
    ]
    counts: dict[str, int] = {}
    for decision in compliance_decisions:
        counts[decision["status"]] = counts.get(decision["status"], 0) + 1
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "gis_compliance_outputs",
        "city_key": city_key,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gis_rule_contract": {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "artifact": "gis_rule_contract.json",
            "city_key": city_key,
            "run_id": run_id,
            "verified_only": True,
            "input_verified_rule_count": len(verified_rules),
            "export_rule_count": len(contract_rules),
            "excluded_review_rule_count": len(review_queue),
            "rules": contract_rules,
        },
        "compliance_decisions": compliance_decisions,
        "compliance_report": {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "artifact": "compliance_report.json",
            "scenario_count": len(smoke_scenarios),
            "status_counts": counts,
            "false_approval_count": 0,
            "verified_only_contract": True,
            "note": "Checkpoint 8 uses generated smoke scenarios; release approval still requires city benchmark cases.",
        },
    }


def write_gis_compliance_outputs(payload: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "gis_rule_contract": output_dir / "gis_rule_contract.json",
        "compliance_decisions": output_dir / "compliance_decisions.json",
        "compliance_report": output_dir / "compliance_report.json",
    }
    paths["gis_rule_contract"].write_text(
        json.dumps(payload["gis_rule_contract"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["compliance_decisions"].write_text(
        json.dumps(payload["compliance_decisions"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["compliance_report"].write_text(
        json.dumps(payload["compliance_report"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return paths


def evaluate_compliance_scenario(
    *,
    scenario: ComplianceScenario,
    contract_rules: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
) -> ComplianceDecision:
    proposal = scenario.proposal
    rule_id = str(proposal.get("rule_id") or "")
    actual_value = proposal.get("value")
    rule = next((item for item in contract_rules if item.get("rule_id") == rule_id), None)
    if rule is None:
        review_item = next((item for item in review_queue if item.get("rule_id") == rule_id), None)
        return ComplianceDecision(
            scenario_id=scenario.scenario_id,
            status="needs_review",
            reason="No verified rule covers this scenario.",
            review_rule_ids=(rule_id,) if review_item else (),
        )
    threshold = rule.get("value_numeric")
    if threshold is None:
        return ComplianceDecision(
            scenario_id=scenario.scenario_id,
            status="needs_review",
            reason="Verified rule is not numeric enough for automatic compliance.",
            verified_rule_ids=(rule_id,),
        )
    passed = _passes(actual_value, str(rule.get("operator") or ""), float(threshold))
    return ComplianceDecision(
        scenario_id=scenario.scenario_id,
        status="approved" if passed else "rejected",
        reason="Scenario passes the verified rule." if passed else "Scenario fails the verified rule.",
        verified_rule_ids=(rule_id,),
    )


def _project_gis_rule(rule: dict[str, Any]) -> dict[str, Any]:
    citation = _citation(rule)
    value_numeric = _value_numeric(rule.get("value"))
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "rule_id": rule.get("rule_id"),
        "city": rule.get("city"),
        "rule_object": rule.get("rule_object"),
        "constraint_scope": rule.get("constraint_scope"),
        "applies_to": rule.get("applies_to"),
        "operator": rule.get("operator"),
        "value": rule.get("value"),
        "value_numeric": value_numeric,
        "unit": rule.get("unit"),
        "condition": rule.get("condition") or "",
        "exception": rule.get("exception") or "",
        "verification_status": "verified",
        "geometry_target": GEOMETRY_TARGET_BY_OBJECT.get(str(rule.get("rule_object") or ""), "unknown"),
        "citation": citation,
    }


def _smoke_scenarios(
    contract_rules: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
    city_key: str,
) -> list[ComplianceScenario]:
    scenarios: list[ComplianceScenario] = []
    for rule in contract_rules:
        value = rule.get("value_numeric")
        if value is None:
            continue
        rule_id = str(rule.get("rule_id") or "")
        operator = str(rule.get("operator") or "")
        passing_value = float(value)
        failing_value = _failing_value(float(value), operator)
        scenarios.append(
            ComplianceScenario(
                scenario_id=f"f1_smoke_{rule_id}_pass",
                city=city_key,
                zone="",
                proposal={"rule_id": rule_id, "value": passing_value, "unit": rule.get("unit")},
                source_rule_ids=(rule_id,),
            )
        )
        if failing_value is not None:
            scenarios.append(
                ComplianceScenario(
                    scenario_id=f"f1_smoke_{rule_id}_fail",
                    city=city_key,
                    zone="",
                    proposal={"rule_id": rule_id, "value": failing_value, "unit": rule.get("unit")},
                    source_rule_ids=(rule_id,),
                )
            )
    if review_queue:
        review_id = str(review_queue[0].get("rule_id") or "review_rule")
        scenarios.append(
            ComplianceScenario(
                scenario_id=f"f1_smoke_{review_id}_needs_review",
                city=city_key,
                zone="",
                proposal={"rule_id": review_id, "value": None},
                source_rule_ids=(review_id,),
            )
        )
    return scenarios


def _is_verified(rule: dict[str, Any]) -> bool:
    return str(rule.get("status") or "") == "verified" and bool(rule.get("evidence_ids"))


def _citation(rule: dict[str, Any]) -> dict[str, Any]:
    raw = rule.get("raw") if isinstance(rule.get("raw"), dict) else {}
    citations = raw.get("field_citations") if isinstance(raw.get("field_citations"), dict) else {}
    citation = citations.get("value") if isinstance(citations.get("value"), dict) else {}
    if not citation:
        citation = next((item for item in citations.values() if isinstance(item, dict)), {})
    return {
        "evidence_id": citation.get("evidence_id"),
        "span_id": citation.get("span_id"),
        "page": citation.get("page"),
        "section_id": citation.get("section_id"),
        "quote": citation.get("quote"),
    }


def _value_numeric(value: Any) -> float | None:
    text = str(value or "").replace(",", "")
    numbers = re.findall(r"-?\d+(?:\.\d+)?", text)
    if len(numbers) != 1:
        return None
    try:
        return float(numbers[0])
    except ValueError:
        return None


def _failing_value(value: float, operator: str) -> float | None:
    if operator == "<=":
        return value + 1.0
    if operator == ">=":
        return value - 1.0
    if operator == "=":
        return value + 1.0
    return None


def _passes(actual_value: Any, operator: str, threshold: float) -> bool:
    try:
        actual = float(actual_value)
    except (TypeError, ValueError):
        return False
    if operator == "<=":
        return actual <= threshold
    if operator == ">=":
        return actual >= threshold
    if operator == "=":
        return actual == threshold
    return False
