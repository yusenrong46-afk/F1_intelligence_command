"""Optional Streamlit page for M8 overview."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from dashboard.m8_data import load_m8_output, m8_metric_cards, unresolved_dependency_rows, weakest_coverage_rows


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "outputs" / "m8_runs" / "burnaby_r1" / "local_m8"


st.set_page_config(page_title="M8 Overview", layout="wide")
data = load_m8_output(DEFAULT_OUTPUT)
st.title("M8 Overview")
cols = st.columns(6)
for col, card in zip(cols, m8_metric_cards(data)):
    col.metric(card["label"], card["value"])
st.subheader("Weakest Coverage")
st.dataframe(weakest_coverage_rows(data), use_container_width=True)
st.subheader("Unresolved Dependencies")
st.dataframe(unresolved_dependency_rows(data), use_container_width=True)
