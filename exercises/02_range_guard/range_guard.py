"""Exercise 2: a count range is not a maximum.

Zoning tables often list counts as ranges by building type, and an extractor
that flattens the table to text sees "1 to 3 Units; 4 to 6 Units". If it then
proposes ``dwelling_units <= 3`` for the whole lot, it has read one range's
upper bound as the lot maximum (the real maximum is 6).

Implement :func:`range_bound_gap`. Return ``True`` (hold this candidate for
review) when the evidence mentions a count of units or storeys that is larger
than ``claimed``, and ``False`` otherwise. A count can appear as:

* a plain count: ``"4 units"``, ``"2 storeys"``;
* a range: ``"4 to 6 units"``, ``"4-6 units"``, ``"4 through 6 units"`` (use the
  high end). The unit noun may come a few words after the range
  (``"1 to 3 small-scale multi-unit dwelling units"``), but never across a
  clause break (``.``, ``;``, ``:`` or a newline): in ``"1 to 3 metres. 2 units"``
  the ``1 to 3`` is not a unit count.

If ``scope`` contains a word that names which building or yard the rule is for
(``front``, ``rear``, ``side``, ``accessory``, ``corner``), the claim is already
disambiguated: return ``False``.

Matching is case-insensitive. Use only the standard library.
"""

from __future__ import annotations


def range_bound_gap(claimed: int, evidence_text: str, scope: str = "lot") -> bool:
    raise NotImplementedError("exercise 2: implement range_bound_gap")
