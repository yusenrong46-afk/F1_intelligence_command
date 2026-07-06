"""Optional Streamlit page for M8 repair attempts."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from dashboard.m8_data import load_m8_output, repair_rows


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "outputs" / "m8_runs" / "burnaby_r1" / "local_m8"


st.set_page_config(page_title="M8 Repair Inspector", layout="wide")
data = load_m8_output(DEFAULT_OUTPUT)
st.title("M8 Repair Inspector")
st.dataframe(repair_rows(data), use_container_width=True)
