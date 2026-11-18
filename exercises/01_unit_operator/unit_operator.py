"""Exercise 1: unit and operator compatibility.

A zoning-rule candidate carries a rule family (``rule_object``), a unit, an
operator and a constraint type. Some combinations can never be a real rule:

* a building height measured in percent;
* a lot coverage measured in metres;
* a constraint called "maximum" whose operator is ``>=``.

Implement :func:`check_unit_operator` so it returns the list of problems
(gap names) for one candidate, in this order: family first, then unit, then
operator. Return an empty list when the candidate is consistent.

Gap names:

* ``"family_not_in_contract"``: ``rule_object`` is not in ``FAMILY_UNITS``
  (return only this gap; nothing else can be judged);
* ``"unit_not_compatible"``: the unit is not allowed for the family;
* ``"operator_contradicts_constraint"``: a ``"maximum"`` with ``>=`` or ``>``,
  or a ``"minimum"`` with ``<=`` or ``<``.

Units are compared case-insensitively after trimming spaces.
"""

from __future__ import annotations

# Allowed units per rule family. This is data for the exercise, not the answer.
FAMILY_UNITS: dict[str, set[str]] = {
    "height": {"m", "metres", "meters"},
    "setback": {"m", "metres", "meters"},
    "lot_coverage": {"%", "percent"},
    "dwelling_units": {"units", "unit"},
    "lot_area": {"m2", "sq. m", "square metres"},
}


def check_unit_operator(rule_object: str, unit: str, operator: str, constraint_type: str) -> list[str]:
    raise NotImplementedError("exercise 1: implement check_unit_operator")
