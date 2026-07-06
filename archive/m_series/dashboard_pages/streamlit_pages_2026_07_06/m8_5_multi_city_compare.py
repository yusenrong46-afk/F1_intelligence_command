"""Optional Streamlit page for M8.5 comparison metrics."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from dashboard.m8_5_data import comparison_metric_rows, coverage_rows, load_m8_5_output, m8_5_metric_cards, status_count_rows


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "outputs" / "m8_5_runs" / "burnaby_r1" / "local_m8_5"


st.set_page_config(page_title="M8.5 Compare", layout="wide")
data = load_m8_5_output(DEFAULT_OUTPUT)
st.title("M8.5 Compare")
cards = m8_5_metric_cards(data)
cols = st.columns(4)
for index, card in enumerate(cards):
    cols[index % 4].metric(card["label"], card["value"])
st.subheader("Status Counts")
st.dataframe(status_count_rows(data), use_container_width=True)
st.subheader("Metric States")
st.dataframe(comparison_metric_rows(data), use_container_width=True)
st.subheader("Coverage By Rule Type")
st.dataframe(coverage_rows(data, "coverage_by_rule_type"), use_container_width=True)
st.subheader("Coverage By Source Type")
st.dataframe(coverage_rows(data, "coverage_by_table_vs_prose_source"), use_container_width=True)
