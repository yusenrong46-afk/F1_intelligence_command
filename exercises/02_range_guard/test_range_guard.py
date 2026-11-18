import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from range_guard import range_bound_gap  # noqa: E402

TABLE_TEXT = "Total Dwelling Units on a Lot: 1 to 3 Units; 4 to 6 Units"
QUALIFIED = "1 to 3 small-scale multi-unit dwelling units on a lot"


def test_lower_range_upper_bound_is_not_the_lot_maximum():
    assert range_bound_gap(3, TABLE_TEXT) is True


def test_true_maximum_passes():
    assert range_bound_gap(6, TABLE_TEXT) is False


def test_noun_after_qualifiers_still_counts():
    assert range_bound_gap(1, QUALIFIED) is True


def test_top_of_qualified_range_passes():
    assert range_bound_gap(3, QUALIFIED) is False


def test_dash_and_through_ranges():
    assert range_bound_gap(3, "1-3 units or 4-8 units") is True
    assert range_bound_gap(2, "1 through 4 storeys") is True


def test_disambiguated_scope_is_not_held():
    assert range_bound_gap(3, TABLE_TEXT, scope="rear principal building") is False


def test_range_in_another_clause_is_ignored():
    assert range_bound_gap(2, "Setbacks of 1 to 3 metres. A maximum of 2 units per lot") is False


def test_single_count_equal_to_claim_passes():
    assert range_bound_gap(4, "A maximum of 4 units per lot") is False


def test_plain_larger_count_is_held():
    assert range_bound_gap(2, "Up to 2 storeys for a rear building and 3 storeys at the front") is True
