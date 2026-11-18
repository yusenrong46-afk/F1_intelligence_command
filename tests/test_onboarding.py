"""Onboarding kit (make onboard) tests on a synthetic PDF, in a temporary root.

The dry-run step is replaced by a stub here (it is exercised for real by
`make onboard` in CI); every other step runs as written.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import fetch_bylaw  # noqa: E402
import onboard_city  # noqa: E402
from pdf_fixture import make_pdf  # noqa: E402

PAGES = [
    ["Chapter 5 General"],
    ["10.20 Residential Detached Zone RD", "10.20.40.10 The permitted maximum height of a building is 10.0 metres."],
    ["10.20.40.70 The required minimum front yard setback is 6.0 metres."],
    ["Chapter 15 Other"],
]


@pytest.fixture()
def root(tmp_path: Path, monkeypatch) -> Path:
    (tmp_path / "configs").mkdir()
    shutil.copy(ROOT / "configs" / "_template.json", tmp_path / "configs" / "_template.json")
    (tmp_path / "benchmark" / "gold").mkdir(parents=True)
    (tmp_path / "scripts").symlink_to(ROOT / "scripts")
    monkeypatch.setattr(onboard_city, "ROOT", tmp_path)
    monkeypatch.setattr(fetch_bylaw, "ROOT", tmp_path)
    monkeypatch.setattr(onboard_city, "dry_run", lambda city, out, found: ("PASS", "stubbed in tests"))
    return tmp_path


def _files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and not p.is_relative_to(root / "scripts")}


def test_new_city_from_config_only(root: Path, tmp_path_factory) -> None:
    pdf = tmp_path_factory.mktemp("src") / "bylaw.pdf"
    pdf.write_bytes(make_pdf(PAGES))
    before = _files(root)
    code = onboard_city.main([
        "--city", "toyville_rd", "--url", pdf.as_uri(), "--pages", "2-3",
        "--locate", "Residential Detached", "--name", "Toyville", "--zone", "RD", "--bylaw", "Toy By-law 1",
    ])
    assert code == 0
    created = _files(root) - before
    # Onboarding may touch only configs/, the city's provenance (and its gitignored
    # PDF and .gitignore), outputs/onboarding/ and *.DRAFT.json.
    allowed = ("configs/", "data/bylaws/", "outputs/onboarding/toyville_rd/", "benchmark/gold/toyville_rd_gold_rules.DRAFT.json")
    assert created and all(path.startswith(allowed) for path in created), created
    provenance = json.loads((root / "data/bylaws/toyville_rd/provenance.json").read_text())
    assert provenance["pages"] == [2, 3]
    assert provenance["sha256"] == hashlib.sha256(pdf.read_bytes()).hexdigest()
    config = json.loads((root / "configs/toyville_rd.json").read_text())
    assert config["city"] == "Toyville" and config["source_url"] == pdf.as_uri()
    summary = json.loads((root / "outputs/onboarding/toyville_rd/onboarding_summary.json").read_text())
    assert summary["locate_pages"] == [2]
    statuses = {s["step"]: s["status"] for s in summary["steps"]}
    assert statuses == {
        "config": "PASS", "source": "PASS", "validate_config": "PASS", "locate": "PASS",
        "page_text": "PASS", "dry_run": "PASS", "gold_draft": "PASS",
    }
    assert all(isinstance(s["seconds"], float) for s in summary["steps"])
    text = (root / "outputs/onboarding/toyville_rd/source_pages.txt").read_text()
    assert "===== page 2 =====" in text and "page 4" not in text
    draft = json.loads((root / "benchmark/gold/toyville_rd_gold_rules.DRAFT.json").read_text())
    assert draft["label_source"] == "agent_draft_unreviewed" and draft["status"] == "exploratory"
    report = (root / "outputs/onboarding/toyville_rd/ONBOARDING_REPORT.md").read_text()
    for needle in ("exploratory", provenance["sha256"], "| dry_run | PASS |", "NOT RUN", "Roll back"):
        assert needle in report


def test_drifted_source_never_rewrites_provenance(root: Path, tmp_path_factory) -> None:
    pdf = tmp_path_factory.mktemp("src") / "bylaw.pdf"
    pdf.write_bytes(make_pdf(PAGES))
    city_dir = root / "data" / "bylaws" / "drift_rd"
    city_dir.mkdir(parents=True)
    provenance = {"url": pdf.as_uri(), "sha256": "0" * 64, "pages": [2, 3]}
    (city_dir / "provenance.json").write_text(json.dumps(provenance))
    before = (city_dir / "provenance.json").read_bytes()
    code = onboard_city.main(["--city", "drift_rd"])
    assert code == 1
    assert (city_dir / "provenance.json").read_bytes() == before
    assert not (city_dir / "source.pdf").exists()
    summary = json.loads((root / "outputs/onboarding/drift_rd/onboarding_summary.json").read_text())
    statuses = {s["step"]: s["status"] for s in summary["steps"]}
    assert statuses["source"] == "FAIL" and statuses["dry_run"] == "NOT RUN" and statuses["page_text"] == "NOT RUN"


def test_locate_pages_suggests_the_largest_run(tmp_path: Path) -> None:
    import locate_pages

    pdf = tmp_path / "bylaw.pdf"
    pdf.write_bytes(make_pdf(PAGES))
    assert locate_pages.matching_pages(pdf, r"^10\.20\.") == [2, 3]
    assert locate_pages.largest_run([2, 3, 4, 9, 30, 31], max_gap=1) == (2, 4)
    assert locate_pages.largest_run([5, 7, 8], max_gap=1) == (5, 8)
    assert locate_pages.largest_run([], max_gap=1) is None


def test_draft_gold_quote_check_catches_invented_quotes_and_values():
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_draft_gold_quotes as q  # noqa: PLC0415

    pages = q.parse_pages("===== page 7 =====\nThe maximum height of a\nbuilding is 10.0 metres.\n===== page 8 =====\nOther text.\n")
    rule = {"gold_id": "t1", "rule_object": "height", "constraint_type": "max", "value": "10.0", "unit": "m",
            "operator": "<=", "source_page": 7, "quote": "maximum height of a building is 10.0 metres",
            "label_source": "agent_draft_unreviewed"}
    draft = {"label_source": "agent_draft_unreviewed", "rules": [rule]}
    assert q.check(draft, pages) == []
    assert any("not found on page 8" in p for p in q.check({**draft, "rules": [{**rule, "source_page": 8}]}, pages))
    assert any("does not occur" in p for p in q.check({**draft, "rules": [{**rule, "value": "12.0"}]}, pages))
    assert any("fewer than" in p for p in q.check(draft, pages, min_rules=30))
    assert any("label_source" in p for p in q.check({**draft, "rules": [{**rule, "label_source": "human"}]}, pages))
    two = {**rule, "value": "2", "quote": "may have no more than two storeys"}
    pages2 = q.parse_pages("===== page 7 =====\nthe building may have no more than two storeys; at least 2,000 square metres\n")
    assert q.check({**draft, "rules": [two, {**two, "gold_id": "t2", "value": "2000", "quote": "at least 2,000 square metres"}]}, pages2) == []
