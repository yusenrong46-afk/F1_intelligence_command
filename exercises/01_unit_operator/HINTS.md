# Hints: exercise 1

1. Check the family first. If it is not a key of `FAMILY_UNITS`, return
   `["family_not_in_contract"]` straight away.
2. Normalize the unit with `.strip().lower()` before looking it up.
3. Keep two small sets of operators: the ones that mean "at most" and the ones
   that mean "at least". A maximum must use an "at most" operator.
4. Append gaps to one list in the order the docstring gives, then return it.
5. Why this matters: a percent height or a flipped operator can look fine to a
   language model. In the real verifier these are critical gaps that reject the
   candidate outright.

After you finish, compare with `rule_object_unit_compatible` in
`src/burnaby_prototype/support_checks.py` and the `table_operator_refuted` gap
in `src/burnaby_prototype/decision_policy.py`.
