"""Optional Streamlit page for M7 vs M8 comparison."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from dashboard.m8_data import load_m8_output


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "outputs" / "m8_runs" / "burnaby_r1" / "local_m8"


st.set_page_config(page_title="M8 Benchmark Compare", layout="wide")
data = load_m8_output(DEFAULT_OUTPUT)
st.title("M7 vs M8")
comparison = data.get("comparison") or {}
st.json(comparison)
