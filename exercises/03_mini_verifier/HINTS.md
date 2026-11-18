# Hints: exercise 3

1. Look up the evidence first and return early if it is missing.
2. For the value, escape it with `re.escape` and surround it with
   `(?<![\d.])` and `(?![\d]|\.\d)`, so `4.5` cannot match inside `14.5` and
   `40` cannot match inside `400`. Note that `4` must not match inside `40`.
3. For units, build one pattern per word. Use `\b` around words, but not around
   `%`, because `%` is not a word character.
4. For the operator, a simple `phrase in text.lower()` is enough.
5. Collect gaps in order, then decide from them. Keep the decision a pure
   function of the gaps: that is what makes the real verifier auditable.
6. Why this matters: every candidate in `POISONED` is the kind of thing a
   language model can propose with full confidence. The verifier is the only
   authority, so it must say no.

After you finish, compare with `contains_value` in
`src/burnaby_prototype/support_checks.py` and `verification_decision_from_gaps`
in `src/burnaby_prototype/decision_policy.py`.
