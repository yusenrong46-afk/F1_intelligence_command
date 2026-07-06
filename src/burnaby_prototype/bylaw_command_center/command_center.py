"""F1 command-center preview artifact."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import ARTIFACT_SCHEMA_VERSION


def build_command_center_outputs(
    *,
    summary: dict[str, Any],
    gis_rule_contract: dict[str, Any],
    compliance_report: dict[str, Any],
    chatbot_eval: dict[str, Any],
    review_queue: list[dict[str, Any]],
    city_key: str,
    run_id: str,
) -> dict[str, Any]:
    cards = _cards(summary, gis_rule_contract, compliance_report, chatbot_eval)
    manifest = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "command_center_manifest.json",
        "city_key": city_key,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cards": cards,
        "verified_rules": gis_rule_contract.get("rules") or [],
        "review_queue": review_queue,
        "compliance_status_counts": compliance_report.get("status_counts") or {},
        "chatbot_metrics": chatbot_eval.get("metrics") or {},
        "source_artifacts": {
            "summary": "f1_summary.json",
            "gis_rule_contract": "gis_rule_contract.json",
            "compliance_report": "compliance_report.json",
            "chatbot_eval": "chatbot_eval.json",
        },
    }
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "command_center_outputs",
        "city_key": city_key,
        "run_id": run_id,
        "generated_at": manifest["generated_at"],
        "command_center_manifest": manifest,
        "command_center_html": _render_html(manifest),
    }


def write_command_center_outputs(payload: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "command_center_manifest.json"
    html_path = output_dir / "command_center_preview.html"
    manifest_path.write_text(
        json.dumps(payload["command_center_manifest"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    html_path.write_text(payload["command_center_html"], encoding="utf-8")
    return {"command_center_manifest": manifest_path, "command_center_preview": html_path}


def build_command_center_app_outputs(
    *,
    summary: dict[str, Any],
    gis_rule_contract: dict[str, Any],
    compliance_report: dict[str, Any],
    compliance_decisions: list[dict[str, Any]],
    chatbot_eval: dict[str, Any],
    review_queue: list[dict[str, Any]],
    benchmark_eval: dict[str, Any],
    city_key: str,
    run_id: str,
    app_version: str = "checkpoint_15",
    operation_artifacts: dict[str, str] | None = None,
    operation_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the first product-grade F1 command-center artifact.

    The app is still static HTML, but it behaves like the product surface: it
    has searchable verified rules, review triage, evidence inspection,
    benchmark/safety readouts, and a single-rule compliance sandbox. All actions
    are read-only over F1 artifacts.
    """
    verified_rules = [_app_rule(rule) for rule in gis_rule_contract.get("rules") or []]
    review_items = [_app_review_item(item) for item in review_queue]
    decisions = [_app_compliance_decision(item) for item in compliance_decisions]
    benchmark_metrics = _benchmark_metrics(benchmark_eval)
    app_cards = _app_cards(
        summary=summary,
        verified_rules=verified_rules,
        review_items=review_items,
        compliance_report=compliance_report,
        chatbot_eval=chatbot_eval,
        benchmark_metrics=benchmark_metrics,
    )
    manifest = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "command_center_app_manifest.json",
        "city_key": city_key,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": "F1 Bylaw Intelligence Command Center",
        "app_version": app_version,
        "cards": app_cards,
        "verified_rules": verified_rules,
        "review_queue": review_items,
        "compliance_decisions": decisions,
        "compliance_status_counts": compliance_report.get("status_counts") or {},
        "chatbot_metrics": chatbot_eval.get("metrics") or {},
        "benchmark_metrics": benchmark_metrics,
        "workflow_health": {
            "quality_gates_passed": bool((benchmark_eval.get("quality_gates") or {}).get("passed")),
            "false_verified_count": benchmark_metrics.get("false_verified_count", 0),
            "false_approval_count": benchmark_metrics.get("false_approval_count", 0),
            "review_queue_count": len(review_items),
            "verified_rule_count": len(verified_rules),
        },
        "product_workflows": [
            {"id": "rule_explorer", "label": "Rule Explorer", "status": "available"},
            {"id": "review_workbench", "label": "Review Workbench", "status": "available"},
            {"id": "evidence_inspector", "label": "Evidence Inspector", "status": "available"},
            {"id": "single_rule_compliance", "label": "Single-Rule Compliance Sandbox", "status": "available"},
            {"id": "chatbot_safety", "label": "Chatbot Safety Monitor", "status": "available"},
        ],
        "source_artifacts": {
            "summary": "f1_summary.json",
            "gis_rule_contract": "gis_rule_contract.json",
            "review_queue": "review_queue.json",
            "compliance_decisions": "compliance_decisions.json",
            "compliance_report": "compliance_report.json",
            "chatbot_eval": "chatbot_eval.json",
            "benchmark_eval": "f1_benchmark_report.json",
        },
    }
    if operation_artifacts:
        manifest["operation_artifacts"] = operation_artifacts
        manifest["operation_metrics"] = operation_metrics or {}
        manifest["product_workflows"].extend(
            [
                {"id": "review_action_drafting", "label": "Review Action Drafting", "status": "available"},
                {"id": "scenario_builder", "label": "Compliance Scenario Builder", "status": "available"},
                {"id": "evidence_navigation", "label": "Evidence Navigation", "status": "available"},
            ]
        )
        manifest["source_artifacts"].update(operation_artifacts)
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "command_center_app_outputs",
        "city_key": city_key,
        "run_id": run_id,
        "generated_at": manifest["generated_at"],
        "command_center_app_manifest": manifest,
        "command_center_app_html": _render_app_html(manifest),
    }


