"""F1 benchmark evaluation.

This module measures F1 outputs against city gold artifacts. It is deliberately
separate from extraction and verification: benchmark scoring can identify gaps,
but it cannot promote or approve anything.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from burnaby_prototype.compliance import evaluate_cases, summarize_case_results

from .contracts import ARTIFACT_SCHEMA_VERSION
from .proof_rag import build_retrieval_report


def build_benchmark_eval_outputs(
    *,
    source_spans: list[dict[str, Any]],
    candidate_rules: list[dict[str, Any]],
    verified_rules: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
    gis_rule_contract: dict[str, Any],
    city_key: str,
    run_id: str,
    root: Path,
) -> dict[str, Any]:
    gold_rules_path = root / "benchmark" / "gold" / f"{city_key}_gold_rules.json"
    proposal_cases_path = root / "benchmark" / "gold" / f"{city_key}_proposal_cases.json"
    gold_rules = _read_list(gold_rules_path)
    proposal_cases = _read_list(proposal_cases_path)
    return evaluate_benchmark_outputs(
        source_spans=source_spans,
        gold_rules=gold_rules,
        proposal_cases=proposal_cases,
        candidate_rules=candidate_rules,
        verified_rules=verified_rules,
        review_queue=review_queue,
        gis_rule_contract=gis_rule_contract,
        city_key=city_key,
        run_id=run_id,
        gold_rules_path=gold_rules_path if gold_rules_path.exists() else None,
        proposal_cases_path=proposal_cases_path if proposal_cases_path.exists() else None,
    )


def evaluate_benchmark_outputs(
    *,
    source_spans: list[dict[str, Any]],
    gold_rules: list[dict[str, Any]],
    proposal_cases: list[dict[str, Any]],
    candidate_rules: list[dict[str, Any]],
    verified_rules: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
    gis_rule_contract: dict[str, Any],
    city_key: str,
    run_id: str,
    gold_rules_path: Path | None = None,
    proposal_cases_path: Path | None = None,
) -> dict[str, Any]:
    retrieval_benchmark = _retrieval_benchmark(source_spans, gold_rules, city_key, run_id)
    candidate_matches = _match_gold_rules(gold_rules, candidate_rules)
    verified_matches = _match_gold_rules(gold_rules, verified_rules)
    false_verified = [
        str(rule.get("rule_id") or "")
        for rule in verified_rules
        if not _best_gold_match(rule, gold_rules)
    ]
    support_failures = _verified_source_support_failures(verified_rules)
    gis_metrics = _gis_contract_metrics(gis_rule_contract, verified_rules, review_queue)
    review_candidates = [_review_candidate(item) for item in review_queue]
    proposal_results = evaluate_cases(proposal_cases, verified_rules, review_candidates)
    proposal_metrics = summarize_case_results(proposal_results)

    gold_count = len(gold_rules)
    rule_metrics = {
        "gold_rule_count": gold_count,
        "candidate_rule_count": len(candidate_rules),
        "verified_rule_count": len(verified_rules),
        "review_rule_count": len(review_queue),
        "candidate_recall": _ratio(len({row["gold_id"] for row in candidate_matches}), gold_count),
        "verified_recall": _ratio(len({row["gold_id"] for row in verified_matches}), gold_count),
        "verified_precision": _ratio(len(verified_rules) - len(false_verified), len(verified_rules)),
        "false_verified_count": len(false_verified),
        "false_verified_rule_ids": false_verified,
        "verified_source_support_failed_count": len(support_failures),
        "verified_source_support_failures": support_failures,
        "matched_candidates": candidate_matches,
        "matched_verified": verified_matches,
        "missed_candidate_gold_rule_ids": _missing_gold_ids(gold_rules, candidate_matches),
        "missed_verified_gold_rule_ids": _missing_gold_ids(gold_rules, verified_matches),
    }
    quality_gates = _quality_gates(
        retrieval_metrics=retrieval_benchmark["metrics"],
        rule_metrics=rule_metrics,
        gis_metrics=gis_metrics,
        proposal_metrics=proposal_metrics,
    )
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "f1_benchmark_report.json",
        "city_key": city_key,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gold_rules_path": str(gold_rules_path) if gold_rules_path else None,
        "proposal_cases_path": str(proposal_cases_path) if proposal_cases_path else None,
        "retrieval_benchmark": retrieval_benchmark,
        "rule_metrics": rule_metrics,
        "gis_contract_metrics": gis_metrics,
        "proposal_metrics": proposal_metrics,
        "proposal_results": proposal_results,
        "quality_gates": quality_gates,
        "safety": {
            "benchmark_promotes_rules": False,
            "benchmark_approves_proposals": False,
            "false_verified_count": rule_metrics["false_verified_count"],
            "false_approval_count": proposal_metrics["false_approval_count"],
        },
    }


def write_benchmark_eval_outputs(payload: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "f1_benchmark_report.json"
    md_path = output_dir / "f1_benchmark_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return {"f1_benchmark_report": json_path, "f1_benchmark_report_md": md_path}


def _retrieval_benchmark(
    source_spans: list[dict[str, Any]],
    gold_rules: list[dict[str, Any]],
    city_key: str,
    run_id: str,
) -> dict[str, Any]:
    queries = [_gold_query(gold) for gold in gold_rules]
    report = build_retrieval_report(
        source_spans=source_spans,
        city_key=city_key,
        run_id=f"{run_id}_benchmark_retrieval",
        queries=queries,
        top_k=6,
    )
    rows = []
    for gold, query_row in zip(gold_rules, report.get("queries") or [], strict=False):
        required_terms = _required_terms(gold, "required_evidence_terms")
        matched_hit = None
        for hit in query_row.get("hits") or []:
            if _contains_terms(str(hit.get("quote") or ""), required_terms):
                matched_hit = hit
                break
        rows.append(
            {
                "gold_id": gold.get("gold_id"),
                "query": query_row.get("query"),
                "matched": matched_hit is not None,
                "matched_evidence_id": matched_hit.get("evidence_id") if matched_hit else None,
                "matched_span_id": matched_hit.get("span_id") if matched_hit else None,
                "required_evidence_terms": required_terms,
                "hit_count": query_row.get("hit_count", 0),
            }
        )
    matched = sum(1 for row in rows if row["matched"])
    return {
        "method": "gold_term_queries_at_6",
        "top_k": 6,
        "metrics": {
            "gold_rule_count": len(gold_rules),
            "retrieved_gold_rule_count": matched,
            "retrieval_recall_at_6": _ratio(matched, len(gold_rules)),
        },
        "gold_results": rows,
    }


def _quality_gates(
    *,
    retrieval_metrics: dict[str, Any],
    rule_metrics: dict[str, Any],
    gis_metrics: dict[str, Any],
    proposal_metrics: dict[str, Any],
) -> dict[str, Any]:
    gates = {
        "verified_precision_is_1": rule_metrics["verified_precision"] == 1.0,
        "false_verified_is_0": rule_metrics["false_verified_count"] == 0,
        "false_approval_is_0": proposal_metrics["false_approval_count"] == 0,
        "retrieval_recall_at_6_ge_0_95": retrieval_metrics["retrieval_recall_at_6"] >= 0.95,
        "candidate_recall_ge_0_90": rule_metrics["candidate_recall"] >= 0.90,
        "verified_source_support_complete": rule_metrics["verified_source_support_failed_count"] == 0,
        "gis_verified_only": gis_metrics["verified_only"] is True and gis_metrics["review_rule_leak_count"] == 0,
    }
    if proposal_metrics.get("proposal_case_count", 0) > 0:
        gates["proposal_decision_accuracy_is_1"] = proposal_metrics.get("proposal_decision_accuracy") == 1.0
        gates["proposal_case_accuracy_is_1"] = proposal_metrics.get("proposal_case_accuracy") == 1.0
    return {
        "gates": gates,
        "passed": all(gates.values()),
        "failed_gates": [name for name, passed in gates.items() if not passed],
    }


def _match_gold_rules(gold_rules: list[dict[str, Any]], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches = []
    for gold in gold_rules:
        match = _best_rule_match(gold, rules)
        if match:
            matches.append(
                {
                    "gold_id": gold.get("gold_id"),
                    "rule_id": match.get("rule_id"),
                    "score": _score_match(gold, match),
                }
            )
    return matches


def _best_gold_match(rule: dict[str, Any], gold_rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    return _best_rule_match(rule, gold_rules, reverse=True)


def _best_rule_match(
    gold: dict[str, Any],
    rules: list[dict[str, Any]],
    *,
    reverse: bool = False,
) -> dict[str, Any] | None:
    scored = []
    for rule in rules:
        score = _score_match(rule, gold) if reverse else _score_match(gold, rule)
        if score >= 7:
            scored.append((score, rule))
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], str(item[1].get("rule_id") or item[1].get("gold_id") or "")))
    return scored[0][1]


def _score_match(gold: dict[str, Any], rule: dict[str, Any]) -> int:
    if _norm_object(gold.get("rule_object")) != _norm_object(rule.get("rule_object")):
        return 0
    score = 4
    gold_value = gold.get("value")
    if gold_value is not None:
        if not _value_equal(gold_value, rule.get("value")):
            return 0
        score += 2
    gold_unit = gold.get("unit")
    if gold_unit:
        if _norm_unit(gold_unit) != _norm_unit(rule.get("unit")):
            return 0
        score += 1
    gold_operator = gold.get("operator")
    if gold_operator and _norm_operator(gold_operator) != _norm_operator(rule.get("operator")):
        return 0
    if gold_operator:
        score += 1
    required_terms = _required_terms(gold, "required_rule_terms")
    if required_terms:
        text = _rule_text(rule)
        if not _contains_terms(text, required_terms, minimum=max(1, len(required_terms) // 2)):
            return 0
        score += min(3, len(required_terms))
    return score


def _verified_source_support_failures(verified_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures = []
    required_fields = ("rule_object", "operator", "value", "unit", "constraint_scope", "applies_to")
    for rule in verified_rules:
        raw = rule.get("raw") if isinstance(rule.get("raw"), dict) else {}
        citations = raw.get("field_citations") if isinstance(raw.get("field_citations"), dict) else {}
        missing = []
        for field in required_fields:
            if not str(rule.get(field) or "").strip():
                continue
            citation = citations.get(field) if isinstance(citations.get(field), dict) else {}
            if not citation.get("evidence_id") or not citation.get("span_id") or not citation.get("quote"):
                missing.append(field)
        if not rule.get("evidence_ids"):
            missing.append("evidence_ids")
        if missing:
            failures.append({"rule_id": rule.get("rule_id"), "missing_support_fields": sorted(set(missing))})
    return failures


def _gis_contract_metrics(
    gis_rule_contract: dict[str, Any],
    verified_rules: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
) -> dict[str, Any]:
    contract_rules = gis_rule_contract.get("rules") or []
    review_ids = {str(item.get("rule_id") or "") for item in review_queue}
    leaked = [str(rule.get("rule_id") or "") for rule in contract_rules if str(rule.get("rule_id") or "") in review_ids]
    citation_missing = [
        str(rule.get("rule_id") or "")
        for rule in contract_rules
        if not ((rule.get("citation") or {}).get("evidence_id") and (rule.get("citation") or {}).get("quote"))
    ]
    return {
        "verified_only": gis_rule_contract.get("verified_only") is True,
        "verified_rule_count": len(verified_rules),
        "export_rule_count": len(contract_rules),
        "export_matches_verified_count": len(contract_rules) == len(verified_rules),
        "review_rule_leak_count": len(leaked),
        "review_rule_leak_ids": leaked,
        "citation_missing_count": len(citation_missing),
        "citation_missing_rule_ids": citation_missing,
    }


def _review_candidate(review_item: dict[str, Any]) -> dict[str, Any]:
    candidate = review_item.get("candidate") if isinstance(review_item.get("candidate"), dict) else {}
    if not candidate:
        return review_item
    merged = dict(candidate)
    merged.setdefault("rule_id", review_item.get("rule_id"))
    merged.setdefault("status", review_item.get("status"))
    return merged


def _missing_gold_ids(gold_rules: list[dict[str, Any]], matches: list[dict[str, Any]]) -> list[str]:
    matched = {str(match.get("gold_id") or "") for match in matches}
    return [str(gold.get("gold_id") or "") for gold in gold_rules if str(gold.get("gold_id") or "") not in matched]


def _gold_query(gold: dict[str, Any]) -> str:
    parts = []
    parts.extend(_required_terms(gold, "required_evidence_terms"))
    parts.extend(str(item) for item in (gold.get("rule_object"), gold.get("value"), gold.get("unit")) if item is not None)
    return " ".join(dict.fromkeys(part for part in parts if part))


def _required_terms(gold: dict[str, Any], field: str) -> list[str]:
    terms = gold.get(field) or []
    if not isinstance(terms, list):
        return []
    return [str(term).lower().strip() for term in terms if str(term).strip()]


def _contains_terms(text: str, terms: list[str], *, minimum: int | None = None) -> bool:
    if not terms:
        return True
    normalized = _norm_text(text)
    matched = 0
    for term in terms:
        term_tokens = _tokens(term)
        if term_tokens and all(token in normalized for token in term_tokens):
            matched += 1
    return matched >= (len(terms) if minimum is None else minimum)


def _rule_text(rule: dict[str, Any]) -> str:
    raw = rule.get("raw") if isinstance(rule.get("raw"), dict) else {}
    citations = raw.get("field_citations") if isinstance(raw.get("field_citations"), dict) else {}
    quotes = " ".join(str(item.get("quote") or "") for item in citations.values() if isinstance(item, dict))
    return " ".join(
        str(item or "")
        for item in (
            rule.get("rule_object"),
            rule.get("constraint_scope"),
            rule.get("applies_to"),
            rule.get("condition"),
            rule.get("exception"),
            quotes,
        )
    )


def _value_equal(left: Any, right: Any) -> bool:
    try:
        return abs(float(left) - float(right)) <= 0.01
    except (TypeError, ValueError):
        return str(left).strip().lower() == str(right).strip().lower()


def _norm_object(value: Any) -> str:
    text = str(value or "").lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "building_height": "height",
        "permitted_dwelling_units": "dwelling_units",
        "impervious_surfaces": "impervious_surface",
    }
    return aliases.get(text, text)


def _norm_unit(value: Any) -> str:
    text = re.sub(r"[.\s]+", " ", str(value or "").lower()).strip()
    return {
        "metre": "m",
        "metres": "m",
        "meter": "m",
        "meters": "m",
        "m²": "m2",
        "sq m": "m2",
        "square metres": "m2",
        "square meters": "m2",
        "units": "units",
        "unit": "units",
        "percent": "%",
        "per cent": "%",
    }.get(text, text)


def _norm_operator(value: Any) -> str:
    text = str(value or "").lower().strip()
    return {
        "maximum": "<=",
        "max": "<=",
        "minimum": ">=",
        "min": ">=",
        "allowed": "allowed",
    }.get(text, text)


def _norm_text(text: str) -> set[str]:
    return set(_tokens(text))


def _tokens(text: Any) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", str(text or "").lower())


def _ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator <= 0 else round(numerator / denominator, 4)


def _read_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _render_markdown(payload: dict[str, Any]) -> str:
    retrieval = payload["retrieval_benchmark"]["metrics"]
    rules = payload["rule_metrics"]
    gis = payload["gis_contract_metrics"]
    proposal = payload["proposal_metrics"]
    gates = payload["quality_gates"]
    failed = ", ".join(f"`{gate}`" for gate in gates["failed_gates"]) or "none"
    return f"""# F1 Benchmark Report

