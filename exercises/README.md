# Exercises

Three small, stand-alone exercises on the ideas that keep this verifier safe.
Each folder has a stub with `NotImplementedError`, a test file that fails until
you implement the stub, and `HINTS.md`. Nothing here imports the project's
`src/` code, so you can copy a folder anywhere. There are no solutions in the
repository; the real implementations are pointed to at the end of each hint file
for after you finish.

| Folder | You write | Idea |
|---|---|---|
| `01_unit_operator/` | `check_unit_operator` | A height in percent, or a "maximum" with `>=`, can never be a valid rule. |
| `02_range_guard/` | `range_bound_gap` | "1 to 3 units" is a range, never "maximum 3" when "4 to 6 units" is also listed. |
| `03_mini_verifier/` | `verify` | A plausible candidate whose value is not in its cited evidence must be rejected. |

Run one exercise from the repository root:

```bash
.venv/bin/python -m pytest -q exercises/01_unit_operator
```

`make exercises-check` confirms that every exercise test still fails on the
unsolved stub (so nobody commits a solution by accident).
