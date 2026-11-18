"""Streamlit product UI for the F1 Bylaw Intelligence Command Center."""

from __future__ import annotations

import html
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "dashboard" / "assets"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.f1_data import (  # noqa: E402
    DEFAULT_F1_OUTPUT,
    answer_artifact_question,
    benchmark_gate_rows,
    compliance_rows,
    compliance_status_rows,
    discover_f1_outputs,
    evidence_rows,
    evidence_navigation_rows,
    evaluate_single_rule,
    find_review_item,
    find_rule,
    load_f1_output,
    operator_action_template_rows,
    operator_review_action_rows,
    retrieval_evidence_rows,
    review_gap_rows,
    review_rows,
    review_statuses,
    rule_objects,
    rule_rows,
    save_operator_review_action,
    scenario_template_rows,
)


NAV_ITEMS = [
    "0 Command Center",
    "1 Sources",
    "2 Verified Rules",
    "3 Review Workbench",
    "4 Repair Evidence",
    "5 GIS + Compliance",
    "6 Quality Audit",
]

PAGE_TITLES = {
    "0 Command Center": "Bylaw Intelligence Command Center",
    "1 Sources": "Source Documents",
    "2 Verified Rules": "Verified Rules",
    "3 Review Workbench": "Review Workbench",
    "4 Repair Evidence": "Repair Evidence",
    "5 GIS + Compliance": "GIS + Compliance",
    "6 Quality Audit": "Quality Checks",
}

PAGE_BLURBS = {
    "0 Command Center": "A city bylaw run distilled into verified rules, review work, source evidence, and bounded answers.",
    "1 Sources": "Official bylaw PDFs, scoped source pages, and evidence packets used by the verifier.",
    "2 Verified Rules": "Source-supported rules that can be used downstream.",
    "3 Review Workbench": "One held candidate at a time: why it is blocked, what evidence differs, and what to inspect next.",
    "4 Repair Evidence": "Shadow evidence checks: what improved, what still blocks verification, and why outputs do not change automatically.",
    "5 GIS + Compliance": "Verified-only, deduplicated rules prepared for map and scenario use.",
    "6 Quality Audit": "Audit support for source coverage, status mix, and verification-flow diagnostics.",
}