def write_command_center_app_outputs(payload: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "command_center_app_manifest.json"
    html_path = output_dir / "command_center_app.html"
    manifest_path.write_text(
        json.dumps(payload["command_center_app_manifest"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    html_path.write_text(payload["command_center_app_html"], encoding="utf-8")
    return {"command_center_app_manifest": manifest_path, "command_center_app": html_path}


def _cards(
    summary: dict[str, Any],
    gis_rule_contract: dict[str, Any],
    compliance_report: dict[str, Any],
    chatbot_eval: dict[str, Any],
) -> list[dict[str, Any]]:
    verification = summary.get("verification") or {}
    repair = summary.get("repair_review") or {}
    retrieval = summary.get("retrieval") or {}
    chatbot_metrics = chatbot_eval.get("metrics") or {}
    return [
        {"label": "Verified Rules", "value": verification.get("verified_count", 0), "tone": "good"},
        {"label": "Review Queue", "value": verification.get("review_queue_count", 0), "tone": "warn"},
        {"label": "Guarded Repairs", "value": repair.get("guarded_repair_promotion_count", 0), "tone": "good"},
        {"label": "GIS Rules", "value": gis_rule_contract.get("export_rule_count", 0), "tone": "good"},
        {"label": "RAG Hits", "value": retrieval.get("total_hit_count", 0), "tone": "neutral"},
        {"label": "Chat Approval Claims", "value": chatbot_metrics.get("approval_claim_count", 0), "tone": "good"},
        {"label": "False Verified", "value": summary.get("safety", {}).get("f1_false_verified_count", 0), "tone": "good"},
        {"label": "False Approvals", "value": compliance_report.get("false_approval_count", 0), "tone": "good"},
    ]


def _app_cards(
    *,
    summary: dict[str, Any],
    verified_rules: list[dict[str, Any]],
    review_items: list[dict[str, Any]],
    compliance_report: dict[str, Any],
    chatbot_eval: dict[str, Any],
    benchmark_metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    verification = summary.get("verification") or {}
    chatbot_metrics = chatbot_eval.get("metrics") or {}
    return [
        {"label": "Verified Rules", "value": len(verified_rules), "tone": "good"},
        {"label": "Review Queue", "value": len(review_items), "tone": "warn"},
        {"label": "Verified Recall", "value": _pct(benchmark_metrics.get("verified_recall")), "tone": "neutral"},
        {"label": "Retrieval Recall", "value": _pct(benchmark_metrics.get("retrieval_recall_at_6")), "tone": "good"},
        {"label": "Proposal Accuracy", "value": _pct(benchmark_metrics.get("proposal_case_accuracy")), "tone": "good"},
        {"label": "False Verified", "value": benchmark_metrics.get("false_verified_count", 0), "tone": "good"},
        {"label": "False Approvals", "value": compliance_report.get("false_approval_count", 0), "tone": "good"},
        {
            "label": "Chat Safety",
            "value": f"{chatbot_metrics.get('approval_claim_count', 0)} claims",
            "tone": "good" if not chatbot_metrics.get("approval_claim_count", 0) else "warn",
        },
        {
            "label": "Verifier Output",
            "value": verification.get("verified_count", len(verified_rules)),
            "tone": "neutral",
        },
    ]


def _app_rule(rule: dict[str, Any]) -> dict[str, Any]:
    citation = rule.get("citation") if isinstance(rule.get("citation"), dict) else {}
    evidence_ids = [str(item) for item in rule.get("evidence_ids") or [] if item]
    if citation.get("evidence_id") and citation["evidence_id"] not in evidence_ids:
        evidence_ids.insert(0, str(citation["evidence_id"]))
    return {
        "rule_id": str(rule.get("rule_id") or ""),
        "rule_object": str(rule.get("rule_object") or ""),
        "applies_to": str(rule.get("applies_to") or ""),
        "constraint_scope": str(rule.get("constraint_scope") or ""),
        "operator": str(rule.get("operator") or ""),
        "value": str(rule.get("value") or ""),
        "unit": str(rule.get("unit") or ""),
        "condition": str(rule.get("condition") or ""),
        "exception": str(rule.get("exception") or ""),
        "geometry_target": str(rule.get("geometry_target") or ""),
        "verification_status": str(rule.get("verification_status") or rule.get("status") or "verified"),
        "evidence_ids": evidence_ids,
        "citation": _compact_citation(citation),
        "search_text": _search_text(
            rule.get("rule_id"),
            rule.get("rule_object"),
            rule.get("applies_to"),
            rule.get("constraint_scope"),
            rule.get("condition"),
            rule.get("exception"),
            evidence_ids,
            citation.get("quote"),
        ),
    }


def _app_review_item(item: dict[str, Any]) -> dict[str, Any]:
    candidate = item.get("candidate") if isinstance(item.get("candidate"), dict) else {}
    field_citations = candidate.get("raw", {}).get("field_citations") if isinstance(candidate.get("raw"), dict) else {}
    evidence = _review_evidence(candidate, field_citations if isinstance(field_citations, dict) else {})
    return {
        "rule_id": str(item.get("rule_id") or candidate.get("rule_id") or ""),
        "status": str(item.get("status") or candidate.get("status") or "review_needed"),
        "support_gaps": [str(gap) for gap in item.get("support_gaps") or []],
        "unresolved_dependencies": [str(dep) for dep in item.get("unresolved_dependencies") or []],
        "rule_object": str(candidate.get("rule_object") or ""),
        "applies_to": str(candidate.get("applies_to") or ""),
        "constraint_scope": str(candidate.get("constraint_scope") or ""),
        "operator": str(candidate.get("operator") or ""),
        "value": str(candidate.get("value") or ""),
        "unit": str(candidate.get("unit") or ""),
        "condition": str(candidate.get("condition") or ""),
        "exception": str(candidate.get("exception") or ""),
        "evidence": evidence,
        "search_text": _search_text(
            item.get("rule_id"),
            item.get("status"),
            item.get("support_gaps"),
            candidate.get("rule_object"),
            candidate.get("applies_to"),
            candidate.get("constraint_scope"),
            candidate.get("value"),
            candidate.get("unit"),
            evidence,
        ),
    }


def _app_compliance_decision(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario_id": str(item.get("scenario_id") or ""),
        "status": str(item.get("status") or ""),
        "reason": str(item.get("reason") or ""),
        "verified_rule_ids": [str(rule_id) for rule_id in item.get("verified_rule_ids") or []],
        "review_rule_ids": [str(rule_id) for rule_id in item.get("review_rule_ids") or []],
    }


def _benchmark_metrics(benchmark_eval: dict[str, Any]) -> dict[str, Any]:
    rule_metrics = benchmark_eval.get("rule_metrics") or {}
    retrieval = (benchmark_eval.get("retrieval_benchmark") or {}).get("metrics") or {}
    proposal = benchmark_eval.get("proposal_metrics") or {}
    gis = benchmark_eval.get("gis_contract_metrics") or {}
    quality = benchmark_eval.get("quality_gates") or {}
    return {
        "quality_gates_passed": bool(quality.get("passed")),
        "failed_gates": quality.get("failed_gates") or [],
        "retrieval_recall_at_6": retrieval.get("retrieval_recall_at_6"),
        "candidate_recall": rule_metrics.get("candidate_recall"),
        "verified_precision": rule_metrics.get("verified_precision"),
        "verified_recall": rule_metrics.get("verified_recall"),
        "false_verified_count": rule_metrics.get("false_verified_count", 0),
        "verified_source_support_failed_count": rule_metrics.get("verified_source_support_failed_count", 0),
        "gis_review_rule_leak_count": gis.get("review_rule_leak_count", 0),
        "proposal_case_accuracy": proposal.get("proposal_case_accuracy"),
        "proposal_decision_accuracy": proposal.get("proposal_decision_accuracy"),
        "false_approval_count": proposal.get("false_approval_count", 0),
    }


def _compact_citation(citation: dict[str, Any]) -> dict[str, Any]:
    if not citation:
        return {}
    return {
        "evidence_id": str(citation.get("evidence_id") or ""),
        "span_id": str(citation.get("span_id") or ""),
        "section_id": str(citation.get("section_id") or ""),
        "page": citation.get("page"),
        "quote": _clip(citation.get("quote"), 900),
    }


def _review_evidence(candidate: dict[str, Any], field_citations: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for field, citation in field_citations.items():
        if not isinstance(citation, dict):
            continue
        evidence_id = str(citation.get("evidence_id") or "")
        key = f"{field}:{evidence_id}:{citation.get('span_id')}"
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "field": str(field),
                "evidence_id": evidence_id,
                "span_id": str(citation.get("span_id") or ""),
                "section_id": str(citation.get("section_id") or ""),
                "page": citation.get("page"),
                "quote": _clip(citation.get("quote"), 900),
            }
        )
    if rows:
        return rows[:8]
    return [
        {"field": "candidate", "evidence_id": str(eid), "span_id": "", "section_id": "", "page": None, "quote": ""}
        for eid in candidate.get("evidence_ids") or []
        if eid
    ][:8]


def _search_text(*parts: Any) -> str:
    flattened: list[str] = []
    for part in parts:
        if isinstance(part, dict):
            flattened.extend(str(value) for value in part.values())
        elif isinstance(part, (list, tuple, set)):
            flattened.extend(str(value) for value in part)
        elif part is not None:
            flattened.append(str(part))
    return " ".join(flattened).lower()


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "n/a"


def _clip(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _json_for_script(value: dict[str, Any]) -> str:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _render_app_html(manifest: dict[str, Any]) -> str:
    data_json = _json_for_script(manifest)
    cards_html = "\n".join(_app_card(card) for card in manifest.get("cards") or [])
    benchmark_svg = _benchmark_svg(manifest.get("benchmark_metrics") or {})
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>F1 Command Center</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17212b;
      --muted: #617181;
      --line: #d8e1e8;
      --soft: #f6f8fa;
      --panel: #ffffff;
      --green: #0c7a5b;
      --red: #b13f34;
      --amber: #a56300;
      --blue: #245f9f;
      --violet: #6956a8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #ffffff;
    }}
    header {{
      padding: 20px 28px 14px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfd;
    }}
    .topline {{ display: flex; align-items: baseline; justify-content: space-between; gap: 16px; flex-wrap: wrap; }}
    h1 {{ margin: 0; font-size: 24px; letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 16px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 8px; font-size: 14px; letter-spacing: 0; }}
    .run {{ color: var(--muted); font-size: 13px; }}
    main {{ padding: 18px 28px 34px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}
    .card {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; background: var(--panel); min-height: 78px; }}
    .card .label {{ color: var(--muted); font-size: 12px; }}
    .card .value {{ margin-top: 7px; font-size: 24px; font-weight: 760; }}
    .card.good .value {{ color: var(--green); }}
    .card.warn .value {{ color: var(--amber); }}
    .card.neutral .value {{ color: var(--blue); }}
    .workspace {{ margin-top: 18px; display: grid; grid-template-columns: minmax(320px, 1.05fr) minmax(340px, 1.15fr) minmax(280px, .8fr); gap: 14px; align-items: start; }}
    .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); min-width: 0; }}
    .panel-head {{ padding: 12px 14px; border-bottom: 1px solid var(--line); background: var(--soft); }}
    .panel-body {{ padding: 12px 14px; }}
    .controls {{ display: grid; grid-template-columns: 1fr 160px; gap: 8px; }}
    input, select, button {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #ffffff;
      color: var(--ink);
      font: inherit;
      min-height: 36px;
      padding: 7px 9px;
    }}
    button {{ cursor: pointer; background: #eef4f9; border-color: #c9d8e4; font-weight: 650; }}
    button:hover {{ background: #e2edf6; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 8px 7px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }}
    tbody tr {{ cursor: pointer; }}
    tbody tr:hover {{ background: #f4f8fb; }}
    .scroll {{ max-height: 420px; overflow: auto; }}
    .pill {{ display: inline-flex; align-items: center; border-radius: 999px; padding: 2px 8px; font-size: 12px; border: 1px solid var(--line); background: #f8fafc; }}
    .pill.good {{ color: var(--green); border-color: #b9dfd1; background: #eef9f5; }}
    .pill.warn {{ color: var(--amber); border-color: #ead3a8; background: #fff8ea; }}
    .pill.bad {{ color: var(--red); border-color: #efc3bd; background: #fff2f0; }}
    .detail-grid {{ display: grid; grid-template-columns: 130px 1fr; gap: 8px 12px; font-size: 13px; }}
    .detail-grid dt {{ color: var(--muted); }}
    .detail-grid dd {{ margin: 0; min-width: 0; overflow-wrap: anywhere; }}
    .quote {{ margin-top: 10px; padding: 10px 11px; border-left: 3px solid var(--blue); background: #f5f8fb; color: #263746; font-size: 13px; line-height: 1.45; }}
    .section-grid {{ margin-top: 14px; display: grid; grid-template-columns: minmax(320px, .9fr) minmax(360px, 1.1fr); gap: 14px; align-items: start; }}
    .sandbox {{ display: grid; grid-template-columns: 1fr 110px 96px; gap: 8px; align-items: end; }}
    .result {{ margin-top: 10px; padding: 10px 11px; border-radius: 8px; background: var(--soft); border: 1px solid var(--line); font-size: 13px; }}
    .tiny {{ color: var(--muted); font-size: 12px; line-height: 1.45; }}
    .empty {{ color: var(--muted); padding: 12px 2px; }}
    code {{ background: #eef4f8; border-radius: 4px; padding: 1px 4px; }}
    @media (max-width: 1180px) {{ .workspace, .section-grid {{ grid-template-columns: 1fr; }} }}
    @media (max-width: 760px) {{
      header, main {{ padding-left: 16px; padding-right: 16px; }}
      .controls, .sandbox {{ grid-template-columns: 1fr; }}
      .cards {{ grid-template-columns: repeat(2, minmax(130px, 1fr)); }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="topline">
      <h1>F1 Bylaw Intelligence Command Center</h1>
      <div class="run">City <code>{html.escape(str(manifest.get("city_key") or ""))}</code> · Run <code>{html.escape(str(manifest.get("run_id") or ""))}</code></div>
    </div>
  </header>
  <main>
    <section class="cards">{cards_html}</section>
    <section class="workspace">
      <div class="panel">
        <div class="panel-head">
          <h2>Rule Explorer</h2>
          <div class="controls">
            <input id="ruleSearch" type="search" placeholder="Search rules, objects, evidence">
            <select id="ruleObjectFilter"><option value="">All objects</option></select>
          </div>
        </div>
        <div class="panel-body scroll">
          <table>
            <thead><tr><th>Rule</th><th>Object</th><th>Limit</th><th>Applies To</th></tr></thead>
            <tbody id="verifiedRows"></tbody>
          </table>
        </div>
      </div>
      <div class="panel">
        <div class="panel-head"><h2>Selected Rule</h2></div>
        <div class="panel-body" id="ruleDetail"></div>
      </div>
      <div class="panel">
        <div class="panel-head"><h2>Evidence Inspector</h2></div>
        <div class="panel-body" id="evidencePanel"></div>
      </div>
    </section>
    <section class="section-grid">
      <div class="panel">
        <div class="panel-head">
          <h2>Review Workbench</h2>
          <div class="controls">
            <input id="reviewSearch" type="search" placeholder="Search review gaps and evidence">
            <select id="reviewStatusFilter"><option value="">All statuses</option></select>
          </div>
        </div>
        <div class="panel-body scroll">
          <table>
            <thead><tr><th>Rule</th><th>Status</th><th>Object</th><th>Gap</th></tr></thead>
            <tbody id="reviewRows"></tbody>
          </table>
        </div>
      </div>
      <div class="panel">
        <div class="panel-head"><h2>Compliance And Safety</h2></div>
        <div class="panel-body">
          <h3>Single-Rule Sandbox</h3>
          <div class="sandbox">
            <select id="scenarioRule"></select>
            <input id="scenarioValue" type="number" step="0.01" placeholder="Value">
            <button id="scenarioRun" type="button">Check</button>
          </div>
          <div id="scenarioResult" class="result">Select a verified rule and enter a value.</div>
          <h3 style="margin-top:16px">Benchmark Gates</h3>
          {benchmark_svg}
          <div id="benchmarkText" class="tiny"></div>
          <h3 style="margin-top:16px">Chatbot Boundary</h3>
          <div id="chatbotSafety" class="tiny"></div>
        </div>
      </div>
    </section>
  </main>
  <script id="app-data" type="application/json">{data_json}</script>
  <script>
    const data = JSON.parse(document.getElementById('app-data').textContent);
    const state = {{ selectedRuleId: (data.verified_rules[0] || {{}}).rule_id || '', selectedReviewId: '' }};
    const $ = (id) => document.getElementById(id);
    const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
    const compact = (value, fallback='') => {{
      const text = String(value ?? '').trim();
      return text || fallback;
    }};
    const limitText = (rule) => `${{compact(rule.operator)}} ${{compact(rule.value)}} ${{compact(rule.unit)}}`.trim();
    function statusPill(status) {{
      const lower = String(status || '').toLowerCase();
      let tone = 'warn';
      if (lower.includes('verified') || lower.includes('success')) tone = 'good';
      if (lower.includes('rejected')) tone = 'bad';
      return `<span class="pill ${{tone}}">${{esc(status)}}</span>`;
    }}
    function populateFilters() {{
      const objects = [...new Set(data.verified_rules.map((rule) => rule.rule_object).filter(Boolean))].sort();
      $('ruleObjectFilter').innerHTML = '<option value="">All objects</option>' + objects.map((item) => `<option value="${{esc(item)}}">${{esc(item)}}</option>`).join('');
      const statuses = [...new Set(data.review_queue.map((item) => item.status).filter(Boolean))].sort();
      $('reviewStatusFilter').innerHTML = '<option value="">All statuses</option>' + statuses.map((item) => `<option value="${{esc(item)}}">${{esc(item)}}</option>`).join('');
      $('scenarioRule').innerHTML = data.verified_rules.map((rule) => `<option value="${{esc(rule.rule_id)}}">${{esc(rule.rule_id)}} · ${{esc(rule.rule_object)}} ${{esc(limitText(rule))}}</option>`).join('');
    }}
    function renderRules() {{
      const search = $('ruleSearch').value.toLowerCase();
      const objectFilter = $('ruleObjectFilter').value;
      const rows = data.verified_rules.filter((rule) => {{
        if (objectFilter && rule.rule_object !== objectFilter) return false;
        return !search || rule.search_text.includes(search);
      }});
      $('verifiedRows').innerHTML = rows.map((rule) => `
        <tr data-rule="${{esc(rule.rule_id)}}">
          <td><code>${{esc(rule.rule_id)}}</code></td>
          <td>${{esc(rule.rule_object)}}</td>
          <td>${{esc(limitText(rule))}}</td>
          <td>${{esc(rule.applies_to || rule.constraint_scope)}}</td>
        </tr>`).join('') || '<tr><td colspan="4" class="empty">No matching verified rules.</td></tr>';
      document.querySelectorAll('[data-rule]').forEach((row) => row.addEventListener('click', () => selectRule(row.dataset.rule)));
      if (!rows.find((rule) => rule.rule_id === state.selectedRuleId) && rows[0]) selectRule(rows[0].rule_id);
    }}
    function selectRule(ruleId) {{
      state.selectedRuleId = ruleId;
      const rule = data.verified_rules.find((item) => item.rule_id === ruleId);
      if (!rule) return;
      $('scenarioRule').value = ruleId;
      $('ruleDetail').innerHTML = `
        <dl class="detail-grid">
          <dt>Status</dt><dd>${{statusPill(rule.verification_status)}}</dd>
          <dt>Rule ID</dt><dd><code>${{esc(rule.rule_id)}}</code></dd>
          <dt>Object</dt><dd>${{esc(rule.rule_object)}}</dd>
          <dt>Limit</dt><dd>${{esc(limitText(rule))}}</dd>
          <dt>Applies To</dt><dd>${{esc(rule.applies_to || 'not specified')}}</dd>
          <dt>Scope</dt><dd>${{esc(rule.constraint_scope || 'not specified')}}</dd>
          <dt>Condition</dt><dd>${{esc(rule.condition || 'none')}}</dd>
          <dt>Exception</dt><dd>${{esc(rule.exception || 'none')}}</dd>
          <dt>GIS Target</dt><dd>${{esc(rule.geometry_target || 'none')}}</dd>
        </dl>`;
      renderEvidenceForRule(rule);
    }}
    function renderEvidenceForRule(rule) {{
      const citation = rule.citation || {{}};
      $('evidencePanel').innerHTML = `
        <div class="detail-grid">
          <dt>Evidence ID</dt><dd><code>${{esc(citation.evidence_id || (rule.evidence_ids || [])[0] || 'none')}}</code></dd>
          <dt>Page</dt><dd>${{esc(citation.page ?? 'unknown')}}</dd>
          <dt>Section</dt><dd>${{esc(citation.section_id || 'unknown')}}</dd>
          <dt>Span</dt><dd><code>${{esc(citation.span_id || 'unknown')}}</code></dd>
        </div>
        <div class="quote">${{esc(citation.quote || 'No quote attached to this rule.')}}</div>`;
    }}
    function renderReviews() {{
      const search = $('reviewSearch').value.toLowerCase();
      const status = $('reviewStatusFilter').value;
      const rows = data.review_queue.filter((item) => {{
        if (status && item.status !== status) return false;
        return !search || item.search_text.includes(search);
      }});
      $('reviewRows').innerHTML = rows.map((item) => `
        <tr data-review="${{esc(item.rule_id)}}">
          <td><code>${{esc(item.rule_id)}}</code></td>
          <td>${{statusPill(item.status)}}</td>
          <td>${{esc(item.rule_object || 'unknown')}}</td>
          <td>${{esc((item.support_gaps || item.unresolved_dependencies || []).slice(0, 2).join(', ') || 'context required')}}</td>
        </tr>`).join('') || '<tr><td colspan="4" class="empty">No matching review items.</td></tr>';
      document.querySelectorAll('[data-review]').forEach((row) => row.addEventListener('click', () => selectReview(row.dataset.review)));
    }}
    function selectReview(ruleId) {{
      state.selectedReviewId = ruleId;
      const item = data.review_queue.find((row) => row.rule_id === ruleId);
      if (!item) return;
      $('ruleDetail').innerHTML = `
        <dl class="detail-grid">
          <dt>Status</dt><dd>${{statusPill(item.status)}}</dd>
          <dt>Rule ID</dt><dd><code>${{esc(item.rule_id)}}</code></dd>
          <dt>Object</dt><dd>${{esc(item.rule_object || 'unknown')}}</dd>
          <dt>Candidate</dt><dd>${{esc(limitText(item))}}</dd>
          <dt>Applies To</dt><dd>${{esc(item.applies_to || 'not specified')}}</dd>
          <dt>Gaps</dt><dd>${{esc((item.support_gaps || []).join(', ') || 'none listed')}}</dd>
          <dt>Dependencies</dt><dd>${{esc((item.unresolved_dependencies || []).join(', ') || 'none listed')}}</dd>
        </dl>`;
      $('evidencePanel').innerHTML = (item.evidence || []).map((ev) => `
        <div class="detail-grid">
          <dt>Field</dt><dd>${{esc(ev.field)}}</dd>
          <dt>Evidence ID</dt><dd><code>${{esc(ev.evidence_id || 'none')}}</code></dd>
          <dt>Page</dt><dd>${{esc(ev.page ?? 'unknown')}}</dd>
        </div>
        <div class="quote">${{esc(ev.quote || 'No quote attached.')}}</div>`).join('') || '<div class="empty">No evidence attached.</div>';
    }}
    function runScenario() {{
      const rule = data.verified_rules.find((item) => item.rule_id === $('scenarioRule').value);
      const actual = Number($('scenarioValue').value);
      const target = Number(rule && rule.value);
      if (!rule || !Number.isFinite(actual) || !Number.isFinite(target)) {{
        $('scenarioResult').innerHTML = 'Needs review: the selected rule or value is not numeric.';
        return;
      }}
      const op = String(rule.operator || '').trim();
      let passes = false;
      if (op === '<=' || op === '≤') passes = actual <= target;
      else if (op === '>=' || op === '≥') passes = actual >= target;
      else if (op === '<') passes = actual < target;
      else if (op === '>') passes = actual > target;
      else passes = actual === target;
      const tone = passes ? 'good' : 'bad';
      const label = passes ? 'passes this verified rule' : 'fails this verified rule';
      $('scenarioResult').innerHTML = `<span class="pill ${{tone}}">${{esc(label)}}</span> ${{esc(actual)}} against <code>${{esc(rule.rule_id)}}</code> (${{esc(limitText(rule))}}). This is not a full project approval.`;
    }}
    function renderSafety() {{
      const bm = data.benchmark_metrics || {{}};
      const chat = data.chatbot_metrics || {{}};
      $('benchmarkText').innerHTML = `Quality gates: <strong>${{bm.quality_gates_passed ? 'passed' : 'not passed'}}</strong>. Failed gates: ${{esc((bm.failed_gates || []).join(', ') || 'none')}}.`;
      $('chatbotSafety').innerHTML = `Cases: ${{esc(chat.case_count || 0)}}. Cited answers: ${{esc(chat.cited_answer_count || 0)}}. Approval claims: ${{esc(chat.approval_claim_count || 0)}}. False approvals: ${{esc(chat.false_approval_count || 0)}}.`;
    }}
    populateFilters();
    renderRules();
    renderReviews();
    renderSafety();
    if (state.selectedRuleId) selectRule(state.selectedRuleId);
    $('ruleSearch').addEventListener('input', renderRules);
    $('ruleObjectFilter').addEventListener('change', renderRules);
    $('reviewSearch').addEventListener('input', renderReviews);
    $('reviewStatusFilter').addEventListener('change', renderReviews);
    $('scenarioRule').addEventListener('change', () => selectRule($('scenarioRule').value));
    $('scenarioRun').addEventListener('click', runScenario);
  </script>
</body>
</html>
"""


def _app_card(card: dict[str, Any]) -> str:
    return (
        f"<div class='card {html.escape(str(card.get('tone') or 'neutral'))}'>"
        f"<div class='label'>{html.escape(str(card.get('label') or ''))}</div>"
        f"<div class='value'>{html.escape(str(card.get('value') or 0))}</div>"
        "</div>"
    )


def _benchmark_svg(metrics: dict[str, Any]) -> str:
    rows = [
        ("Retrieval", metrics.get("retrieval_recall_at_6"), "#245f9f"),
        ("Candidate", metrics.get("candidate_recall"), "#6956a8"),
        ("Precision", metrics.get("verified_precision"), "#0c7a5b"),
        ("Proposal", metrics.get("proposal_case_accuracy"), "#a56300"),
    ]
    svg_rows: list[str] = []
    y = 18
    for label, value, color in rows:
        try:
            width = max(0, min(1, float(value))) * 220
            text_value = f"{float(value) * 100:.1f}%"
        except (TypeError, ValueError):
            width = 0
            text_value = "n/a"
        svg_rows.append(f"<text x='12' y='{y + 12}' font-size='12' fill='#617181'>{html.escape(label)}</text>")
        svg_rows.append(f"<rect x='92' y='{y}' width='220' height='14' fill='#edf2f6' rx='4'/>")
        svg_rows.append(f"<rect x='92' y='{y}' width='{width:.1f}' height='14' fill='{color}' rx='4'/>")
        svg_rows.append(f"<text x='320' y='{y + 12}' font-size='12' fill='#17212b'>{text_value}</text>")
        y += 28
    return (
        "<svg viewBox='0 0 370 128' width='100%' role='img' aria-label='F1 benchmark metric bars'>"
        "<rect x='0' y='0' width='370' height='128' fill='#f6f8fa' rx='8'/>"
        + "".join(svg_rows)
        + "</svg>"
    )


def _render_html(manifest: dict[str, Any]) -> str:
    cards = manifest["cards"]
    rules = manifest["verified_rules"]
    review_queue = manifest["review_queue"]
    compliance_counts = manifest["compliance_status_counts"]
    chatbot_metrics = manifest["chatbot_metrics"]
    card_html = "\n".join(_card(card) for card in cards)
    rule_rows = "\n".join(_rule_row(rule) for rule in rules) or "<tr><td colspan='6'>No verified GIS rules.</td></tr>"
    review_rows = "\n".join(_review_row(item) for item in review_queue) or "<tr><td colspan='4'>No review items.</td></tr>"
    compliance_svg = _compliance_svg(compliance_counts)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>F1 Command Center Preview</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #16202a;
      --muted: #5f6f7f;
      --line: #d9e2ea;
      --panel: #f7fafc;
      --good: #0d7a5f;
      --warn: #a56300;
      --blue: #1d5f9f;
    }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #ffffff;
    }}
    header {{
      padding: 28px 36px 18px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #f8fbfd 0%, #ffffff 100%);
    }}
    h1 {{ margin: 0 0 8px; font-size: 30px; letter-spacing: 0; }}
    h2 {{ margin: 0 0 14px; font-size: 18px; letter-spacing: 0; }}
    p {{ color: var(--muted); line-height: 1.5; max-width: 980px; }}
    main {{ padding: 24px 36px 42px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; background: var(--panel); }}
    .label {{ color: var(--muted); font-size: 13px; }}
    .value {{ margin-top: 8px; font-size: 28px; font-weight: 760; }}
    .good .value {{ color: var(--good); }}
    .warn .value {{ color: var(--warn); }}
    section {{ margin-top: 28px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 8px; text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    .split {{ display: grid; grid-template-columns: minmax(280px, 420px) 1fr; gap: 22px; align-items: start; }}
    .note {{ color: var(--muted); font-size: 13px; }}
    code {{ background: #eef4f8; border-radius: 4px; padding: 1px 4px; }}
    @media (max-width: 780px) {{
      header, main {{ padding-left: 18px; padding-right: 18px; }}
      .split {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>F1 Bylaw Intelligence Command Center</h1>
    <p>City: <code>{html.escape(manifest["city_key"])}</code> · Run: <code>{html.escape(manifest["run_id"])}</code>. This preview reads only F1 artifacts from the current run. GIS and compliance remain verified-only, and chatbot approval authority is disabled.</p>
  </header>
  <main>
    <section class="grid">{card_html}</section>
    <section class="split">
      <div>
        <h2>Compliance Smoke Results</h2>
        {compliance_svg}
        <p class="note">Smoke scenarios validate wiring. Release claims still require benchmark proposal cases.</p>
      </div>
      <div>
        <h2>Chatbot Safety</h2>
        <table>
          <tr><th>Metric</th><th>Value</th></tr>
          <tr><td>Cases</td><td>{html.escape(str(chatbot_metrics.get("case_count", 0)))}</td></tr>
          <tr><td>Cited answers</td><td>{html.escape(str(chatbot_metrics.get("cited_answer_count", 0)))}</td></tr>
          <tr><td>Uncertain/refusal</td><td>{html.escape(str(chatbot_metrics.get("uncertain_count", 0)))}</td></tr>
          <tr><td>Approval claims</td><td>{html.escape(str(chatbot_metrics.get("approval_claim_count", 0)))}</td></tr>
        </table>
      </div>
    </section>
    <section>
      <h2>Verified GIS Rules</h2>
      <table>
        <tr><th>Rule</th><th>Object</th><th>Applies To</th><th>Operator</th><th>Value</th><th>Geometry</th></tr>
        {rule_rows}
      </table>
    </section>
    <section>
      <h2>Review Or Rejected Items</h2>
      <table>
        <tr><th>Rule</th><th>Status</th><th>Support Gaps</th><th>Dependencies</th></tr>
        {review_rows}
      </table>
    </section>
  </main>
</body>
</html>
"""


def _card(card: dict[str, Any]) -> str:
    return (
        f"<div class='card {html.escape(str(card.get('tone') or 'neutral'))}'>"
        f"<div class='label'>{html.escape(str(card.get('label') or ''))}</div>"
        f"<div class='value'>{html.escape(str(card.get('value') or 0))}</div>"
        "</div>"
    )


def _rule_row(rule: dict[str, Any]) -> str:
    value = f"{rule.get('value')} {rule.get('unit') or ''}".strip()
    return (
        "<tr>"
        f"<td>{html.escape(str(rule.get('rule_id') or ''))}</td>"
        f"<td>{html.escape(str(rule.get('rule_object') or ''))}</td>"
        f"<td>{html.escape(str(rule.get('applies_to') or ''))}</td>"
        f"<td>{html.escape(str(rule.get('operator') or ''))}</td>"
        f"<td>{html.escape(value)}</td>"
        f"<td>{html.escape(str(rule.get('geometry_target') or ''))}</td>"
        "</tr>"
    )


def _review_row(item: dict[str, Any]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(str(item.get('rule_id') or ''))}</td>"
        f"<td>{html.escape(str(item.get('status') or ''))}</td>"
        f"<td>{html.escape(', '.join(str(gap) for gap in item.get('support_gaps') or []))}</td>"
        f"<td>{html.escape(', '.join(str(dep) for dep in item.get('unresolved_dependencies') or []))}</td>"
        "</tr>"
    )


def _compliance_svg(counts: dict[str, Any]) -> str:
    approved = int(counts.get("approved") or 0)
    rejected = int(counts.get("rejected") or 0)
    review = int(counts.get("needs_review") or 0)
    total = max(approved + rejected + review, 1)
    values = [
        ("Approved", approved, "#0d7a5f"),
        ("Rejected", rejected, "#a63d2d"),
        ("Needs Review", review, "#a56300"),
    ]
    x = 18
    bars = []
    for label, value, color in values:
        width = int(300 * value / total)
        bars.append(f"<rect x='{x}' y='34' width='{width}' height='26' fill='{color}' rx='4'/>")
        bars.append(f"<text x='{x}' y='84' font-size='12' fill='#16202a'>{html.escape(label)}: {value}</text>")
        x += width + 8
    return (
        "<svg viewBox='0 0 360 104' width='100%' role='img' aria-label='Compliance smoke result counts'>"
        "<rect x='0' y='0' width='360' height='104' fill='#f7fafc' rx='8'/>"
        + "".join(bars)
        + "</svg>"
    )
