"""Exercise 3: a mini-verifier that must reject poisoned candidates.

A candidate is a dict with ``evidence_id``, ``value`` (a string such as
``"4.5"``), ``unit`` and ``operator`` (``"<="`` or ``">="``). ``evidence_by_id``
maps evidence ids to the cited text.

Implement :func:`verify`. It returns ``(decision, gaps)``.

Gaps, checked in this order:

1. ``"source_evidence_id_not_found"``: the cited id is not in ``evidence_by_id``.
   Return ``("rejected", [that gap])`` at once.
2. ``"value_not_found_in_evidence"``: the value does not appear in the text as a
   whole number. ``"4.5"`` is not in ``"14.5 m"``, and ``"0.45"`` is not in
   ``"45 %"``.
3. ``"unit_not_found_in_evidence"``: none of the words in ``UNIT_WORDS[unit]``
   appears in the text (whole words, case-insensitive; ``%`` may touch the
   number, as in ``"40%"``). An unknown unit is never found.
4. ``"operator_not_supported"``: the text has none of the phrases in
   ``OPERATOR_PHRASES[operator]`` (case-insensitive).

Decision: ``"rejected"`` if any of gaps 1 to 3 is present (they are critical:
the text contradicts or lacks the claim); otherwise ``"review_needed"`` if any
gap is present; otherwise ``"verified"``.

Use only the standard library.
"""

from __future__ import annotations

from typing import Any

# Data for the exercise, not the answer.
UNIT_WORDS: dict[str, tuple[str, ...]] = {
    "m": ("m", "metre", "metres", "meter", "meters"),
    "%": ("%", "percent", "per cent"),
    "units": ("unit", "units"),
}
OPERATOR_PHRASES: dict[str, tuple[str, ...]] = {
    "<=": ("maximum", "must not exceed", "no more than", "up to"),
    ">=": ("minimum", "at least", "not less than"),
}
CRITICAL_GAPS = {"source_evidence_id_not_found", "value_not_found_in_evidence", "unit_not_found_in_evidence"}


def verify(candidate: dict[str, Any], evidence_by_id: dict[str, str]) -> tuple[str, list[str]]:
    raise NotImplementedError("exercise 3: implement verify")