def main() -> None:
    try:
        import streamlit as st
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise SystemExit("Streamlit is required: .venv/bin/python -m streamlit run streamlit_app.py") from exc

    st.set_page_config(
        page_title="F1 Bylaw Command Center",
        page_icon="F1",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _style(st)

    output_dir = _sidebar_output_selector(st)
    data = load_f1_output(output_dir)
    if not data.get("manifest"):
        st.error("No F1 command-center manifest was found for the selected output.")
        st.stop()

    page = _sidebar_nav(st, data)
    _page_header(st, data, page)

    if page == "0 Command Center":
        _results_chat_page(st, data)
    elif page == "1 Sources":
        _source_documents_page(st, data)
    elif page == "2 Verified Rules":
        _verified_rules_page(st, data)
    elif page == "3 Review Workbench":
        _human_review_page(st, data)
    elif page == "4 Repair Evidence":
        _repair_evidence_page(st, data)
    elif page == "5 GIS + Compliance":
        _gis_handoff_page(st, data)
    else:
        _quality_audit_page(st, data)


def _sidebar_output_selector(st: Any) -> Path:
    outputs = discover_f1_outputs()
    if DEFAULT_F1_OUTPUT.exists() and DEFAULT_F1_OUTPUT not in outputs:
        outputs.insert(0, DEFAULT_F1_OUTPUT)
    labels = [
        f"Current F1 — {path.parent.name.replace('_', ' ').title()} · {path.name.replace('_', ' ').title()}"
        for path in outputs
    ]

    st.sidebar.markdown(
        "<div class='side-brand'><span>F1</span><b>Bylaw Command<br>Center</b></div>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("<div class='rail-label'>Current run</div>", unsafe_allow_html=True)
    if not outputs:
        st.sidebar.error("No F1 command-center outputs found.")
        return DEFAULT_F1_OUTPUT
    default_index = outputs.index(DEFAULT_F1_OUTPUT) if DEFAULT_F1_OUTPUT in outputs else 0
    selected = st.sidebar.selectbox("Current run", labels, index=default_index, label_visibility="collapsed")
    output_dir = outputs[labels.index(selected)]

    source = _source_document(data=None, output_dir=output_dir)
    st.sidebar.markdown(
        "<div class='source-card'><span>Source document</span>"
        f"<a href='{html.escape(source.get('source_url') or '#')}' target='_blank'>Open official PDF</a></div>",
        unsafe_allow_html=True,
    )
    return output_dir


def _sidebar_nav(st: Any, data: dict[str, Any]) -> str:
    st.sidebar.markdown("<div class='rail-label'>Pipeline order</div>", unsafe_allow_html=True)
    page = st.sidebar.radio("Pipeline order", NAV_ITEMS, label_visibility="collapsed")
    st.sidebar.markdown(
        "<div class='side-rule'><b>Product law</b><span>Verified rules move forward. Uncertain rules stay out of GIS and approval flows.</span></div>",
        unsafe_allow_html=True,
    )
    st.sidebar.caption("Source-grounded bylaw intelligence. Verification controls what moves forward.")
    return page


def _page_header(st: Any, data: dict[str, Any], page: str) -> None:
    manifest = data.get("manifest") or {}
    city = _city_label(manifest.get("city_key"))
    health = manifest.get("workflow_health") or {}
    benchmark = manifest.get("benchmark_metrics") or {}
    status = "Benchmark safe" if health.get("quality_gates_passed") else "Needs audit"
    flow = _candidate_flow_counts(data)
    st.markdown(
        f"""
        <div class="command-topbar">
          <div>
            <span class="eyebrow">F1 product run</span>
            <span class="city-chip">{html.escape(city)}</span>
          </div>
          <span class="health-chip">{html.escape(status)}</span>
        </div>
        <h1 class="page-title">{html.escape(PAGE_TITLES[page])}</h1>
        <p class="page-blurb">{html.escape(PAGE_BLURBS[page])}</p>
        <div class="metric-pill-row">
          <span><b>{html.escape(str(health.get("verified_rule_count", 0)))}</b> verified rules</span>
          <span><b>{html.escape(str(health.get("review_queue_count", 0)))}</b> operator queue</span>
          <span><b>{html.escape(str(flow.get("in_review", 0)))}</b> still needs proof</span>
          <span><b>{html.escape(_pct(benchmark.get("verified_precision")))}</b> precision</span>
          <span><b>{html.escape(str(health.get("false_verified_count", 0)))}</b> false verified</span>
          <span><b>{html.escape(str(health.get("false_approval_count", 0)))}</b> false approvals</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _results_chat_page(st: Any, data: dict[str, Any]) -> None:
    manifest = data.get("manifest") or {}
    source = _source_document(data)
    flow = _candidate_flow_counts(data)
    total = max(flow["items_checked"], 1)

    _command_briefing(st, data, manifest, source, flow)

    verified_pct = flow["verified"] / total * 100
    review_pct = flow["in_review"] / total * 100
    rejected_pct = flow["rejected"] / total * 100
    st.markdown(
        "<div class='white-card flow-panel'><div class='card-title-row'><div class='card-title-text'>Candidate Check Flow</div><span>Verifier-owned</span></div>"
        "<div class='flow-grid'>"
        f"<div class='flow-total'><span>Items checked</span><b>{flow['items_checked']}</b></div>"
        f"<div class='flow-card good'><span>Verified</span><b>{flow['verified']}</b><small>{verified_pct:.1f}%. Moves downstream.</small></div>"
        f"<div class='flow-card warn'><span>In review</span><b>{flow['in_review']}</b><small>{review_pct:.1f}%. Needs review.</small></div>"
        f"<div class='flow-card bad'><span>Rejected</span><b>{flow['rejected']}</b><small>{rejected_pct:.1f}%. Blocked.</small></div>"
        "</div>"
        f"<div class='flow-bar'><i class='good' style='width:{verified_pct:.2f}%'></i><i class='warn' style='width:{review_pct:.2f}%'></i><i class='bad' style='width:{rejected_pct:.2f}%'></i></div>"
        "<div class='flow-foot'><span>All checked items are accounted for in verifier buckets.</span><b>Verified-only rules feed GIS and compliance.</b></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    _operations_status_panel(st, data)

    left, right = st.columns([1.1, 0.9])
    with left:
        st.markdown("<div class='white-card chat-shell'><div class='card-title-row'><div class='card-title-text'>Ask the Bylaw</div><span>source grounded</span></div>", unsafe_allow_html=True)
        _ask_f1(st, data, key="home")
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        _guardrail_panel(st, data)

    _next_actions(st)


def _command_briefing(
    st: Any,
    data: dict[str, Any],
    manifest: dict[str, Any],
    source: dict[str, Any],
    flow: dict[str, int],
) -> None:
    benchmark = manifest.get("benchmark_metrics") or {}
    health = manifest.get("workflow_health") or {}
    source_title = _pretty_source_title(source.get("title") or "Official zoning bylaw source")
    st.markdown(
        "<div class='briefing-shell'>"
        "<div class='brief-main'>"
        "<div class='brief-kicker'>Source-to-decision control plane</div>"
        f"<h2>{html.escape(_city_label(manifest.get('city_key')))} bylaw run</h2>"
        f"<p>{html.escape(source_title)} has been turned into a working product surface: verified constraints, review work, GIS handoff, scenario checks, and source-grounded chat.</p>"
        "<div class='system-map'>"
        "<span>Official source</span><i></i><span>Evidence retrieval</span><i></i><span>Rule candidates</span><i></i><span>Verifier</span><i></i><span>Command center</span>"
        "</div>"
        "</div>"
        "<div class='brief-scoreboard'>"
        f"{_score_tile('Verified', flow['verified'], 'good')}"
        f"{_score_tile('Needs proof', flow['in_review'], 'warn')}"
        f"{_score_tile('Rejected', flow['rejected'], 'bad')}"
        f"{_score_tile('Precision', _pct(benchmark.get('verified_precision')), 'good')}"
        "</div>"
        "<div class='brief-rail'>"
        f"<a href='{html.escape(source.get('source_url') or '#')}' target='_blank'>Open source PDF</a>"
        f"<span>{html.escape(str(health.get('review_queue_count', 0)))} operator queue records</span>"
        f"<span>{html.escape(str(health.get('false_verified_count', 0)))} false verified</span>"
        f"<span>{html.escape(str(health.get('false_approval_count', 0)))} false approvals</span>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def _source_documents_page(st: Any, data: dict[str, Any]) -> None:
    source = _source_document(data)
    doc = data.get("document_intelligence_report") or {}
    doc_summary = doc.get("summary") or (data.get("summary") or {}).get("document_intelligence") or {}
    retrieval = data.get("retrieval_report") or {}
    evidence = retrieval.get("evidence") or []

    st.markdown("<div class='white-card'><h3>Source Library</h3><p>Committed source material and evidence packets used by the dashboard.</p>", unsafe_allow_html=True)
    st.markdown(
        "<div class='mini-grid'>"
        f"{_mini_metric('Source spans', doc_summary.get('source_span_count', 0), 'sections available to retrieval')}"
        f"{_mini_metric('Evidence hits', len(evidence), 'bounded support packets')}"
        f"{_mini_metric('Scoped pages', doc_summary.get('page_count', source.get('page_count', 0)), 'source pages represented')}"
        "</div>",
        unsafe_allow_html=True,
    )
    st.link_button("Open official source PDF", source.get("source_url") or "#")
    st.markdown("</div>", unsafe_allow_html=True)

    st.subheader("Registered Source")
    st.dataframe(
        [
            {
                "source_id": source.get("source_id"),
                "title": source.get("title"),
                "pages": source.get("page_count"),
                "hash_verified": source.get("hash_verified"),
                "sha256": source.get("sha256"),
            }
        ],
        width="stretch",
        hide_index=True,
    )
    st.subheader("Evidence Packets")
    st.dataframe(retrieval_evidence_rows(data, limit=100), width="stretch", hide_index=True)
    st.subheader("Rule-to-Source Navigation")
    nav_left, nav_right = st.columns([1, 2])
    source_filter = nav_left.selectbox("Evidence source", ["", "verified", "review"], format_func=lambda value: value.title() if value else "All")
    evidence_query = nav_right.text_input("Search evidence navigation", placeholder="rule id, evidence id, object, quote...")
    st.dataframe(
        evidence_navigation_rows(data, source=source_filter, query=evidence_query, limit=200),
        width="stretch",
        hide_index=True,
    )


def _verified_rules_page(st: Any, data: dict[str, Any]) -> None:
    rules = list((data.get("manifest") or {}).get("verified_rules") or [])
    groups = _rules_by_object(rules)
    st.markdown("<div class='white-card'><h3>Verified-only output</h3><p>Open a group instead of scrolling through the full verified-rule set.</p>", unsafe_allow_html=True)
    filter_left, filter_right = st.columns(2)
    selected_family = filter_left.selectbox("Rule family", [""] + sorted(groups), format_func=lambda value: value.replace("_", " ").title() if value else "All families")
    pages = sorted({str((rule.get("citation") or {}).get("page")) for rule in rules if (rule.get("citation") or {}).get("page")})
    selected_page = filter_right.selectbox("Source page", [""] + pages, format_func=lambda value: f"Page {value}" if value else "All pages")
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = [
        rule
        for rule in rules
        if (not selected_family or rule.get("rule_object") == selected_family)
        and (not selected_page or str((rule.get("citation") or {}).get("page")) == selected_page)
    ]
    family_rows = [{"rule_family": key.replace("_", " ").title(), "count": len(value)} for key, value in groups.items()]
    st.markdown("<div class='rail-label light'>Rule family groups</div>", unsafe_allow_html=True)
    st.dataframe(family_rows, width="stretch", hide_index=True)

    display_groups = _rules_by_object(filtered)
    for family, family_rules in display_groups.items():
        with st.expander(f"{family.replace('_', ' ').title()} - {len(family_rules)} rules", expanded=family == selected_family):
            _rule_sentence_list(st, family_rules)


def _human_review_page(st: Any, data: dict[str, Any]) -> None:
    st.markdown(
        "<div class='white-card'><h3>Human review</h3><p>Rules the verifier could not prove. Pick one item, see why it is held, then open details only when needed.</p>",
        unsafe_allow_html=True,
    )
    with st.expander("Narrow the review queue", expanded=False):
        query_col, status_col = st.columns([2, 1])
        query = query_col.text_input("Search review items", placeholder="support gap, rule id, object, evidence...")
        statuses = [""] + review_statuses(data)
        selected_status = status_col.selectbox("Review status", statuses, format_func=lambda value: value or "All statuses")
    rows = review_rows(data, query=query if "query" in locals() else "", status=selected_status if "selected_status" in locals() else "")
    st.markdown("</div>", unsafe_allow_html=True)

    items = (data.get("manifest") or {}).get("review_queue") or []
    visible_ids = [str(row["rule_id"]) for row in rows if row.get("rule_id")]
    if not visible_ids:
        st.info("No review items match the current filters.")
        return
    selected_rule_id = st.selectbox("Choose a review item", visible_ids, format_func=lambda rid: _review_option_label(find_review_item(data, rid) or {}))
    item = find_review_item(data, selected_rule_id)
    if not item:
        return
    closest = _closest_verified_rule(data, item)
    _review_detail(st, item, closest)
    _operator_action_draft(st, data, item)
    with st.expander("Show grouped worklist", expanded=False):
        st.dataframe(rows, width="stretch", hide_index=True)
    with st.expander("Show source packet", expanded=False):
        st.dataframe(_review_evidence_table(item), width="stretch", hide_index=True)
    with st.expander("Show routing table", expanded=False):
        st.dataframe(review_gap_rows(data), width="stretch", hide_index=True)
    with st.expander("Show saved operator action log", expanded=False):
        st.dataframe(operator_review_action_rows(data), width="stretch", hide_index=True)


def _review_detail(st: Any, item: dict[str, Any], closest: dict[str, Any] | None) -> None:
    gaps = item.get("support_gaps") or item.get("unresolved_dependencies") or [item.get("status") or "review_needed"]
    candidate_sentence = _rule_sentence(item)
    closest_sentence = _rule_sentence(closest or {}) if closest else "No close verified rule loaded."
    st.markdown(
        "<div class='review-grid'>"
        "<div class='white-card'>"
        f"<div class='rail-label light'>Why held</div><h3>{html.escape(_plain_label(gaps[0]))}</h3>"
        f"<p>{html.escape(_gap_reason(item))}</p>"
        f"<div class='kv'><b>Main gap</b><span>{html.escape(', '.join(_plain_label(gap) for gap in gaps[:3]))}</span></div>"
        f"<div class='kv'><b>Priority</b><span>{html.escape(_review_priority(item))}</span></div>"
        f"<div class='kv'><b>Closest verified</b><span>{html.escape(str((closest or {}).get('rule_id') or 'n/a'))}</span></div>"
        "<div class='kv'><b>Next action</b><span>Inspect proof trace and support gaps.</span></div>"
        "</div>"
        "<div class='white-card'>"
        "<div class='rail-label light'>Claim side by side</div>"
        "<h4>Candidate in review</h4>"
        f"<p class='claim'>{html.escape(candidate_sentence)}</p>"
        "<h4>Closest verified rule</h4>"
        f"<p class='claim'>{html.escape(closest_sentence)}</p>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    if closest:
        st.subheader("Highlighted differences")
        st.dataframe(_field_comparison_rows(item, closest), width="stretch", hide_index=True)


def _operator_action_draft(st: Any, data: dict[str, Any], item: dict[str, Any]) -> None:
    templates = data.get("operator_action_templates") or []
    template = next((row for row in templates if row.get("rule_id") == item.get("rule_id")), {})
    allowed = template.get("allowed_actions") or [
        "needs_source_research",
        "ready_for_repair_candidate",
        "request_legal_review",
        "mark_duplicate_candidate",
        "defer",
    ]
    default_action = template.get("recommended_action") if template.get("recommended_action") in allowed else allowed[0]
    st.markdown(
        "<div class='white-card'><div class='rail-label light'>Checkpoint 16 operator action</div>"
        "<h3>Draft next step</h3>"
        "<p>Save a local review note without changing verifier status, verified rules, or GIS outputs.</p>",
        unsafe_allow_html=True,
    )
    action_col, note_col = st.columns([0.8, 1.2])
    action_type = action_col.selectbox(
        "Action",
        allowed,
        index=allowed.index(default_action),
        format_func=lambda value: _plain_label(value),
        key=f"review_action_{item.get('rule_id')}",
    )
    note = note_col.text_area(
        "Reviewer note",
        value=template.get("default_note") or _gap_reason(item),
        height=96,
        key=f"review_note_{item.get('rule_id')}",
    )
    if st.button("Save draft action", key=f"save_review_action_{item.get('rule_id')}"):
        saved = save_operator_review_action(data, rule_id=str(item.get("rule_id")), action_type=action_type, note=note)
        st.success(f"Saved draft {saved['action_id']}. This did not promote or approve the rule.")
    st.markdown("</div>", unsafe_allow_html=True)


def _repair_evidence_page(st: Any, data: dict[str, Any]) -> None:
    report = data.get("repair_rerun_report") or {}
    promotions = data.get("guarded_repair_promotions") or []
    st.markdown("<div class='white-card'><div class='rail-label light'>Shadow only</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='mini-grid'>"
        f"{_mini_metric('Suggestions', report.get('review_only_attempt_count', 0), 'review-only patch candidates')}"
        f"{_mini_metric('Shadow reruns', report.get('attempt_count', 0), 'retested without changing outputs')}"
        f"{_mini_metric('Gaps improved', report.get('review_needed_reduction_from_repair_rerun', 0), 'passed verifier after repair')}"
        f"{_mini_metric('Promotion ready', report.get('promotion_ready_count', 0), 'must still pass deterministic gates')}"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p>Shadow outcome: {html.escape(str(report.get('remaining_review_queue_count', 0)))} still in review, "
        f"{html.escape(str(report.get('repair_rerun_rejected_count', 0)))} rejected, "
        f"{html.escape(str(report.get('guarded_repair_promotion_count', 0)))} repaired successfully. "
        "Output promotion remains blocked unless the verifier proves source support.</p></div>",
        unsafe_allow_html=True,
    )

    if promotions:
        selected = st.selectbox(
            "Choose a repair result",
            [row.get("rule_id") for row in promotions],
            format_func=lambda rule_id: _repair_option_label(next(row for row in promotions if row.get("rule_id") == rule_id)),
        )
        promotion = next(row for row in promotions if row.get("rule_id") == selected)
        _repair_result(st, data, promotion)
    else:
        st.info("No guarded repair promotions are loaded for this run.")
    with st.expander("Show all repair rows", expanded=False):
        st.dataframe(data.get("guarded_repair_promotions") or [], width="stretch")
    with st.expander("Show rerun table", expanded=False):
        st.dataframe(data.get("verifier_rerun_requests") or [], width="stretch")


def _repair_result(st: Any, data: dict[str, Any], promotion: dict[str, Any]) -> None:
    rule = find_rule(data, str(promotion.get("rule_id"))) or {}
    proofs = promotion.get("field_proofs") or {}
    proof_rows = [
        {
            "field": field,
            "evidence_id": proof.get("evidence_id"),
            "page": proof.get("page"),
            "quote": proof.get("quote"),
        }
        for field, proof in proofs.items()
    ]
    st.markdown(
        "<div class='white-card'>"
        f"<div class='rail-label light'>Selected repair result</div><h3>{html.escape(str(promotion.get('rule_id')))}</h3>"
        "<p>Evidence improved and deterministic verification accepted the patched candidate.</p>"
        f"<p class='claim'>{html.escape(_rule_sentence(rule))}</p>"
        f"<div class='kv'><b>Changed fields</b><span>{html.escape(', '.join((promotion.get('changed_fields') or {}).keys()))}</span></div>"
        f"<div class='kv'><b>Decision</b><span>{html.escape(str(promotion.get('decision_status')))}</span></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.dataframe(proof_rows, width="stretch", hide_index=True)


def _gis_handoff_page(st: Any, data: dict[str, Any]) -> None:
    gis = data.get("gis_contract") or {}
    rules = gis.get("rules") or (data.get("manifest") or {}).get("verified_rules") or []
    ready = sum(1 for rule in rules if rule.get("geometry_target") and rule.get("geometry_target") != "unknown")
    st.markdown(
        "<div class='white-card'><h3>GIS handoff</h3><p>Verified-only, geometry-tagged rules ready for the map. These are the only rules that should drive GIS.</p>"
        "<div class='mini-grid'>"
        f"{_mini_metric('Verified rules', gis.get('input_verified_rule_count', len(rules)), 'source-supported')}"
        f"{_mini_metric('GIS constraints', gis.get('export_rule_count', len(rules)), 'deduplicated for the map')}"
        f"{_mini_metric('Map-ready', ready, 'drawable: number + geometry')}"
        "</div></div>",
        unsafe_allow_html=True,
    )
    _scenario_builder(st, data, rules)
    st.markdown("<div class='rail-label light'>Verified GIS rules</div>", unsafe_allow_html=True)
    st.caption("Every verified rule in plain English. Download the machine-readable contract below.")
    _rule_sentence_list(st, rules, limit=120)
    output_dir = Path(data.get("output_dir") or DEFAULT_F1_OUTPUT)
    contract_path = output_dir / "gis_rule_contract.json"
    if contract_path.exists():
        st.download_button(
            "Download gis_rule_contract.json",
            contract_path.read_text(encoding="utf-8"),
            file_name="gis_rule_contract.json",
            mime="application/json",
        )


def _scenario_builder(st: Any, data: dict[str, Any], rules: list[dict[str, Any]]) -> None:
    templates = data.get("scenario_templates") or []
    numeric_rule_ids = [str(item.get("rule_id")) for item in templates if item.get("rule_id")]
    numeric_rules = [rule for rule in rules if str(rule.get("rule_id")) in set(numeric_rule_ids)]
    st.markdown(
        "<div class='white-card'><div class='rail-label light'>Scenario builder</div><h3>Check one verified constraint</h3>"
        "<p>This uses verified-only rules. A pass here is a scoped rule check, not a full permit approval.</p>",
        unsafe_allow_html=True,
    )
    if not numeric_rules:
        st.info("No numeric verified GIS rules are available for scenario checks.")
        st.markdown("</div>", unsafe_allow_html=True)
        return
    template_by_rule = {str(item.get("rule_id")): item for item in templates}
    selected_rule_id = st.selectbox(
        "Verified rule",
        [str(rule.get("rule_id")) for rule in numeric_rules],
        format_func=lambda rid: _scenario_option_label(next(rule for rule in numeric_rules if str(rule.get("rule_id")) == rid)),
    )
    selected_rule = next(rule for rule in numeric_rules if str(rule.get("rule_id")) == selected_rule_id)
    template = template_by_rule.get(selected_rule_id) or {}
    default_value = template.get("passing_example_value") or selected_rule.get("value_numeric") or selected_rule.get("value") or 0
    value = st.number_input("Scenario value", value=float(default_value), step=0.1, key=f"scenario_value_{selected_rule_id}")
    result = evaluate_single_rule(selected_rule, value)
    tone = "good" if result["status"] == "passes_rule" else "bad" if result["status"] == "fails_rule" else "warn"
    st.markdown(
        f"<div class='result-box {tone}'><b>{html.escape(_plain_label(result['status']))}</b>"
        f"<span>{html.escape(result['message'])}</span></div>",
        unsafe_allow_html=True,
    )
    st.dataframe(scenario_template_rows(data), width="stretch", hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _quality_audit_page(st: Any, data: dict[str, Any]) -> None:
    benchmark = (data.get("manifest") or {}).get("benchmark_metrics") or {}
    flow = _candidate_flow_counts(data)
    st.markdown(
        "<div class='white-card'><h3>Analytics</h3><p>Quality, status mix, and verification-flow diagnostics.</p>"
        "<div class='quality-bars'>"
        f"{_quality_bar('Precision', benchmark.get('verified_precision', 0))}"
        f"{_quality_bar('Recall', benchmark.get('verified_recall', 0))}"
        f"{_quality_bar('Source support', 1 if not benchmark.get('verified_source_support_failed_count') else 0)}"
        "</div>"
        f"<p>Precision {_pct(benchmark.get('verified_precision'))} · verified recall {_pct(benchmark.get('verified_recall'))} · false verified {benchmark.get('false_verified_count', 0)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.subheader("Where candidates stop")
    st.markdown(
        "<div class='funnel-row'>"
        f"{_funnel_step(str(flow['items_checked']), 'Candidates extracted', '100%')}"
        f"{_funnel_step(str(flow['items_checked']), 'Evidence-backed candidates', '100%')}"
        f"{_funnel_step(str(flow['verified'] + flow['in_review']), 'Inside verification scope', f'{(flow['verified'] + flow['in_review']) / max(flow['items_checked'], 1) * 100:.0f}%')}"
        f"{_funnel_step(str(flow['verified']), 'Verified', f'{flow['verified'] / max(flow['items_checked'], 1) * 100:.0f}%')}"
        "</div>",
        unsafe_allow_html=True,
    )
    left, right = st.columns(2)
    with left:
        st.subheader("Benchmark Gates")
        st.dataframe(benchmark_gate_rows(data), width="stretch", hide_index=True)
    with right:
        st.subheader("Review Gap Mix")
        st.dataframe(review_gap_rows(data), width="stretch", hide_index=True)
    st.subheader("Checkpoint 16 Operations Trace")
    ops_left, ops_right = st.columns(2)
    with ops_left:
        st.dataframe(operator_action_template_rows(data), width="stretch", hide_index=True)
    with ops_right:
        st.dataframe(operator_review_action_rows(data), width="stretch", hide_index=True)


def _visual_story_strip(st: Any) -> None:
    cols = st.columns(2)
    hero_cards = [
        (
            "Data Chain",
            "f1_command_network.svg",
            "Source packets are ranked, traced, and checked before any rule enters the command flow.",
        ),
        (
            "Operational Safety",
            "f1_flow_ribbon.svg",
            "Only verified rules progress to GIS and compliance; review remains local and auditable.",
        ),
    ]
    for index, (label, filename, blurb) in enumerate(hero_cards):
        path = ASSET_DIR / filename
        if not path.exists():
            continue
        with cols[index % 2]:
            st.image(str(path), width="stretch")
            st.markdown(
                "<div class='hero-note'><b>"
                + html.escape(label)
                + "</b><span>"
                + html.escape(blurb)
                + "</span></div>",
                unsafe_allow_html=True,
            )


def _guardrail_panel(st: Any, data: dict[str, Any]) -> None:
    benchmark = (data.get("manifest") or {}).get("benchmark_metrics") or {}
    gis = data.get("gis_contract") or {}
    st.markdown("<div class='white-card'><h3>Run guardrails</h3><p>A compact safety check. The detailed audit lives in Quality Audit.</p>", unsafe_allow_html=True)
    st.markdown(
        "<div class='guard-grid'>"
        f"{_guard_metric('Verified precision', _pct(benchmark.get('verified_precision')))}"
        f"{_guard_metric('False verified', benchmark.get('false_verified_count', 0))}"
        f"{_guard_metric('Source failures', benchmark.get('verified_source_support_failed_count', 0))}"
        f"{_guard_metric('GIS review leaks', benchmark.get('gis_review_rule_leak_count', gis.get('review_rule_leak_count', 0)))}"
        "</div></div>",
        unsafe_allow_html=True,
    )


def _operations_status_panel(st: Any, data: dict[str, Any]) -> None:
    operations = data.get("operations_report") or {}
    manifest = data.get("manifest") or {}
    app_version = manifest.get("app_version") or "checkpoint_15"
    version_digits = "".join(char for char in str(app_version) if char.isdigit())
    app_version_label = "F1 C" + ((version_digits[-2:].lstrip("0") or version_digits) if version_digits else "?")
    st.markdown(
        "<div class='ops-panel'><div class='card-title-row'><div class='card-title-text'>Product operations</div><span>checkpoint 16</span></div>"
        "<div class='mini-grid'>"
        f"{_mini_metric('App version', app_version_label, 'current product surface')}"
        f"{_mini_metric('Review drafts', operations.get('action_template_count', 0), 'safe action templates')}"
        f"{_mini_metric('Scenario templates', operations.get('scenario_template_count', 0), 'verified-rule checks')}"
        f"{_mini_metric('Evidence links', operations.get('evidence_navigation_count', 0), 'rule-to-source rows')}"
        "</div>"
        "<p class='tiny-note'>This is the product layer: reviewers get action drafts, scenario checks, and evidence navigation. "
        "They do not edit verification decisions, verified rules, or GIS contracts.</p></div>",
        unsafe_allow_html=True,
    )


def _ask_f1(st: Any, data: dict[str, Any], *, key: str) -> None:
    prompt_key = f"f1_chat_prompt_{key}"
    suggestions = [
        "What is the maximum lot coverage?",
        "What still needs review?",
        "Can GIS use review rules?",
        "Is this run safe enough to demo?",
    ]
    st.markdown("<div class='rail-label light'>Prompt library</div>", unsafe_allow_html=True)
    cols = st.columns(2)
    for index, suggestion in enumerate(suggestions):
        if cols[index % 2].button(suggestion, key=f"suggestion_{key}_{index}", width="stretch"):
            st.session_state[prompt_key] = suggestion
    question = st.text_input("Ask", key=prompt_key, placeholder="Ask a bylaw question...")
    if question:
        answer = answer_artifact_question(data, question)
        st.markdown(_chat_answer_markup(answer), unsafe_allow_html=True)


def _chat_answer_markup(answer: dict[str, Any]) -> str:
    tone = str(answer.get("tone") or "neutral")
    details = "".join(f"<li>{html.escape(str(item))}</li>" for item in answer.get("details") or [])
    citations = answer.get("citations") or []
    citation_html = (
        "<div class='citation-row'><b>Citations</b><span>"
        + html.escape(", ".join(str(item) for item in citations))
        + "</span></div>"
        if citations
        else "<div class='citation-row muted'><b>Citations</b><span>No citation needed for this boundary answer.</span></div>"
    )
    label = {
        "safe": "Verified answer",
        "review": "Needs review",
        "blocked": "Boundary",
        "neutral": "F1 answer",
    }.get(tone, "F1 answer")
    return (
        f"<div class='answer-card {html.escape(tone)}'>"
        f"<div class='answer-kicker'>{html.escape(label)}</div>"
        f"<h4>{html.escape(str(answer.get('summary') or answer.get('answer') or 'Answer unavailable.'))}</h4>"
        + (f"<div class='answer-detail'><b>What this means</b><ul>{details}</ul></div>" if details else "")
        + f"<div class='next-step'><b>Next</b><span>{html.escape(str(answer.get('next_step') or 'Open the relevant F1 page for details.'))}</span></div>"
        + citation_html
        + "</div>"
    )


def _next_actions(st: Any) -> None:
    st.markdown(
        "<div class='white-card'><div class='card-title-row'><div class='card-title-text'>Next best actions</div><span>Start here</span></div>"
        "<div class='action-grid'>"
        "<div><b>Explain the result</b><span>Use Ask the Bylaw for a plain-language answer with boundaries and citations.</span></div>"
        "<div><b>Resolve review work</b><span>Open Review Workbench, compare the held rule, and save a draft next step.</span></div>"
        "<div><b>Use verified outputs</b><span>Open GIS + Compliance for verified-only rules and scoped scenario checks.</span></div>"
        "</div></div>",
        unsafe_allow_html=True,
    )


def _candidate_flow_counts(data: dict[str, Any]) -> dict[str, int]:
    verification = data.get("verification_report") or {}
    counts = verification.get("status_counts") or {}
    manifest = data.get("manifest") or {}
    verified = int(counts.get("verified", 0)) + int(counts.get("repaired_successfully", 0))
    rejected = int(counts.get("rejected", 0))
    in_review = int(counts.get("review_needed", 0)) + int(counts.get("context_required", 0)) + int(counts.get("not_used", 0))
    checked = int(verification.get("candidate_count") or (verified + rejected + in_review) or len(manifest.get("verified_rules") or []) + len(manifest.get("review_queue") or []))
    if not (verified or rejected or in_review):
        verified = int((manifest.get("workflow_health") or {}).get("verified_rule_count", 0))
        in_review = int((manifest.get("workflow_health") or {}).get("review_queue_count", 0))
        checked = verified + in_review
    return {"items_checked": checked, "verified": verified, "in_review": in_review, "rejected": rejected}


def _source_document(data: dict[str, Any] | None = None, output_dir: Path | None = None) -> dict[str, Any]:
    if data:
        docs = (data.get("source_registry") or {}).get("documents") or []
        if docs:
            return docs[0]
    if output_dir:
        source_path = output_dir / "source_registry.json"
        if source_path.exists():
            import json

            docs = (json.loads(source_path.read_text(encoding="utf-8")) or {}).get("documents") or []
            if docs:
                return docs[0]
    return {
        "title": "Burnaby Zoning Bylaw 1965 · Division E — R1 District",
        "source_url": "https://www.burnaby.ca/sites/default/files/acquiadam/2024-07/R1Small-Scale-Multi-Unit-Housing-District.pdf",
    }


def _rules_by_object(rules: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rule in rules:
        groups[str(rule.get("rule_object") or "unknown")].append(rule)
    return dict(sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])))


def _closest_verified_rule(data: dict[str, Any], item: dict[str, Any]) -> dict[str, Any] | None:
    for rule in (data.get("manifest") or {}).get("verified_rules") or []:
        if rule.get("rule_object") == item.get("rule_object"):
            return rule
    rules = (data.get("manifest") or {}).get("verified_rules") or []
    return rules[0] if rules else None


def _field_comparison_rows(candidate: dict[str, Any], verified: dict[str, Any]) -> list[dict[str, Any]]:
    fields = ["operator", "value", "unit", "rule_object", "constraint_scope", "applies_to", "condition", "exception"]
    rows = []
    for field in fields:
        c_value = candidate.get(field) or ""
        v_value = verified.get(field) or ""
        if str(c_value) != str(v_value):
            rows.append({"field": field, "status": "different", "candidate": c_value, "verified": v_value})
    return rows or [{"field": "none", "status": "same", "candidate": "", "verified": ""}]


def _review_evidence_table(item: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "field": evidence.get("field"),
            "evidence_id": evidence.get("evidence_id"),
            "page": evidence.get("page"),
            "quote": evidence.get("quote"),
        }
        for evidence in item.get("evidence") or []
    ]


def _rule_sentence_list(st: Any, rules: list[dict[str, Any]], *, limit: int = 80) -> None:
    for index, rule in enumerate(rules[:limit], start=1):
        st.markdown(
            f"<div class='rule-card'><span>{index}</span><div><p>{html.escape(_rule_sentence(rule))}</p>"
            f"{_rule_quote_html(rule)}</div></div>",
            unsafe_allow_html=True,
        )
    if len(rules) > limit:
        st.caption(f"Showing first {limit} of {len(rules)} rules.")


def _rule_quote_html(rule: dict[str, Any]) -> str:
    """The cited bylaw text behind a rule, so a reader sees what the verifier checked."""
    citation = rule.get("citation") or {}
    quote = str(citation.get("quote") or "").strip()
    if not quote:
        return ""
    where = ", ".join(
        part
        for part in (
            f"page {citation['page']}" if citation.get("page") else "",
            f"section {citation['section_id']}" if citation.get("section_id") else "",
        )
        if part
    )
    label = f"Source text ({where})" if where else "Source text"
    return f"<p class='rule-quote'>{html.escape(label)}: “{html.escape(quote)}”</p>"


def _rule_sentence(rule: dict[str, Any]) -> str:
    if not rule:
        return "No rule is available."
    obj = _plain_label(rule.get("rule_object")) or "rule"
    value = " ".join(str(part) for part in (rule.get("value"), rule.get("unit")) if part not in (None, ""))
    direction = str(rule.get("operator") or "")
    applies = str(rule.get("applies_to") or rule.get("constraint_scope") or "").strip()
    condition = str(rule.get("condition") or "").strip()
    if direction in {"<=", "≤"}:
        lead = f"Maximum {obj} is {value}"
    elif direction in {">=", "≥"}:
        lead = f"Minimum {obj} is {value}"
    elif direction == ">":
        lead = f"{obj.title()} must be more than {value}"
    elif direction == "<":
        lead = f"{obj.title()} must be less than {value}"
    else:
        lead = f"{obj.title()} is {value}" if value else f"{obj.title()} is claimed"
    if applies:
        lead += f" for {applies}"
    if condition:
        lead += f" ({condition})"
    return lead.rstrip(" .") + "."


def _review_option_label(item: dict[str, Any]) -> str:
    if not item:
        return ""
    parts = [
        str(item.get("rule_id") or ""),
        _plain_label(item.get("rule_object")),
        " ".join(str(part) for part in (item.get("value"), item.get("unit")) if part not in (None, "")),
        _plain_label((item.get("support_gaps") or [item.get("status") or "review"])[0]),
    ]
    return " | ".join(part for part in parts if part)


def _repair_option_label(item: dict[str, Any]) -> str:
    return f"{item.get('rule_id')} | {item.get('decision_status')} | {', '.join((item.get('changed_fields') or {}).keys())}"


def _scenario_option_label(rule: dict[str, Any]) -> str:
    return " | ".join(
        part
        for part in (
            str(rule.get("rule_id") or ""),
            _plain_label(rule.get("rule_object")),
            " ".join(str(value) for value in (rule.get("operator"), rule.get("value"), rule.get("unit")) if value not in (None, "")),
        )
        if part
    )


def _review_priority(item: dict[str, Any]) -> str:
    status = str(item.get("status") or "")
    if status == "context_required":
        return "High"
    if status == "review_needed":
        return "Medium"
    return "Low"


def _gap_reason(item: dict[str, Any]) -> str:
    gaps = item.get("support_gaps") or item.get("unresolved_dependencies") or []
    if not gaps:
        return "Verifier could not prove this candidate."
    return "Verifier held this candidate because " + ", ".join(_plain_label(gap) for gap in gaps[:3]) + "."


def _score_tile(label: str, value: Any, tone: str) -> str:
    return (
        "<div class='score-tile "
        + html.escape(str(tone))
        + "'><span>"
        + html.escape(str(label))
        + "</span><b>"
        + html.escape(str(value))
        + "</b></div>"
    )


def _mini_metric(label: str, value: Any, note: str) -> str:
    return (
        "<div class='mini-card'><span>"
        + html.escape(str(label))
        + "</span><b>"
        + html.escape(str(value))
        + "</b><small>"
        + html.escape(str(note))
        + "</small></div>"
    )


def _guard_metric(label: str, value: Any) -> str:
    return "<div><span>" + html.escape(str(label)) + "</span><b>" + html.escape(str(value)) + "</b></div>"


def _quality_bar(label: str, value: Any) -> str:
    try:
        pct = max(0.0, min(float(value), 1.0)) * 100
    except (TypeError, ValueError):
        pct = 0.0
    return (
        f"<div class='quality-row'><span>{html.escape(label)}</span>"
        f"<div><i style='width:{pct:.1f}%'></i></div><b>{pct:.0f}%</b></div>"
    )


def _funnel_step(value: str, label: str, pct: str) -> str:
    return f"<div class='funnel-step'><b>{html.escape(value)}</b><span>{html.escape(pct)}</span><small>{html.escape(label)}</small></div>"


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "n/a"


def _plain_label(value: Any) -> str:
    return str(value or "").replace("_", " ").strip().title()


def _city_label(value: Any) -> str:
    text = str(value or "Burnaby R1").replace("_", " ").title()
    return text.replace("R1", "R1")


def _pretty_source_title(value: Any) -> str:
    title = str(value or "Official zoning bylaw source").strip()
    if title.lower().endswith(".pdf"):
        title = title[:-4]
    return title.replace("-", " ").replace("  ", " ")


def _style(st: Any) -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@500;600;700&display=swap');
        :root {
          --ink:#172033; --muted:#647184; --soft:#8b98a8; --line:#d9e3eb; --hair:#edf2f6;
          --panel:#ffffff; --canvas:#f4f7f9; --rail:#0d1626; --rail2:#111b2d;
          --green:#176a3b; --green-soft:#eaf7ef; --amber:#946200; --amber-soft:#fff5d9;
          --red:#b42318; --red-soft:#fff0ed; --blue:#245d91; --blue-soft:#eaf3fb;
          --shadow:0 20px 46px rgba(23,32,51,.11); --tight:0 9px 22px rgba(23,32,51,.075);
        }
        #MainMenu, footer, div[data-testid="stDecoration"] {display:none;}
        header[data-testid="stHeader"] {background:transparent;}
        html, body, .stApp, .stApp div, .stApp p, .stApp span, .stApp label, .stApp input, .stApp textarea, .stApp button {
          font-family:Manrope, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
          letter-spacing:0 !important;
        }
        .stApp {color:var(--ink); background:linear-gradient(180deg,#fbfcfd 0%, var(--canvas) 360px, #eef3f6 100%);}
        .block-container {max-width:1260px; padding:36px 2rem 58px; margin-left:0; position:relative; z-index:1;}
        section[data-testid="stSidebar"] {background:linear-gradient(180deg,var(--rail),var(--rail2)); border-right:1px solid rgba(255,255,255,.08);}
        section[data-testid="stSidebar"] * {color:#f7fafc;}
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] label {display:none;}
        section[data-testid="stSidebar"] [data-baseweb="select"] > div {
          min-height:42px; background:#182231 !important; border:1px solid rgba(255,255,255,.14) !important; border-radius:8px !important;
          box-shadow:inset 0 1px 0 rgba(255,255,255,.04);
        }
        section[data-testid="stSidebar"] [data-baseweb="select"] span,
        section[data-testid="stSidebar"] [data-baseweb="select"] div {color:#f7fafc !important;}
        .side-brand {display:flex; gap:13px; align-items:center; margin:24px 0 30px;}
        .side-brand span {display:flex; align-items:center; justify-content:center; width:40px; height:40px; border-radius:9px; border:1px solid #80d99e; background:#123922; color:white; font-family:"IBM Plex Mono", monospace !important; font-weight:800;}
        .side-brand b {font-size:15px; line-height:1.18; font-weight:800;}
        .rail-label {font-family:"IBM Plex Mono", monospace !important; font-size:11px; letter-spacing:.09em !important; text-transform:uppercase; font-weight:800; color:#aab6c5 !important; margin:20px 0 9px;}
        .rail-label.light {color:#65758b !important; margin-top:8px;}
        .source-card, .side-rule {border:1px solid rgba(255,255,255,.12); border-radius:10px; padding:14px; background:rgba(255,255,255,.05); margin:18px 0;}
        .source-card span, .side-rule span {display:block; color:#c7d0da !important; font-size:13px; line-height:1.45; margin-bottom:12px;}
        .source-card a {color:#a7f3b5 !important; font-weight:800; text-decoration:none;}
        section[data-testid="stSidebar"] div[role="radiogroup"] > label {
          min-height:42px; padding:10px 14px; border-radius:9px; margin:3px 0; color:#d9e1ea !important; font-size:14px; font-weight:700;
          border:1px solid transparent;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {background:#237b47; border-color:#58b979; color:white !important; box-shadow:0 8px 22px rgba(0,0,0,.18);}
        section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {display:none;}
        .command-topbar {display:flex; justify-content:space-between; align-items:center; gap:16px; margin-bottom:10px;}
        .eyebrow {font-family:"IBM Plex Mono", monospace !important; font-size:12px; letter-spacing:.08em !important; text-transform:uppercase; color:#617085; font-weight:800;}
        .city-chip, .health-chip {display:inline-flex; align-items:center; min-height:30px; margin-left:10px; border:1px solid var(--line); border-radius:999px; padding:5px 11px; background:white; color:#475569; font-size:12px; font-weight:800; box-shadow:0 3px 8px rgba(23,32,51,.04);}
        .health-chip::after {content:""; width:8px; height:8px; border-radius:99px; background:var(--green); margin-left:8px;}
        .page-title {font-family:Manrope, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important; font-size:42px; font-weight:800; line-height:1.06; margin:8px 0 10px; color:#111827;}
        .page-blurb {font-size:16px; color:#4c5b6d; max-width:810px; line-height:1.58; margin:0 0 14px;}
        .metric-pill-row {display:flex; flex-wrap:wrap; gap:9px; margin:14px 0 20px;}
        .metric-pill-row span {border:1px solid var(--line); border-radius:999px; background:white; padding:8px 12px; color:#526170; font-size:13px; box-shadow:0 3px 8px rgba(23,32,51,.04);}
        .metric-pill-row b {font-family:"IBM Plex Mono", monospace !important; color:#15202d; margin-right:5px;}
        .white-card, .ops-panel {position:relative; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:20px; margin:16px 0; box-shadow:var(--tight);}
        .white-card h3, .ops-panel h3 {font-size:18px; line-height:1.2; margin:0 0 14px;}
        .white-card p, .ops-panel p {color:#536273; line-height:1.55;}
        .briefing-shell {display:grid; grid-template-columns:1.42fr 1fr; gap:18px; padding:22px; margin:18px 0 16px; background:linear-gradient(135deg,#ffffff 0%,#f8fbf9 100%); border:1px solid #cfdce7; border-radius:12px; box-shadow:var(--shadow);}
        .brief-main h2 {font-size:30px; font-weight:800; margin:4px 0 8px; color:#111827;}
        .brief-main p {margin:0; color:#4d5b6d; line-height:1.5; max-width:720px;}
        .brief-kicker {font-family:"IBM Plex Mono", monospace !important; font-size:11px; letter-spacing:.08em !important; text-transform:uppercase; font-weight:800; color:var(--green);}
        .system-map {display:grid; grid-template-columns:auto 1fr auto 1fr auto 1fr auto 1fr auto; gap:8px; align-items:center; margin-top:18px;}
        .system-map span {display:flex; min-height:34px; align-items:center; justify-content:center; border:1px solid var(--line); background:#f8fafb; border-radius:9px; padding:0 10px; font-size:12px; font-weight:800; color:#334155; white-space:nowrap;}
        .system-map i {height:2px; background:linear-gradient(90deg,var(--green),var(--blue)); border-radius:99px;}
        .brief-scoreboard {display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px;}
        .score-tile {border:1px solid var(--line); border-radius:10px; padding:14px; background:#f8fafb;}
        .score-tile span {display:block; font-family:"IBM Plex Mono", monospace !important; text-transform:uppercase; letter-spacing:.06em !important; font-size:11px; font-weight:800; color:#516174;}
        .score-tile b {display:block; font-family:"IBM Plex Mono", monospace !important; font-size:28px; line-height:1; margin-top:10px; color:#13202d;}
        .score-tile.good {background:var(--green-soft); border-color:#bfdfca;} .score-tile.warn {background:var(--amber-soft); border-color:#ecd08a;} .score-tile.bad {background:var(--red-soft); border-color:#f4c8c2;}
        .brief-rail {grid-column:1 / -1; display:flex; flex-wrap:wrap; gap:10px; align-items:center; border-top:1px solid var(--hair); padding-top:14px;}
        .brief-rail a, .brief-rail span {border:1px solid var(--line); background:#f8fafb; border-radius:999px; padding:7px 11px; font-size:13px; font-weight:800; color:#425266; text-decoration:none;}
        .brief-rail a {background:#f0f8f3; color:var(--green); border-color:#c4e1cf;}
        .source-row {display:flex; justify-content:space-between; align-items:center; gap:18px;}
        .source-row span {display:block; color:var(--muted); font-size:13px; margin-top:6px;}
        .source-row small {display:block; margin-top:8px; color:#425466; line-height:1.45; max-width:620px;}
        .source-row a {color:var(--green); font-weight:750; text-decoration:none;}
        .hero-note {display:grid; grid-template-columns:95px 1fr; gap:10px; margin-top:6px; align-items:start; color:var(--ink);}
        .hero-note b {font-size:11px; text-transform:uppercase; letter-spacing:.08em; display:block; color:#4c5566;}
        .hero-note span {display:block; color:#475569; font-size:13px; line-height:1.45;}
        .card-title-row {display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:14px;}
        .card-title-text {font-family:Manrope, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important; font-size:19px; line-height:1.2; font-weight:800 !important; color:var(--ink);}
        .card-title-row [data-testid="stHeadingWithActionElements"] {margin:0;}
        .card-title-row [data-testid="stHeaderActionElements"] {display:none !important;}
        .card-title-row h3 {margin:0 !important; padding:0 !important; font-size:18px !important; line-height:1.2 !important; font-weight:800 !important;}
        .card-title-row h3 span:first-child {display:inline !important; color:var(--ink) !important; background:transparent !important; border:0 !important; padding:0 !important;}
        .card-title-row > span {font-size:12px; color:var(--green); background:var(--green-soft); border:1px solid #cfe9d6; border-radius:999px; padding:4px 10px; font-weight:800;}
        .flow-grid {display:grid; grid-template-columns:1.05fr 1fr 1fr 1fr; gap:12px; align-items:stretch; margin-top:8px;}
        .flow-total, .flow-card {border:1px solid var(--line); border-radius:8px; padding:17px; transition:transform .2s ease, border-color .2s ease, box-shadow .2s ease;}
        .flow-total span, .flow-card span {display:block; font-family:"IBM Plex Mono", monospace !important; text-transform:uppercase; font-size:11px; font-weight:800; letter-spacing:.06em !important; color:#475569;}
        .flow-total b, .flow-card b {display:block; font-family:"IBM Plex Mono", monospace !important; font-size:38px; line-height:1.02; margin:13px 0 7px;}
        .flow-card small {color:#4b5563; line-height:1.35;}
        .flow-card.good {background:var(--green-soft); border-color:#bfe7c8;} .flow-card.warn {background:var(--amber-soft); border-color:#f1d899;} .flow-card.bad {background:var(--red-soft); border-color:#ffd0ca;}
        .flow-card.good b {color:var(--green);} .flow-card.warn b {color:var(--amber);} .flow-card.bad b {color:var(--red);}
        .flow-card:hover, .mini-card:hover {transform:translateY(-2px); border-color:#adc9dd; box-shadow:0 10px 24px rgba(21,34,50,.08);}
        .flow-bar {display:flex; height:12px; overflow:hidden; border-radius:999px; margin:16px 0 10px; background:#e5e7eb;}
        .flow-bar i.good {background:var(--green);} .flow-bar i.warn {background:var(--amber);} .flow-bar i.bad {background:var(--red);}
        .flow-foot {display:flex; justify-content:space-between; color:#5f6b7a; font-size:13px;} .flow-foot b {color:var(--green);}
        .tag {float:right; background:var(--green-soft); color:var(--green); border-radius:999px; padding:4px 10px; font-size:12px;}
        .callout {background:var(--blue-soft); border:1px solid #cee1f2; border-radius:8px; padding:14px; margin-bottom:14px; color:#243b2a;}
        .tiny-note {color:#5f6b7a; font-size:13px; line-height:1.5; margin:12px 0 0;}
        .guard-grid {display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px;}
        .mini-grid {display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px;}
        .guard-grid div, .mini-card {border:1px solid var(--line); border-radius:8px; padding:14px; background:#fbfcfd; transition:transform .2s ease, border-color .2s ease;}
        .guard-grid span, .mini-card span {display:block; font-family:"IBM Plex Mono", monospace !important; text-transform:uppercase; font-size:11px; letter-spacing:.06em !important; font-weight:800; color:#526170;}
        .guard-grid b, .mini-card b {display:block; font-family:"IBM Plex Mono", monospace !important; font-size:27px; margin-top:8px;} .mini-card small {display:block; color:#667085; margin-top:5px; line-height:1.35;}
        .action-grid {display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px;} .action-grid div {background:#f8fafc; border:1px solid var(--hair); border-radius:8px; padding:15px;} .action-grid b {display:block; margin-bottom:7px;} .action-grid span {color:#5f6b7a; font-size:14px; line-height:1.45;}
        .answer-card {border:1px solid var(--line); border-radius:8px; padding:16px; margin-top:16px; background:#fbfcfd; box-shadow:inset 4px 0 0 #cbd7e3;}
        .answer-card.safe {border-color:#bfe7c8; background:var(--green-soft);}
        .answer-card.review {border-color:#f1d899; background:var(--amber-soft);}
        .answer-card.blocked {border-color:#ffd0ca; background:var(--red-soft);}
        .answer-kicker {font-family:"IBM Plex Mono", monospace !important; font-size:11px; text-transform:uppercase; letter-spacing:.08em !important; font-weight:900; color:#526170; margin-bottom:7px;}
        .answer-card h4 {font-size:17px; line-height:1.35; margin:0 0 10px;}
        .answer-detail {border-top:1px solid rgba(15,23,42,.08); padding-top:11px; margin-top:8px;}
        .answer-detail b {display:block; font-size:12px; color:#475569; margin-bottom:6px;}
        .answer-card ul {margin:0 0 12px 18px; padding:0;}
        .answer-card li {margin:6px 0; line-height:1.45;}
        .next-step, .citation-row {display:grid; grid-template-columns:82px 1fr; gap:12px; border-top:1px solid rgba(15,23,42,.1); padding-top:10px; margin-top:10px; font-size:13px; line-height:1.45;}
        .next-step b, .citation-row b {color:#425466; text-transform:uppercase; letter-spacing:.06em; font-size:11px;}
        .citation-row.muted span {color:#6b7280;}
        .rule-card {display:grid; grid-template-columns:34px 1fr; gap:12px; padding:12px 0; border-bottom:1px solid var(--hair);}
        .rule-card span {display:flex; align-items:center; justify-content:center; width:28px; height:28px; border-radius:7px; background:#eef2f6; font-family:"IBM Plex Mono", monospace !important; font-weight:800; color:#526170;}
        .rule-card p {margin:2px 0 0; font-size:15px; line-height:1.45;}
        .rule-card p.rule-quote {font-size:13px; color:#526170; font-style:italic;}
        .review-grid {display:grid; grid-template-columns:1fr 1fr; gap:16px;} .kv {display:grid; grid-template-columns:130px 1fr; border-top:1px solid var(--hair); padding:10px 0; gap:12px;} .kv b {color:#526170; font-family:"IBM Plex Mono", monospace !important; text-transform:uppercase; font-size:11px; letter-spacing:.06em !important;} .claim {font-size:17px; line-height:1.5;}
        .quality-row {display:grid; grid-template-columns:110px 1fr 44px; gap:12px; align-items:center; margin:10px 0;} .quality-row div {height:12px; background:#edf0f4; border-radius:999px; overflow:hidden;} .quality-row i {display:block; height:100%; background:var(--green);}
        .result-box {border:1px solid var(--line); border-radius:8px; padding:14px; margin:14px 0; display:grid; gap:4px;}
        .result-box.good {background:var(--green-soft); border-color:#bfe7c8;}
        .result-box.warn {background:var(--amber-soft); border-color:#f1d899;}
        .result-box.bad {background:var(--red-soft); border-color:#ffd0ca;}
        .result-box span {color:#334155; line-height:1.45;}
        .funnel-row {display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:12px 0 18px;} .funnel-step {border:1px solid var(--line); border-radius:8px; padding:15px; background:white;} .funnel-step b {font-size:28px;} .funnel-step span {margin-left:8px; color:var(--green); font-weight:800;} .funnel-step small {display:block; margin-top:8px; color:#5f6b7a;}
        div[data-testid="stDataFrame"] {border:1px solid var(--line); border-radius:8px; overflow:hidden;}
        [data-testid="stMetric"] {border:1px solid var(--line); border-radius:8px; background:white; padding:12px;}
        div.stButton > button, div.stDownloadButton > button, a[data-testid="stLinkButton"] {
          border-radius:8px !important; border:1px solid #cbd7e2 !important; background:#f8fafc !important; color:#17202a !important;
          min-height:39px; font-weight:800 !important; box-shadow:0 2px 7px rgba(16,24,40,.04);
        }
        div.stButton > button:hover, div.stDownloadButton > button:hover, a[data-testid="stLinkButton"]:hover {
          border-color:#9fb6c9 !important; background:#eef5fa !important;
        }
        input, textarea, div[data-testid="stText"] textarea {
          border:1px solid var(--line) !important; border-radius:8px !important;
        }
        @keyframes appear {
          from {opacity:0; transform:translateY(6px);}
          to {opacity:1; transform:translateY(0);}
        }
        .white-card, .briefing-shell {animation:appear .24s ease both;}
        @media (max-width: 900px) {
          .briefing-shell, .flow-grid, .guard-grid, .mini-grid, .action-grid, .review-grid, .funnel-row, .metric-pill-row {grid-template-columns:1fr;}
          .system-map {grid-template-columns:1fr;}
          .system-map i {height:18px; width:2px; margin:0 auto;}
          .flow-foot, .source-row {display:block;}
          .hero-note {grid-template-columns:1fr;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
