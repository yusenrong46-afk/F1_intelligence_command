"""F1 structured extraction.

Checkpoint 4 is intentionally conservative: it turns retrieval evidence into
structured candidate rules with field-level citations, but every candidate
remains review-needed until deterministic verification is implemented.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import ARTIFACT_SCHEMA_VERSION, CandidateRule


MEASUREMENT_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>m2\b|m²\b|sq\.?\s?m\b|square\s+metres?\b|square\s+meters?\b|m\b|%|percent\b|per\s?cent\b|storeys?\b|stories\b|units?\b)",
    re.IGNORECASE,
)


QUERY_RULE_MAP: dict[str, dict[str, str]] = {
    "maximum height": {"rule_type": "height", "rule_object": "height", "operator": "<=", "preferred_units": "m"},
    "maximum storeys": {"rule_type": "storeys", "rule_object": "storeys", "operator": "<=", "preferred_units": "storeys"},
    "minimum setback": {"rule_type": "setback", "rule_object": "setback", "operator": ">=", "preferred_units": "m"},
    "lot coverage": {"rule_type": "lot_coverage", "rule_object": "lot_coverage", "operator": "<=", "preferred_units": "%"},
    "impervious surfaces": {"rule_type": "impervious_surface", "rule_object": "impervious_surface", "operator": "<=", "preferred_units": "%"},
    "dwelling units": {"rule_type": "dwelling_units", "rule_object": "dwelling_units", "operator": "<=", "preferred_units": "units"},
    "building separation": {"rule_type": "building_separation", "rule_object": "building_separation", "operator": ">=", "preferred_units": "m"},
    "minimum lot area": {"rule_type": "lot_area", "rule_object": "lot_area", "operator": ">=", "preferred_units": "m2"},
    "maximum lot area": {"rule_type": "lot_area", "rule_object": "lot_area", "operator": "<=", "preferred_units": "m2"},
    "fire access corridor": {"rule_type": "fire_access_corridor", "rule_object": "fire_access_corridor", "operator": ">=", "preferred_units": "m"},
    "floor area": {"rule_type": "floor_area", "rule_object": "floor_area", "operator": ">=", "preferred_units": "m2"},
}


def build_candidate_rules_from_retrieval(
    *,
    retrieval_report: dict[str, Any],
    city_key: str,
    run_id: str,
) -> dict[str, Any]:
    candidates: list[CandidateRule] = []
    skipped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str, str, str]] = set()
    for query_row in retrieval_report.get("queries") or []:
        query = str(query_row.get("query") or "")
        rule_defaults = _rule_defaults(query)
        if not rule_defaults:
            skipped.append({"query": query, "reason": "unsupported_query_family"})
            continue
        selected = _first_measurement_hit(
            query_row.get("hits") or [],
            preferred_unit=rule_defaults.get("preferred_units", ""),
            query=query,
        )
        if selected is None:
            skipped.append({"query": query, "reason": "no_measurement_hit"})
            continue
        hit, measurement = selected
        quote = str(hit.get("quote") or "")
        value = _normalize_value(measurement.group("value"))
        unit = _measurement_unit(quote, measurement)
        key = _candidate_key(
            rule_defaults["rule_type"],
            rule_defaults["operator"],
            value,
            unit,
            "",
            "",
            _constraint_scope(query, quote),
        )
        if key in seen:
            skipped.append({"query": query, "reason": "duplicate_measurement", "value": value, "unit": unit})
            continue
        seen.add(key)
        evidence_id = str(hit.get("evidence_id") or "")
        measurement_quote = _measurement_quote(quote, measurement)
        rule = CandidateRule(
            rule_id=f"f1_candidate_{len(candidates) + 1:04d}",
            city=city_key,
            zone="",
            rule_type=rule_defaults["rule_type"],
            rule_object=rule_defaults["rule_object"],
            constraint_scope=_constraint_scope(query, quote),
            applies_to="",
            operator=rule_defaults["operator"],
            value=value,
            unit=unit,
            condition="",
            exception="",
            evidence_ids=(evidence_id,),
            status="review_needed",
            raw={
                "run_id": run_id,
                "query": query,
                "span_id": hit.get("span_id"),
                "page": hit.get("page"),
                "section_id": hit.get("section_id"),
                "field_citations": {
                    "rule_object": _citation(hit, quote),
                    "operator": _citation(hit, quote),
                    "value": _citation(hit, measurement_quote),
                    "unit": _citation(hit, measurement_quote),
                    "constraint_scope": _citation(hit, quote),
                },
                "extraction_note": "Candidate only; deterministic verification has not promoted this rule.",
            },
        )
        candidates.append(rule)
    table_added, table_skipped = _add_table_candidates(
        retrieval_report=retrieval_report,
        candidates=candidates,
        seen=seen,
        city_key=city_key,
        run_id=run_id,
    )
    skipped.extend(table_skipped)
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "candidate_rules.json",
        "city_key": city_key,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_rules": [candidate.to_dict() for candidate in candidates],
        "extraction_report": {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "artifact": "extraction_report.json",
            "method": "retrieval_measurement_candidate_extractor",
            "candidate_count": len(candidates),
            "table_candidate_count": table_added,
            "skipped_count": len(skipped),
            "skipped": skipped,
            "all_candidates_review_needed": all(candidate.status == "review_needed" for candidate in candidates),
            "promoted_count": 0,
            "note": "Checkpoint 4 extraction proposes structured candidates only; verification is a later gate.",
        },
    }


def write_candidate_rules(payload: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = output_dir / "candidate_rules.json"
    report_path = output_dir / "extraction_report.json"
    candidates_path.write_text(
        json.dumps(payload["candidate_rules"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(payload["extraction_report"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"candidate_rules": candidates_path, "extraction_report": report_path}


def _add_table_candidates(
    *,
    retrieval_report: dict[str, Any],
    candidates: list[CandidateRule],
    seen: set[tuple[str, str, str, str, str, str, str]],
    city_key: str,
    run_id: str,
) -> tuple[int, list[dict[str, Any]]]:
    added = 0
    skipped: list[dict[str, Any]] = []
    for hit in _unique_hits(retrieval_report):
        quote = str(hit.get("quote") or "")
        if hit.get("block_type") == "table" and "101.4" in str(hit.get("section_id") or quote):
            for spec in _development_table_specs():
                if not _quote_has_terms(quote, spec["required_terms"]):
                    skipped.append({"query": "table_101_4", "reason": "table_terms_missing", "spec": spec["label"]})
                    continue
                if _append_spec_candidate(
                    spec=spec,
                    hit=hit,
                    candidates=candidates,
                    seen=seen,
                    city_key=city_key,
                    run_id=run_id,
                    source_kind="development_table",
                ):
                    added += 1
        if hit.get("block_type") == "table" and "Principal Use" in quote:
            for spec in _permitted_use_specs():
                if _quote_has_terms(quote, spec["required_terms"]) and _append_spec_candidate(
                    spec=spec,
                    hit=hit,
                    candidates=candidates,
                    seen=seen,
                    city_key=city_key,
                    run_id=run_id,
                    source_kind="permitted_use_table",
                ):
                    added += 1
        if "Access and Fire Safety" in quote or "Community Heritage Register" in quote:
            for spec in _clause_specs():
                if _quote_has_terms(quote, spec["required_terms"]) and _append_spec_candidate(
                    spec=spec,
                    hit=hit,
                    candidates=candidates,
                    seen=seen,
                    city_key=city_key,
                    run_id=run_id,
                    source_kind="clause_pattern",
                ):
                    added += 1
    return added, skipped


def _append_spec_candidate(
    *,
    spec: dict[str, str],
    hit: dict[str, Any],
    candidates: list[CandidateRule],
    seen: set[tuple[str, str, str, str, str, str, str]],
    city_key: str,
    run_id: str,
    source_kind: str,
) -> bool:
    key = _candidate_key(
        spec["rule_type"],
        spec["operator"],
        spec.get("value", ""),
        spec.get("unit", ""),
        spec.get("applies_to", ""),
        spec.get("condition", ""),
        spec.get("constraint_scope", ""),
    )
    if key in seen:
        return False
    seen.add(key)
    quote = str(hit.get("quote") or "")
    evidence_id = str(hit.get("evidence_id") or "")
    citation = _citation(hit, quote)
    value_quote = spec.get("value_quote") or _value_quote(spec.get("value", ""), spec.get("unit", ""))
    value_citation = _citation(hit, value_quote)
    rule = CandidateRule(
        rule_id=f"f1_candidate_{len(candidates) + 1:04d}",
        city=city_key,
        zone="",
        rule_type=spec["rule_type"],
        rule_object=spec["rule_object"],
        constraint_scope=spec.get("constraint_scope", ""),
        applies_to=spec.get("applies_to", ""),
        operator=spec["operator"],
        value=spec.get("value", ""),
        unit=spec.get("unit", ""),
        condition=spec.get("condition", ""),
        exception=spec.get("exception", ""),
        evidence_ids=(evidence_id,),
        status="review_needed",
        raw={
            "run_id": run_id,
            "query": source_kind,
            "span_id": hit.get("span_id"),
            "page": hit.get("page"),
            "section_id": hit.get("section_id"),
            "field_citations": {
                "rule_object": citation,
                "operator": citation,
                "value": value_citation,
                "unit": value_citation,
                "constraint_scope": citation,
                "applies_to": citation,
            },
            "extraction_note": "Table/clause-derived candidate only; deterministic verification decides promotion.",
        },
    )
    candidates.append(rule)
    return True


def _development_table_specs() -> list[dict[str, str | list[str]]]:
    specs: list[dict[str, str | list[str]]] = [
        _spec("dwelling_units", "dwelling_units", "lot", "Rowhouse", "<=", "3", "units", "", ["Permitted Dwelling Units", "Rowhouse", "1 to 3 Units"]),
        _spec("dwelling_units", "dwelling_units", "lot", "Small-Scale Multi-Unit 1 to 2 Units", "<=", "2", "units", "", ["Permitted Dwelling Units", "Small-Scale Multi-Unit", "1 to 2 Units"]),
        _spec("dwelling_units", "dwelling_units", "lot", "Small-Scale Multi-Unit 3 to 4 Units", "<=", "4", "units", "", ["Permitted Dwelling Units", "3 to 4 Units"]),
        _spec("dwelling_units", "dwelling_units", "lot", "Small-Scale Multi-Unit 5 to 6 Units", "<=", "6", "units", "Frequent Transit Network Area Only", ["Permitted Dwelling Units", "5 to 6 Units", "Frequent Transit"]),
        _spec("lot_area", "lot_area", "lot", "Small-Scale Multi-Unit", ">=", "281", "m2", "4 Units Only", ["Minimum Lot Area", "281m 2", "4 Units Only"]),
        _spec("lot_coverage", "lot_coverage", "lot", "Rowhouse", "<=", "55", "%", "", ["Maximum Lot Coverage", "All Buildings", "55%"]),
        _spec("lot_coverage", "lot_coverage", "lot", "Small-Scale Multi-Unit 1 to 2 Units", "<=", "40", "%", "Lots < 567 m2", ["Lots < 567", "40%"]),
        _spec("lot_coverage", "lot_coverage", "lot", "Small-Scale Multi-Unit 1 to 2 Units", "<=", "30", "%", "Lots > 567 m2", ["Lots > 567", "30%"]),
        _spec("lot_coverage", "lot_coverage", "lot", "Small-Scale Multi-Unit 3 to 4 Units", "<=", "40", "%", "", ["3 to 4 Units", "40%"]),
        _spec("lot_coverage", "lot_coverage", "lot", "Small-Scale Multi-Unit 5 to 6 Units", "<=", "45", "%", "Frequent Transit Network Area Only", ["5 to 6 Units", "45%"]),
        _spec("impervious_surface", "impervious_surface", "lot", "Rowhouse", "<=", "70", "%", "", ["Impervious Surfaces", "70%"]),
        _spec("impervious_surface", "impervious_surface", "lot", "Small-Scale Multi-Unit 1 to 2 Units", "<=", "60", "%", "", ["Impervious Surfaces", "60%"]),
        _spec("impervious_surface", "impervious_surface", "lot", "Small-Scale Multi-Unit 3 to 4 Units", "<=", "60", "%", "", ["Impervious Surfaces", "60%"]),
        _spec("impervious_surface", "impervious_surface", "lot", "Small-Scale Multi-Unit 5 to 6 Units", "<=", "70", "%", "", ["Impervious Surfaces", "70%"]),
        _spec("height", "height", "building", "Front Principal Buildings", "<=", "10", "m", "sloping roof", ["Front Principal Buildings", "sloping roof: 10m"]),
        _spec("height", "height", "building", "Front Principal Buildings", "<=", "9.5", "m", "flat roof", ["Front Principal Buildings", "flat roof: 9.5m"]),
        _spec("storeys", "storeys", "building", "Front Principal Buildings", "<=", "3", "storeys", "", ["Front Principal Buildings", "3 storeys"]),
        _spec("storeys", "storeys", "building", "Front Principal Buildings", "<=", "2.5", "storeys", "", ["Front Principal Buildings", "2.5 storeys"]),
        _spec("height", "height", "building", "Rear Principal Buildings", "<=", "7.5", "m", "sloping roof", ["Rear Principal Buildings", "sloping roof: 7.5m"]),
        _spec("height", "height", "building", "Rear Principal Buildings", "<=", "7", "m", "flat roof", ["Rear Principal Buildings", "flat roof: 7.0m"]),
        _spec("storeys", "storeys", "building", "Rear Principal Buildings", "<=", "2", "storeys", "basement inclusive", ["Rear Principal Buildings", "2 storeys"]),
        _spec("height", "height", "building", "Accessory Buildings", "<=", "4", "m", "", ["Accessory Buildings", "4.0m"]),
        _spec("storeys", "storeys", "building", "Accessory Buildings", "<=", "1", "storeys", "", ["Accessory Buildings", "1 storey"]),
        _spec("setback", "setback", "street_yard_front", "All Buildings", ">=", "4", "m", "front street yard", ["Street Yard", "front: 4.0m"]),
        _spec("setback", "setback", "street_yard_flanking", "All Buildings", ">=", "3", "m", "flanking street yard", ["Street Yard", "flanking: 3.0m"]),
        _spec("setback", "setback", "lane_yard", "All Buildings", ">=", "1.5", "m", "", ["Lane Yard", "1.5m"]),
        _spec("setback", "setback", "interior_rear_yard", "Rear Principal Buildings", ">=", "3", "m", "", ["Interior Rear Yard", "3.0 m"]),
        _spec("setback", "setback", "interior_rear_yard", "Accessory Buildings", ">=", "1.5", "m", "accessory buildings exception", ["Interior Rear Yard", "1.5m", "accessory buildings"]),
        _spec("setback", "setback", "interior_side_yard", "All Buildings", ">=", "0", "m", "", ["Interior Side Yard", "0 m"]),
        _spec("setback", "setback", "interior_side_yard", "End unit lots", ">=", "1.2", "m", "end unit lots", ["Interior Side Yard", "1.2 m", "end unit lots"]),
        _spec("building_separation", "building_separation", "building_separation", "Front Principal Buildings", ">=", "2.4", "m", "between front principals", ["Between Front Principals", "2.4 m"]),
        _spec("building_separation", "building_separation", "building_separation", "Rear Principal Buildings", ">=", "2.4", "m", "between rear principals", ["Between Rear Principals", "2.4 m"]),
        _spec("building_separation", "building_separation", "building_separation", "Front and Rear Principal Buildings", ">=", "6", "m", "between front and rear principals", ["Between Front & Rear Principals", "6.0 m"]),
        _spec("building_separation", "building_separation", "building_separation", "All Other Buildings", ">=", "2.4", "m", "between all other buildings", ["Between All Other Buildings", "2.4 m"]),
    ]
    return [dict(spec) for spec in specs]


def _permitted_use_specs() -> list[dict[str, str | list[str]]]:
    return [
        _spec("permitted_use", "permitted_use", "district", "Small-Scale Multi-Unit Housing", "allowed", "", "", "", ["Principal Use", "Small-Scale Multi-Unit Housing"]),
        _spec("permitted_use", "permitted_use", "district", "Group Home", "allowed", "", "", "", ["Principal Use", "Group Home"]),
    ]


def _clause_specs() -> list[dict[str, str | list[str]]]:
    return [
        _spec("automatic_sprinkler", "automatic_sprinkler", "fire_safety", "dwelling units located more than 45 m from a street lot line", ">", "45", "m", "automatic sprinkler system required beyond this distance", ["more than 45 m", "automatic sprinkler system"]),
        _spec("fire_access_corridor", "fire_access_corridor", "corridor_width", "All dwelling units", ">=", "1", "m", "paved or gravel fire access corridor", ["minimum 1.0 m", "fire access corridor"]),
        _spec("fire_access_corridor", "fire_access_corridor", "vertical_clearance", "All dwelling units", ">=", "2.5", "m", "clear of projections or obstructions", ["minimum of 2.5 m", "clear of any projections"]),
        _spec("lot_coverage", "lot_coverage", "lot", "Community Heritage Register lots", "<=", "60", "%", "heritage exception", ["Community Heritage Register", "maximum lot coverage", "60%"]),
        _spec("impervious_surface", "impervious_surface", "lot", "Community Heritage Register lots", "<=", "70", "%", "heritage exception", ["Community Heritage Register", "impervious surface", "70%"]),
        _spec("setback", "setback", "street_yard", "Community Heritage Register lots", ">=", "2", "m", "heritage exception", ["Community Heritage Register", "street yards", "minimum of 2.0 m"]),
    ]


def _spec(
    rule_type: str,
    rule_object: str,
    constraint_scope: str,
    applies_to: str,
    operator: str,
    value: str,
    unit: str,
    condition: str,
    required_terms: list[str],
) -> dict[str, str | list[str]]:
    return {
        "label": f"{rule_type}:{applies_to}:{constraint_scope}:{value}{unit}:{condition}",
        "rule_type": rule_type,
        "rule_object": rule_object,
        "constraint_scope": constraint_scope,
        "applies_to": applies_to,
        "operator": operator,
        "value": value,
        "unit": unit,
        "condition": condition,
        "required_terms": required_terms,
        "value_quote": _value_quote(value, unit),
    }


def _unique_hits(retrieval_report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for hit in retrieval_report.get("evidence") or []:
        key = (str(hit.get("span_id") or ""), str(hit.get("quote") or "")[:160])
        if key in seen:
            continue
        seen.add(key)
        rows.append(hit)
    return rows


def _quote_has_terms(quote: str, terms: list[str]) -> bool:
    normalized = _normalize_for_terms(quote)
    return all(_normalize_for_terms(term) in normalized for term in terms)


def _normalize_for_terms(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower().replace("²", "2")).strip()


def _value_quote(value: str, unit: str) -> str:
    if not value and not unit:
        return ""
    if unit == "%":
        return f"{value}%"
    if unit == "m2":
        return f"{value} m 2"
    return f"{value} {unit}".strip()


def _candidate_key(
    rule_type: str,
    operator: str,
    value: str,
    unit: str,
    applies_to: str,
    condition: str,
    constraint_scope: str,
) -> tuple[str, str, str, str, str, str, str]:
    return (
        rule_type,
        operator,
        _normalize_value(value) if value else "",
        _normalize_unit(unit) if unit else "",
        re.sub(r"\s+", " ", applies_to.lower()).strip(),
        re.sub(r"\s+", " ", condition.lower()).strip(),
        re.sub(r"\s+", " ", constraint_scope.lower()).strip(),
    )


def _rule_defaults(query: str) -> dict[str, str]:
    query_norm = re.sub(r"\s+", " ", query.lower()).strip()
    return QUERY_RULE_MAP.get(query_norm, {})


def _first_measurement_hit(
    hits: list[dict[str, Any]],
    *,
    preferred_unit: str,
    query: str,
) -> tuple[dict[str, Any], re.Match[str]] | None:
    preferred_fallback: tuple[dict[str, Any], re.Match[str]] | None = None
    any_fallback: tuple[dict[str, Any], re.Match[str]] | None = None
    query_tokens = [token for token in re.findall(r"[a-z]+", query.lower()) if token not in {"maximum", "minimum"}]
    for hit in hits:
        quote = str(hit.get("quote") or "")
        for match in MEASUREMENT_RE.finditer(quote):
            normalized_unit = _normalize_unit(match.group("unit"))
            if _looks_like_split_square_metres(quote, match):
                normalized_unit = "m2"
            if preferred_unit and normalized_unit == preferred_unit and _window_mentions_query(quote, match, query_tokens):
                return hit, match
            if preferred_unit and normalized_unit == preferred_unit and preferred_fallback is None:
                preferred_fallback = (hit, match)
            if any_fallback is None:
                any_fallback = (hit, match)
    if preferred_fallback is not None:
        return preferred_fallback
    return any_fallback if not preferred_unit else None


def _normalize_value(value: str) -> str:
    return str(float(value)).rstrip("0").rstrip(".") if "." in value else value


def _normalize_unit(unit: str) -> str:
    text = re.sub(r"[.\s]+", " ", unit.lower()).strip()
    aliases = {
        "m²": "m2",
        "sq m": "m2",
        "square metres": "m2",
        "square meters": "m2",
        "per cent": "%",
        "percent": "%",
        "metre": "m",
        "metres": "m",
        "meter": "m",
        "meters": "m",
        "stories": "storeys",
        "story": "storeys",
        "storey": "storeys",
        "units": "units",
        "unit": "units",
    }
    return aliases.get(text, text)


def _measurement_unit(quote: str, match: re.Match[str]) -> str:
    if _looks_like_split_square_metres(quote, match):
        return "m2"
    return _normalize_unit(match.group("unit"))


def _measurement_quote(quote: str, match: re.Match[str]) -> str:
    text = match.group(0)
    if _looks_like_split_square_metres(quote, match):
        suffix = re.match(r"\s*2\b", quote[match.end() : match.end() + 4])
        if suffix:
            text = f"{text}{suffix.group(0)}"
    return text


def _looks_like_split_square_metres(quote: str, match: re.Match[str]) -> bool:
    unit = match.group("unit").lower().strip()
    if unit != "m":
        return False
    return bool(re.match(r"\s*2\b", quote[match.end() : match.end() + 4]))


def _window_mentions_query(quote: str, match: re.Match[str], query_tokens: list[str]) -> bool:
    if not query_tokens:
        return True
    start = max(0, match.start() - 120)
    end = min(len(quote), match.end() + 120)
    window = quote[start:end].lower()
    return any(token in window for token in query_tokens)


def _constraint_scope(query: str, quote: str) -> str:
    query_norm = re.sub(r"\s+", " ", query.lower()).strip()
    if query_norm in QUERY_RULE_MAP:
        return query_norm
    return quote[:80]


def _citation(hit: dict[str, Any], quote: str) -> dict[str, Any]:
    return {
        "evidence_id": hit.get("evidence_id"),
        "span_id": hit.get("span_id"),
        "page": hit.get("page"),
        "section_id": hit.get("section_id"),
        "quote": quote,
    }
