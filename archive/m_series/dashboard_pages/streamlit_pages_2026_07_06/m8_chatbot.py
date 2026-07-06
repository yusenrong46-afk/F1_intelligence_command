"""Optional Streamlit page for M8 analytic chatbot."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from burnaby_prototype.m8.chatbot.analyst_tools import answer_m8_question, load_chatbot_context


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "outputs" / "m8_runs" / "burnaby_r1" / "local_m8"


st.set_page_config(page_title="M8 Chatbot", layout="wide")
st.title("M8 Analytic Chatbot")
context = load_chatbot_context(DEFAULT_OUTPUT)
question = st.text_input("Question", "Did M8 preserve the M7 zero-false-verified guarantee?")
if question:
    st.write(answer_m8_question(question, context))
