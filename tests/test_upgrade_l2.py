"""L2 regression tests: verified rules carry their source quote, and the
demo browser check only allows a short host list."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT, ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import demo_check  # noqa: E402
from dashboard import f1_command_center as app  # noqa: E402


class _RecordingSt:
    def __init__(self) -> None:
        self.html: list[str] = []

    def markdown(self, body: str, **_: object) -> None:
        self.html.append(body)

    def caption(self, body: str) -> None:
        self.html.append(body)


def test_rule_card_shows_escaped_source_quote() -> None:
    rule = {
        "rule_object": "height",
        "value": "11",
        "unit": "m",
        "operator": "<=",
        "citation": {"page": 3, "section_id": "101.7", "quote": "11.0 m <b>max</b>"},
    }
    st = _RecordingSt()
    app._rule_sentence_list(st, [rule])
    card = st.html[0]
    assert "class='rule-quote'" in card
    assert "page 3, section 101.7" in card
    assert "11.0 m &lt;b&gt;max&lt;/b&gt;" in card


def test_rule_card_without_quote_has_no_quote_line() -> None:
    st = _RecordingSt()
    app._rule_sentence_list(st, [{"rule_object": "height", "value": "11", "unit": "m"}])
    assert "rule-quote" not in st.html[0]


def test_every_committed_verified_rule_has_a_quote_for_the_demo() -> None:
    assert len(demo_check.verified_quotes()) > 0


def test_demo_network_allowlist_is_short_and_local_first() -> None:
    assert demo_check.host_allowed("http://localhost:8631/_stcore/health")
    assert demo_check.host_allowed("https://fonts.gstatic.com/s/x.woff2")
    assert not demo_check.host_allowed("https://openrouter.ai/api/v1/chat/completions")
    assert not demo_check.host_allowed("https://www.burnaby.ca/source.pdf")
    assert len(demo_check.ALLOWED_HOSTS) <= 5


def test_demo_command_matches_spec() -> None:
    cmd = demo_check.demo_command(8631)
    assert cmd[1:4] == ["-m", "streamlit", "run"]
    assert "streamlit_app.py" in cmd and "--server.headless" in cmd and "8631" in cmd


def test_relative_demo_out_dir_resolves_under_repo_root():
    # CI ran `demo_check.py --out docs/demo` and crashed printing the saved paths.
    out = demo_check.resolve_out(Path("docs/demo"))
    assert out == demo_check.ROOT / "docs" / "demo"
    assert out.relative_to(demo_check.ROOT) == Path("docs/demo")
    assert demo_check.resolve_out(out) == out
