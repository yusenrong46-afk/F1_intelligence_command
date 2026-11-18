# Hints: exercise 2

1. Handle the scope first: split it into lower-case words and return `False` if
   any is a disambiguator.
2. Two regular expressions are enough: one for a plain count
   (`number` then `units?|storeys?`) and one for a range (`low`, a separator, `high`).
3. For the range, check the noun with a lookahead that cannot cross a clause
   break: `(?=[^.;:\n]{0,40}\b(?:units?|storeys?|dwellings?)\b)`. The `[^.;:\n]`
   is what stops `"1 to 3 metres. 2 units"` from matching.
4. Collect every number you found (plain counts and range high ends) and compare
   with `claimed`.
5. Why this matters: this exact bug let a lower bound through in M7. The fix
   was the bounded lookahead; the original pattern needed the noun right after
   the number.

After you finish, compare with `_UNIT_RANGE_IN_TEXT_RE` and
`evidence_shape_gaps` in `src/burnaby_prototype/decision_policy.py`, and the
`RangeLowerBoundNotMaximumTests` in `tests/test_adversarial_hardening.py`.
