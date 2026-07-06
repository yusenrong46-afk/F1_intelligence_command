"""F1 multi-city checkpoint runner."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import ARTIFACT_SCHEMA_VERSION
from .document_intelligence import build_document_intelligence, write_document_intelligence
from .gis_compliance import build_gis_compliance_outputs, write_gis_compliance_outputs
from .proof_rag import build_retrieval_report, write_retrieval_report
from .repair_review import build_guarded_repair_rerun_outputs, write_repair_review_outputs
from .source_registry import build_source_registry, write_source_registry
from .structured_extraction import build_candidate_rules_from_retrieval, write_candidate_rules
from .verification import build_verification_outputs, write_verification_outputs


DEFAULT_MULTI_CITY_KEYS = ("burnaby_r1", "vancouver_rs", "calgary_rcg", "surrey_r3")


def run_multi_city_checkpoint(
    *,
    root: Path,
    output_root: Path,
    run_id: str,
    city_keys: list[str],
    prefer_docling: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    city_results = []
    for city_key in city_keys:
        city_results.append(
            _run_city(
                root=root,
                output_root=output_root,
                city_key=city_key,
                run_id=run_id,
                prefer_docling=prefer_docling,
            )
        )
    aggregate = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "f1_multi_city_report.json",
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prefer_docling": prefer_docling,
        "city_count": len(city_results),
        "completed_city_count": sum(1 for result in city_results if result.get("status") == "completed"),
        "failed_city_count": sum(1 for result in city_results if result.get("status") == "failed"),
        "release_safe_city_count": sum(1 for result in city_results if result.get("release_label") == "benchmark_with_proposals"),
        "exploratory_city_count": sum(1 for result in city_results if result.get("release_label") != "benchmark_with_proposals"),
        "false_verified_total": sum(int(result.get("false_verified_count") or 0) for result in city_results),
        "false_approval_total": sum(int(result.get("false_approval_count") or 0) for result in city_results),
        "runtime_seconds": round(time.perf_counter() - started, 3),
        "cities": city_results,
    }
    return aggregate


def write_multi_city_report(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "f1_multi_city_report.json"
    md_path = output_dir / "f1_multi_city_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    return {"f1_multi_city_report": json_path, "f1_multi_city_report_md": md_path}


def _run_city(
    *,
    root: Path,
    output_root: Path,
    city_key: str,
    run_id: str,
    prefer_docling: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    out_dir = output_root / city_key / run_id
    try:
        source_registry = build_source_registry(city_key=city_key, run_id=run_id, root=root)
        document_intelligence = build_document_intelligence(
            source_registry=source_registry,
            run_id=run_id,
            root=root,
            prefer_docling=prefer_docling,
        )
        retrieval_report = build_retrieval_report(
            source_spans=document_intelligence["source_spans"],
            city_key=city_key,
            run_id=run_id,
        )
        extraction_payload = build_candidate_rules_from_retrieval(
            retrieval_report=retrieval_report,
            city_key=city_key,
            run_id=run_id,
        )
        verification_payload = build_verification_outputs(
            candidate_rules=extraction_payload["candidate_rules"],
            city_key=city_key,
            run_id=run_id,
        )
        repair_payload = build_guarded_repair_rerun_outputs(
            review_queue=verification_payload["review_queue"],
            retrieval_report=retrieval_report,
            city_key=city_key,
            run_id=run_id,
            rule_contract_families=_rule_contract_families(root, city_key),
            preverified_rules=verification_payload["verified_rules"],
            preverified_decisions=_promoted_decisions(verification_payload),
            initial_candidate_count=len(extraction_payload["candidate_rules"]),
        )
        gis_payload = build_gis_compliance_outputs(
            verified_rules=repair_payload["verified_rules"],
            review_queue=repair_payload["review_queue"],
            city_key=city_key,
            run_id=run_id,
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        write_source_registry(source_registry, out_dir)
        write_document_intelligence(document_intelligence, out_dir)
        write_retrieval_report(retrieval_report, out_dir)
        write_candidate_rules(extraction_payload, out_dir)
        write_verification_outputs(repair_payload, out_dir)
        write_repair_review_outputs(repair_payload, out_dir)
        write_gis_compliance_outputs(gis_payload, out_dir)
        summary = _city_summary(
            root=root,
            out_dir=out_dir,
            city_key=city_key,
            run_id=run_id,
            source_registry=source_registry,
            document_intelligence=document_intelligence,
            retrieval_report=retrieval_report,
            extraction_payload=extraction_payload,
            repair_payload=repair_payload,
            gis_payload=gis_payload,
            runtime_seconds=round(time.perf_counter() - started, 3),
        )
        (out_dir / "f1_city_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return summary
    except Exception as exc:
        out_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "artifact": "f1_city_summary.json",
            "city_key": city_key,
            "run_id": run_id,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "runtime_seconds": round(time.perf_counter() - started, 3),
            "release_label": _release_label(root, city_key),
            "gold_rule_count": _json_count(root / "benchmark" / "gold" / f"{city_key}_gold_rules.json"),
            "proposal_case_count": _json_count(root / "benchmark" / "gold" / f"{city_key}_proposal_cases.json"),
        }
        (out_dir / "f1_city_summary.json").write_text(
            json.dumps(failure, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return failure


def _city_summary(
    *,
    root: Path,
    out_dir: Path,
    city_key: str,
    run_id: str,
    source_registry: dict[str, Any],
    document_intelligence: dict[str, Any],
    retrieval_report: dict[str, Any],
    extraction_payload: dict[str, Any],
    repair_payload: dict[str, Any],
    gis_payload: dict[str, Any],
    runtime_seconds: float,
) -> dict[str, Any]:
    doc_summary = document_intelligence.get("summary") or {}
    retrieval_summary = retrieval_report.get("summary") or {}
    extraction_report = extraction_payload.get("extraction_report") or {}
    verification_report = repair_payload.get("verification_report") or {}
    repair_report = repair_payload.get("repair_rerun_report") or {}
    gis_contract = gis_payload.get("gis_rule_contract") or {}
    compliance_report = gis_payload.get("compliance_report") or {}
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "f1_city_summary.json",
        "city_key": city_key,
        "run_id": run_id,
        "status": "completed",
        "output_dir": _display_path(out_dir, root),
        "release_label": _release_label(root, city_key),
        "gold_rule_count": _json_count(root / "benchmark" / "gold" / f"{city_key}_gold_rules.json"),
        "proposal_case_count": _json_count(root / "benchmark" / "gold" / f"{city_key}_proposal_cases.json"),
        "source_registry_status": (source_registry.get("validation") or {}).get("status"),
        "ingest_backend": document_intelligence.get("ingest_backend"),
        "page_count": doc_summary.get("page_count", 0),
        "source_span_count": doc_summary.get("source_span_count", 0),
        "retrieval_queries_with_hits": retrieval_summary.get("queries_with_hits", 0),
        "retrieval_query_count": retrieval_summary.get("query_count", 0),
        "candidate_count": extraction_report.get("candidate_count", 0),
        "verified_count": verification_report.get("verified_count", 0),
        "review_queue_count": verification_report.get("review_queue_count", 0),
        "status_counts": verification_report.get("status_counts") or {},
        "guarded_repair_promotion_count": repair_report.get("guarded_repair_promotion_count", 0),
        "gis_export_rule_count": gis_contract.get("export_rule_count", 0),
        "false_verified_count": verification_report.get("false_verified_count", 0),
        "false_approval_count": compliance_report.get("false_approval_count", 0),
        "runtime_seconds": runtime_seconds,
    }


def _release_label(root: Path, city_key: str) -> str:
    has_gold = (root / "benchmark" / "gold" / f"{city_key}_gold_rules.json").exists()
    has_proposals = (root / "benchmark" / "gold" / f"{city_key}_proposal_cases.json").exists()
    if has_gold and has_proposals:
        return "benchmark_with_proposals"
    if has_gold:
        return "partial_benchmark_no_proposals"
    return "exploratory_no_gold"


def _json_count(path: Path) -> int:
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    return len(data) if isinstance(data, list) else 0


def _rule_contract_families(root: Path, city_key: str) -> set[str] | None:
    path = root / "configs" / f"{city_key}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    verification = data.get("verification") if isinstance(data.get("verification"), dict) else {}
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


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _render_markdown(report: dict[str, Any]) -> str:
    rows = []
    for city in report.get("cities") or []:
        rows.append(
            "| {city} | {status} | {label} | {pages} | {candidates} | {verified} | {review} | {gis} | {fv} | {fa} | {runtime} |".format(
                city=city.get("city_key"),
                status=city.get("status"),
                label=city.get("release_label"),
                pages=city.get("page_count", ""),
                candidates=city.get("candidate_count", ""),
                verified=city.get("verified_count", ""),
                review=city.get("review_queue_count", ""),
                gis=city.get("gis_export_rule_count", ""),
                fv=city.get("false_verified_count", ""),
                fa=city.get("false_approval_count", ""),
                runtime=city.get("runtime_seconds", ""),
            )
        )
    table = "\n".join(rows)
    return f"""# F1 Multi-City Report

Run: `{report.get("run_id")}`

Parser mode: `{"docling-preferred" if report.get("prefer_docling") else "fallback"}`

| City | Status | Release label | Pages | Candidates | Verified | Review | GIS rules | False verified | False approvals | Runtime s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
{table}

## Totals

- Completed cities: `{report.get("completed_city_count")}`
- Failed cities: `{report.get("failed_city_count")}`
- Release-safe benchmark cities: `{report.get("release_safe_city_count")}`
- Exploratory or partial cities: `{report.get("exploratory_city_count")}`
- False verified total: `{report.get("false_verified_total")}`
- False approval total: `{report.get("false_approval_total")}`
- Runtime seconds: `{report.get("runtime_seconds")}`

Cities without both gold rules and proposal cases are exploratory or partial, not release-safe.
"""