City: `{payload.get("city_key")}`

Run: `{payload.get("run_id")}`

## Release Gates

Overall passed: `{str(gates.get("passed")).lower()}`

Failed gates: {failed}

| Gate | Passed |
|---|---:|
{_gate_rows(gates.get("gates") or {})}

## Metrics

| Metric | Value |
|---|---:|
| Gold rules | `{rules["gold_rule_count"]}` |
| Retrieval recall at 6 | `{retrieval["retrieval_recall_at_6"]}` |
| Candidate recall | `{rules["candidate_recall"]}` |
| Verified precision | `{rules["verified_precision"]}` |
| Verified recall | `{rules["verified_recall"]}` |
| False verified | `{rules["false_verified_count"]}` |
| Verified source-support failures | `{rules["verified_source_support_failed_count"]}` |
| GIS verified-only | `{str(gis["verified_only"]).lower()}` |
| GIS review leaks | `{gis["review_rule_leak_count"]}` |
| Proposal cases | `{proposal["proposal_case_count"]}` |
| Proposal decision accuracy | `{proposal["proposal_decision_accuracy"]}` |
| Proposal case accuracy | `{proposal["proposal_case_accuracy"]}` |
| False approvals | `{proposal["false_approval_count"]}` |

The benchmark does not promote rules or approve proposals. Failed gates are
upgrade targets, not permission to weaken verification.
"""


def _gate_rows(gates: dict[str, bool]) -> str:
    return "\n".join(f"| `{name}` | `{str(passed).lower()}` |" for name, passed in gates.items())
