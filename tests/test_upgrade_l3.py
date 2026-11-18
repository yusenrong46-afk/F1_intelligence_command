"""L3 regression tests: eval summary, generated README block, baseline guard."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_eval_baseline  # noqa: E402
import render_results  # noqa: E402

SUMMARY = json.loads((ROOT / "outputs" / "eval_summary.json").read_text(encoding="utf-8"))
BASELINE = json.loads((ROOT / "benchmark" / "eval_baseline.json").read_text(encoding="utf-8"))


def test_committed_summary_passes_the_baseline() -> None:
    assert check_eval_baseline.check(SUMMARY, BASELINE) == []


def test_summary_covers_34_poisoned_cases_and_3_bundles() -> None:
    assert SUMMARY["totals"]["adversarial_cases"] == 34
    assert SUMMARY["totals"]["adversarial_bundles"] == 3
    assert SUMMARY["model_calls"] == 0


@pytest.mark.parametrize(
    ("path", "value", "needle"),
    [
        (("benchmark", "false_verified_count"), 1, "false verified"),
        (("benchmark", "verified_precision"), 0.98, "verified precision"),
        (("adversarial", "bundle_leaked"), 1, "adversarial leaked"),
        (("benchmark", "extraction_coverage_recall"), 0.95, "coverage recall"),
        (("benchmark", "verified_rule_count"), 88, "verified count"),
        (("benchmark", "review_rule_count"), 56, "review count"),
    ],
)
def test_guard_fails_when_a_guarded_number_regresses(path, value, needle) -> None:
    regressed = copy.deepcopy(SUMMARY)
    regressed["cities"]["burnaby_r1"][path[0]][path[1]] = value
    problems = check_eval_baseline.check(regressed, BASELINE)
    assert len(problems) == 1 and needle in problems[0]


def test_readme_block_is_generated_from_the_summary() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    meta = json.loads((ROOT / "outputs" / "eval_summary.meta.json").read_text(encoding="utf-8"))
    assert render_results.render(readme, SUMMARY, meta["measured_on"]) == readme


def test_check_docs_detects_a_hand_edited_number(tmp_path: Path) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8").replace("| 87 |", "| 88 |", 1)
    (tmp_path / "README.md").write_text(readme, encoding="utf-8")
    code = render_results.main(["--readme", str(tmp_path / "README.md"), "--check"])
    assert code == 1
