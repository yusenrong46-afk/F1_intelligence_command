"""Optional Streamlit page for M8.5 repair evaluation."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from dashboard.m8_5_data import load_m8_5_output, repair_evaluation_rows


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "outputs" / "m8_5_runs" / "burnaby_r1" / "local_m8_5"


st.set_page_config(page_title="M8.5 Repair Workbench", layout="wide")
data = load_m8_5_output(DEFAULT_OUTPUT)
st.title("M8.5 Repair Workbench")
st.dataframe(repair_evaluation_rows(data), use_container_width=True)
