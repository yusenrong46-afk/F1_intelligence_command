"""Dashboard chatbot payload tests.

These catch UI-level answer-shape regressions that the lower-level chat-brain
tests cannot see. In particular: broad factual questions should not append a
single verification card from the first matching rule family.
"""

from __future__ import annotations

import importlib.util
import sqlite3
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


def _context(monkeypatch):
    app = _load_dashboard()
    monkeypatch.setattr(app, "_optional_bylaw_llm_answer", lambda *args, **kwargs: "STUB_SOURCE_ANSWER")
    monkeypatch.setattr(
        app,
        "_dashboard_rag_hits",
        lambda *args, **kwargs: [
            {
                "chunk_id": "test_chunk",
                "section": "101.4",
                "page": 2,
                "text": "Permitted Dwelling Units 1 to 6 Units. Maximum lot coverage 55%.",
                "section_text": "Permitted Dwelling Units 1 to 6 Units. Maximum lot coverage 55%.",
            }
        ],
    )
    output_dir = app.DEFAULT_OUTPUT_DIR
    data = app.load_output_data(output_dir)
    return app, FakeStreamlit(), data, app.bylaw_index_path(output_dir), app._chat_brain()


def test_broad_factual_questions_do_not_attach_single_rule_cards(monkeypatch):
    app, st, data, index_path, brain = _context(monkeypatch)
    for question in (
        "How many dwelling units are allowed?",
        "What is the minimum lot area?",
        "What is the maximum lot coverage?",
        "What is the maximum building height?",
    ):
        message = app._build_brain_answer(st, question, index_path, data, [], brain)
        assert message["intent"] == "specific_rule"
        assert message.get("sources"), question
        assert not message.get("rule_cards"), question


def test_explicit_status_questions_keep_rule_cards(monkeypatch):
    app, st, data, index_path, brain = _context(monkeypatch)
    message = app._build_brain_answer(
        st, "Is the minimum lot area of 281 m2 verified?", index_path, data, [], brain
    )
    assert message["intent"] == "why_verification"
    assert len(message.get("rule_cards") or []) == 1
    assert "verified" in message["content"].lower()


def test_review_queue_summary_has_summary_table_not_rule_card(monkeypatch):
    app, st, data, index_path, brain = _context(monkeypatch)
    message = app._build_brain_answer(
        st,
        "among the 57 in review, what is the most common reason causing this",
        index_path,
        data,
        [],
        brain,
    )
    assert message["intent"] == "why_verification"
    assert not message.get("rule_cards")
    assert [table.get("kind") for table in message.get("tables", [])] == ["review_reason_summary"]
    assert "55 of 57" in message["content"]


def test_highest_priority_review_question_selects_one_rule_not_table(monkeypatch):
    app, st, data, index_path, brain = _context(monkeypatch)
    message = app._build_brain_answer(
        st,
        "what's the one with the highest priority among those under review?",
        index_path,
        data,
        [],
        brain,
    )
    assert message["intent"] == "why_verification"
    assert "highest-priority item under review" in message["content"]
    assert not message.get("tables")
    assert len(message.get("rule_cards") or []) == 1
    assert message["selected_rule_id"] == "burnaby_r1_092"


def test_chat_context_database_has_clean_rule_counts(monkeypatch):
    app, _st, data, _index_path, _brain = _context(monkeypatch)
    db_path = app._chat_context_db_path(data)
    assert db_path is not None
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        counts = dict(conn.execute("select bucket, count(*) from rules group by bucket").fetchall())
        top = conn.execute(
            """
            select rule_id
            from rules
            where bucket = 'review'
            order by
              case lower(coalesce(priority, ''))
                when 'critical' then 0
                when 'high' then 1
                when 'medium' then 2
                when 'low' then 3
                else 9
              end,
              coalesce(priority_rank, 999999),
              rule_id
            limit 1
            """
        ).fetchone()[0]
    assert counts == {"review": 57, "verified": 87}
    assert top == "burnaby_r1_092"


def test_followup_uses_previous_selected_review_rule(monkeypatch):
    app, st, data, index_path, brain = _context(monkeypatch)
    llm_calls = {"count": 0}

    def followup_llm(prompt, *args, **kwargs):
        llm_calls["count"] += 1
        assert "SELECTED_ITEM_CONTEXT" in prompt
        assert "burnaby_r1_092" in prompt
        assert "database_fact" in prompt
        assert "REVIEW rule: All Buildings has setback" in prompt
        return "It is High priority because the selected review item has unresolved exception wording and review rank 24."

    monkeypatch.setattr(app, "_optional_bylaw_llm_answer", followup_llm)
    first = app._build_brain_answer(
        st,
        "what's the one with the highest priority among those under review?",
        index_path,
        data,
        [],
        brain,
    )
    history = [
        {"role": "user", "content": "what's the one with the highest priority among those under review?"},
        first,
    ]
    followup = app._build_brain_answer(st, "why is it high priority?", index_path, data, history, brain)
    assert followup["intent"] == "why_verification"
    assert followup["selected_rule_id"] == "burnaby_r1_092"
    assert "high" in followup["content"].lower()
    assert len(followup.get("rule_cards") or []) == 1
    assert llm_calls["count"] == 1


def test_common_definition_uses_static_glossary(monkeypatch):
    app, st, data, index_path, brain = _context(monkeypatch)
    called = {"llm": False}

    def fail_if_called(*args, **kwargs):
        called["llm"] = True
        return "SHOULD_NOT_BE_USED"

    monkeypatch.setattr(app, "_optional_bylaw_llm_answer", fail_if_called)
    message = app._build_brain_answer(st, "What is a setback?", index_path, data, [], brain)
    assert message["intent"] == "definition"
    assert "required distance between a building and a property line" in message["content"]
    assert called["llm"] is False
