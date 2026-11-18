# Upgrade status: P1 bylaw rule verification

Branch `upgrade/2026-11`, based on `main` at `8ecab50`. Spec: `upgrade/SPEC.md`.
Every PASS below carries the command that was run in this session and the
output line that shows it.

## Gates

| Gate | Status | Evidence |
|---|---|---|
| Preflight baseline | PASS (matches expected) | see Preflight |
| L1 Reachable | NOT STARTED | |
| L2 Demonstrable | NOT STARTED | |
| L3 Measured | NOT STARTED | |
| L4 Connectable | NOT STARTED | |
| L5 Explainable | NOT STARTED | |

## Preflight

Python 3.12.3 venv, `pip install -r requirements.txt && pip install -e . --no-build-isolation`, `pytest -q`.

- Expected on 2026-11-18: 669 passed, 20 failed, 23 skipped.
- Measured: `20 failed, 669 passed, 23 skipped in 7.09s`. Matches.
- Note: on a fresh Python 3.12 venv, `pip install -e . --no-build-isolation`
  fails with `ModuleNotFoundError: No module named 'setuptools'` until
  setuptools is installed first. `make setup` installs it.

## Decisions

## Findings

## Needs Thomas
