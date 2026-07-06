"""Optional Streamlit page for M8 rule inspection."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from dashboard.m8_data import evidence_span_rows, load_m8_output, rule_explorer_rows


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "outputs" / "m8_runs" / "burnaby_r1" / "local_m8"


st.set_page_config(page_title="M8 Rule Explorer", layout="wide")
data = load_m8_output(DEFAULT_OUTPUT)
st.title("M8 Rule Explorer")
status = st.selectbox("Status", ["", "verified", "repaired_successfully", "context_required", "review_needed", "rejected", "not_used"])
st.dataframe(rule_explorer_rows(data, status=status or None), use_container_width=True)
st.subheader("Evidence Spans")
st.dataframe(evidence_span_rows(data), use_container_width=True)
