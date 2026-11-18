import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unit_operator import check_unit_operator  # noqa: E402


def test_consistent_height_rule_has_no_gaps():
    assert check_unit_operator("height", "m", "<=", "maximum") == []


def test_height_in_percent_is_incompatible():
    assert check_unit_operator("height", "%", "<=", "maximum") == ["unit_not_compatible"]


def test_lot_coverage_in_metres_is_incompatible():
    assert check_unit_operator("lot_coverage", "m", "<=", "maximum") == ["unit_not_compatible"]


def test_units_compared_case_insensitively():
    assert check_unit_operator("setback", " Metres ", ">=", "minimum") == []


def test_maximum_with_greater_or_equal_contradicts():
    assert check_unit_operator("height", "m", ">=", "maximum") == ["operator_contradicts_constraint"]


def test_minimum_with_less_than_contradicts():
    assert check_unit_operator("setback", "m", "<", "minimum") == ["operator_contradicts_constraint"]


def test_both_problems_reported_in_order():
    assert check_unit_operator("height", "%", ">=", "maximum") == [
        "unit_not_compatible",
        "operator_contradicts_constraint",
    ]


def test_unknown_family_reports_only_contract_gap():
    assert check_unit_operator("floor_space_ratio", "%", ">=", "maximum") == ["family_not_in_contract"]
