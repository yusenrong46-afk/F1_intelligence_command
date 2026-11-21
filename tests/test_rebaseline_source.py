"""rebaseline_source keeps page scoping and records what it replaced."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import rebaseline_source as r  # noqa: E402


def test_new_provenance_keeps_scope_and_records_old_values():
    old = {"url": "https://example.test/a.pdf", "fetched_at": "2026-06-11T00:00:00+00:00", "sha256": "aa",
           "bytes": 10, "pages": [[389, 401], [465, 478]], "pages_rationale": "why", "page_count": 1053}
    new = r.new_provenance(old, b"new bytes", 1060, "2026-11-21T00:00:00+00:00")
    assert new["pages"] == [[389, 401], [465, 478]] and new["pages_rationale"] == "why"
    assert new["bytes"] == 9 and new["page_count"] == 1060 and new["sha256"] != "aa"
    assert new["rebaselined_from"] == {"sha256": "aa", "bytes": 10, "fetched_at": "2026-06-11T00:00:00+00:00",
                                       "page_count": 1053}
    assert "rebaselined_from" not in r.new_provenance(new, b"x", 1, "t")["rebaselined_from"]


def test_evidence_page_matches_counts_only_text_on_its_cited_page():
    pages = ["Maximum height\n10.0 metres", "Front yard 6.0 metres"]
    units = [{"page": "1", "evidence_text": "maximum height 10.0 metres"},
             {"page": 2, "evidence_text": "Maximum height 10.0 metres"},
             {"page": "9", "evidence_text": "out of range"},
             {"page": None, "evidence_text": "no page"}]
    assert r.evidence_page_matches(pages, units) == (1, 2)
