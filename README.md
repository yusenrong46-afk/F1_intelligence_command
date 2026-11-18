# Bylaw rule verification

Turns municipal zoning bylaw PDFs into source-checked rules for planners and GIS
teams: an LLM proposes rules, and a deterministic verifier promotes only the ones
the bylaw text actually supports.

**Result (measured 2026-11-18):** across Burnaby, Calgary and Vancouver, 126 rules
are verified with verified precision 1.00 and 0 false-verified rules against the
gold benchmarks.

![M7 safety check: precision 1.00, 0 false verified, per-city verified and review counts](docs/M7_VALIDATION_SAFETY_RESULTS.png)

**See it:** `make setup && make demo`, then open http://localhost:8631. No account,
no API key, no cost.

This began as a client-sponsored UBC Master of Data Science capstone for Green
Metrics Technology, built by a four-person team. Thomas (Yusen) Rong led
verification. "F1" is his own continuation of the work after the capstone.

## Results

<!-- results:start -->
| City | Candidates | Verified | Review | Verified precision | False verified | Coverage recall |
|---|---:|---:|---:|---:|---:|---:|
| Burnaby R1 | 144 | 87 | 57 | 1.00 | 0 | 0.97 |
| Calgary R-CG | 150 | 29 | 42 | 1.00 | 0 | 1.00 |
| Vancouver RS | 56 | 10 | 31 | 1.00 | 0 | 1.00 |
<!-- results:end -->

Numbers come from the committed M7 run artifacts in `outputs/m7_runs/`
(restored byte-for-byte from the dashboard repo; see
[MANIFEST.sha256](outputs/m7_runs/MANIFEST.sha256)).

## How it works

```text
Extraction proposes.  Verification proves.  GIS consumes only verified rules.
```

Every candidate field (object, value, unit, operator, scope, applies-to,
condition, exception) is checked against cited evidence. Anything incomplete,
ambiguous or contradicted goes to review or is rejected; no confidence score or
model flag can promote a rule. Details: [docs/M7_VERIFICATION_MECHANISM.md](docs/M7_VERIFICATION_MECHANISM.md).

## Commands

```bash
make setup          # Python 3.12 venv and dependencies
make fetch-sources  # official bylaw PDFs, SHA-256 checked against provenance.json
make test           # full test suite
make demo           # command center on http://localhost:8631
make gate-l1        # the portfolio-standard gate for this level
```

Tests that need a bylaw PDF skip with the reason
`source PDF not fetched (run make fetch-sources)` until you fetch the sources.

## More

- [Project guide](docs/PROJECT_GUIDE.md): the full former README (outputs,
  decision buckets, layout, advisory-only modules, guardrails).
- [Documentation index](docs/README.md) and the M7 release story in
  [docs/M7_FINAL_RELEASE.md](docs/M7_FINAL_RELEASE.md).
- [Upgrade status](upgrade/STATUS.md): what this branch adds and how each gate was checked.
