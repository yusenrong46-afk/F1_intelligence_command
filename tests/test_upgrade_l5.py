"""L5 checks: walkthrough pointers, exercise stubs, case-study citations, bullets."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_exercises  # noqa: E402
import check_l5_docs  # noqa: E402
import check_walkthrough  # noqa: E402


def test_committed_walkthrough_passes():
    assert check_walkthrough.check((ROOT / "docs" / "WALKTHROUGH.md").read_text(encoding="utf-8")) == []


def _ten(body: str) -> str:
    return "\n".join(f"## {i}. Q{i}?\n\n{body}\n" for i in range(1, 11))


def test_walkthrough_check_catches_missing_symbol_file_and_long_answer():
    good = "Short. Code: `scripts/run_eval.py::build_summary`"
    assert check_walkthrough.check(_ten(good)) == []
    assert any("not defined" in p for p in check_walkthrough.check(_ten("Code: `scripts/run_eval.py::no_such_fn`")))
    assert any("does not exist" in p for p in check_walkthrough.check(_ten("Code: `scripts/nope.py::x`")))
    long_answer = ("word " * 120) + good
    assert any("words" in p for p in check_walkthrough.check(_ten(long_answer)))
    assert any("no `file::symbol`" in p for p in check_walkthrough.check(_ten("No pointer here.")))
    assert any("numbered" in p for p in check_walkthrough.check(_ten(good).replace("## 10.", "## 11.")))


def test_exercise_stubs_fail_their_tests_and_import_nothing_from_src():
    folders = sorted(p for p in check_exercises.EXERCISES.iterdir() if p.is_dir() and p.name[:2].isdigit())
    assert len(folders) == 3
    for folder in folders:
        assert check_exercises.check_folder(folder) == []


def test_committed_case_study_passes():
    text = (ROOT / "docs" / "CASE_STUDY.md").read_text(encoding="utf-8")
    assert check_l5_docs.check_case_study(text) == []


def test_case_study_check_rejects_uncited_number_and_outside_source():
    text = (ROOT / "docs" / "CASE_STUDY.md").read_text(encoding="utf-8")
    uncited = text.replace("## 2. Discovery\n", "## 2. Discovery\n\nThe client loved it and saw 50% savings.\n", 1)
    assert any("uncited paragraph" in p for p in check_l5_docs.check_case_study(uncited))
    outside = text.replace("[source: docs/M7_SYSTEM_HANDOFF.md §Trust Boundary]", "[source: README.md §Results]", 1)
    assert any("not one of the four allowed" in p for p in check_l5_docs.check_case_study(outside))
    bad_section = text.replace("§Trust Boundary]", "§No Such Heading]", 1)
    assert any("no heading starts" in p for p in check_l5_docs.check_case_study(bad_section))


def test_resume_bullets_match_measured_numbers():
    assert check_l5_docs.check_resume_bullets() == []
