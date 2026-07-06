"""Non-basic chatbot behavior at the dashboard (orchestrator) level.

These pin the upgrades that let the assistant answer questions beyond the most
basic lookup: multi-topic decomposition + balanced retrieval, conditional/meta
shaping in the grounded prompt, deterministic meta answers (counts, the
verified-vs-review distinction), and a graceful extractive fallback when the LLM
returns no text (so the dashboard never shows a raw "no LLM" disclaimer or an
empty bubble for an answerable question).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "dashboard"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _load_dashboard():
    spec = importlib.util.spec_from_file_location(
        "dashboard_streamlit_app", ROOT / "dashboard" / "streamlit_app.py"
    )
    app = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(app)
    return app


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state = {}
        self.secrets = {}


def _context(monkeypatch, llm="STUB_ANSWER"):
    app = _load_dashboard()
    monkeypatch.setattr(app, "_optional_bylaw_llm_answer", lambda *a, **k: llm)
    monkeypatch.setattr(
        app,
        "_dashboard_rag_hits",
        lambda *a, **k: [
            {
                "chunk_id": "c1",
                "section": "101.4",
                "page": 2,
                "text": "Maximum lot coverage 55%.",
                "section_text": "Maximum lot coverage 55%.",
            }
        ],
    )
    out = app.DEFAULT_OUTPUT_DIR
    return app, FakeStreamlit(), app.load_output_data(out), app.bylaw_index_path(out), app._chat_brain()


# --------------------------------------------------------------------------- #
# Plan-aware grounded prompt
# --------------------------------------------------------------------------- #

def test_grounded_prompt_multi_part_instruction(monkeypatch):
    app = _load_dashboard()
    hits = [{"section": "101.4", "page": 2, "section_text": "x"}]
    plan = {"subqueries": [{"query": "setback"}, {"query": "height"}]}
    prompt = app._grounded_bylaw_prompt("setback and height?", hits, plan=plan)
    assert "MULTIPLE parts" in prompt
    assert "Answer EVERY part" in prompt


def test_grounded_prompt_conditional_instruction(monkeypatch):
    app = _load_dashboard()
    hits = [{"section": "101.4", "page": 2, "section_text": "x"}]
    plan = {"subqueries": [{"query": "units"}], "conditional": {"op": "is", "value": "300", "raw": "300 m2"}}
    prompt = app._grounded_bylaw_prompt("if my lot is 300 m2?", hits, plan=plan)
    assert "states a condition" in prompt and "300 m2" in prompt


# --------------------------------------------------------------------------- #
# Balanced multi-query retrieval (round-robin, no starvation)
# --------------------------------------------------------------------------- #

def test_retrieve_for_plan_covers_every_subtopic(monkeypatch):
    app = _load_dashboard()

    def fake_hits(index_path, query, top_k=6, st=None):
        # each query returns its own distinct family of chunks
        return [{"chunk_id": f"{query}-{i}", "section": query, "page": i, "section_text": query} for i in range(top_k)]

    monkeypatch.setattr(app, "_dashboard_rag_hits", fake_hits)
    plan = {"retrieval_queries": ["setback", "height"], "standalone_query": "setback and height"}
    hits = app._retrieve_for_plan(FakeStreamlit(), plan, app.bylaw_index_path(app.DEFAULT_OUTPUT_DIR))
    families = {h["section"] for h in hits}
    assert "setback" in families and "height" in families  # BOTH topics represented


def test_retrieve_for_plan_single_query_uses_plain_path(monkeypatch):
    app = _load_dashboard()
    seen = {}

    def fake_hits(index_path, query, top_k=6, st=None):
        seen["query"] = query
        seen["top_k"] = top_k
        return [{"chunk_id": "x", "section": "1", "page": 1, "section_text": "t"}]

    monkeypatch.setattr(app, "_dashboard_rag_hits", fake_hits)
    plan = {"retrieval_queries": ["only one"], "standalone_query": "only one"}
    app._retrieve_for_plan(FakeStreamlit(), plan, app.bylaw_index_path(app.DEFAULT_OUTPUT_DIR))
    assert seen["query"] == "only one"
    assert seen["top_k"] == app.RAG_CHAT_TOP_K  # full budget for a single-topic question


# --------------------------------------------------------------------------- #
# Deterministic meta answers
# --------------------------------------------------------------------------- #

def test_meta_count_answer_reports_both_buckets(monkeypatch):
    app, st, data, index_path, brain = _context(monkeypatch)
    msg = app._build_brain_answer(st, "how many rules are verified and how many in review?", index_path, data, [], brain)
    assert "87" in msg["content"] and "57" in msg["content"]
    assert not msg.get("rule_cards")


def test_status_distinction_answer_uses_glossary(monkeypatch):
    app, st, data, index_path, brain = _context(monkeypatch)
    msg = app._build_brain_answer(st, "what is the difference between a verified rule and one in review?", index_path, data, [], brain)
    low = msg["content"].lower()
    assert "verified" in low and "review" in low
    assert not msg.get("rule_cards")


# --------------------------------------------------------------------------- #
# Multi-topic end-to-end + extractive fallback on empty LLM
# --------------------------------------------------------------------------- #

def test_multi_topic_question_grounded_with_sources(monkeypatch):
    app, st, data, index_path, brain = _context(monkeypatch)
    msg = app._build_brain_answer(st, "What is the setback and the maximum height for a rear principal building?", index_path, data, [], brain)
    assert msg["intent"] == "specific_rule"
    assert msg.get("sources")  # retrieval ran
    assert msg["content"] == "STUB_ANSWER"


def test_empty_llm_falls_back_to_extractive_sources(monkeypatch):
    # LLM returns no text -> the user must still get the relevant source passage,
    # quoted and cited, NOT a "no LLM key configured" disclaimer or an empty bubble.
    app, st, data, index_path, brain = _context(monkeypatch, llm="")
    msg = app._build_brain_answer(st, "What is the maximum lot coverage?", index_path, data, [], brain)
    assert "101.4" in msg["content"]
    assert "55%" in msg["content"]
    assert "no deployed LLM key" not in msg["content"].lower()
    assert msg["content"].strip()  # never empty


def test_retrieval_only_answer_is_extractive_and_cited(monkeypatch):
    app = _load_dashboard()
    hits = [{"chunk_id": "c1", "section": "541(1)", "page": 6, "section_text": "The minimum lot area is 281 square metres."}]
    out = app._retrieval_only_bylaw_answer("min lot area?", hits)
    assert "281 square metres" in out
    assert "541(1)" in out and "p.6" in out
    assert "no deployed LLM key" not in out.lower()
