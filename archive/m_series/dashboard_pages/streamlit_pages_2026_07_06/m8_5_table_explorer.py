"""Optional Streamlit page for M8.5 table lineage."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from dashboard.m8_5_data import load_m8_5_output, table_derived_rule_rows, table_lineage_rows


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "outputs" / "m8_5_runs" / "burnaby_r1" / "local_m8_5"


st.set_page_config(page_title="M8.5 Table Explorer", layout="wide")
data = load_m8_5_output(DEFAULT_OUTPUT)
st.title("M8.5 Table Explorer")
st.subheader("Table-Derived Rule Candidates")
st.dataframe(table_derived_rule_rows(data), use_container_width=True)
st.subheader("Cell Lineage")
st.dataframe(table_lineage_rows(data), use_container_width=True)
