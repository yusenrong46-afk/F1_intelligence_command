import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mini_verifier import verify  # noqa: E402

EVIDENCE = {
    "e1": "The minimum front yard setback is 4.5 m.",
    "e2": "Lot coverage must not exceed 40% of the lot area.",
    "e3": "The minimum rear yard setback is 14.5 metres.",
    "e4": "Floor area must not exceed 45 % of the site.",
}


def cand(evidence_id, value, unit, operator):
    return {"evidence_id": evidence_id, "value": value, "unit": unit, "operator": operator}


def test_supported_setback_verifies():
    assert verify(cand("e1", "4.5", "m", ">="), EVIDENCE) == ("verified", [])


def test_supported_coverage_verifies():
    assert verify(cand("e2", "40", "%", "<="), EVIDENCE) == ("verified", [])


def test_unit_word_metres_counts_for_m():
    assert verify(cand("e3", "14.5", "m", ">="), EVIDENCE) == ("verified", [])


def test_missing_evidence_is_rejected():
    assert verify(cand("e9", "4.5", "m", ">="), EVIDENCE) == ("rejected", ["source_evidence_id_not_found"])


def test_value_hidden_inside_a_larger_number_is_rejected():
    assert verify(cand("e3", "4.5", "m", ">="), EVIDENCE) == ("rejected", ["value_not_found_in_evidence"])


def test_decimal_ratio_is_not_a_percent():
    assert verify(cand("e4", "0.45", "%", "<="), EVIDENCE) == ("rejected", ["value_not_found_in_evidence"])


def test_wrong_unit_is_rejected():
    assert verify(cand("e1", "4.5", "%", ">="), EVIDENCE) == ("rejected", ["unit_not_found_in_evidence"])


def test_flipped_operator_is_held_for_review():
    assert verify(cand("e1", "4.5", "m", "<="), EVIDENCE) == ("review_needed", ["operator_not_supported"])


POISONED = [
    pytest.param(cand("e1", "9.9", "m", ">="), id="value-not-in-evidence"),
    pytest.param(cand("e2", "4", "%", "<="), id="value-inside-40"),
    pytest.param(cand("e2", "40", "m", "<="), id="coverage-in-metres"),
    pytest.param(cand("e3", "14.5", "m", "<="), id="minimum-read-as-maximum"),
    pytest.param(cand("missing", "40", "%", "<="), id="invented-evidence-id"),
]


@pytest.mark.parametrize("candidate", POISONED)
def test_poisoned_candidate_never_verifies(candidate):
    decision, gaps = verify(candidate, EVIDENCE)
    assert decision != "verified"
    assert gaps
