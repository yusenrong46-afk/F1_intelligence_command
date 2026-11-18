# Project guide (the full former README)

> Moved here from the repository README on 2026-11-18 so the README's first
> screen can stay short. Commands that failed on a clean clone were fixed or
> removed; each change is noted inline. Short version: see `../README.md`.

## F1 Bylaw Intelligence Command Center

F1 is the current product generation after the M-series research track. It turns
municipal bylaw documents into source-backed rules, review workflows,
GIS-ready constraints, compliance decisions, and an open-ended RAG chatbot.

Start here for F1:

```text
docs/F1_CONSTITUTION.md
docs/F1_ENGINEERING_PLAN.md
docs/F1_ARTIFACT_CONTRACTS.md
F1_TEXTBOOK.ipynb
```

The F1 checkpoints under `outputs/f1_runs/` are committed history. (Removed
2026-11-18: the former `run_f1_checkpoint.py --run-id checkpoint_0` command
rewrote that committed history and exited 1 on a clean clone.)

The M-series remains reproducible as the research record that F1 builds from.
See:

```text
archive/m_series/README.md
```

## Verification Heritage

This project verifies zoning rules extracted from municipal bylaws before they
can be used downstream by GIS or map dashboards.

The core boundary is unchanged:

```text
Extraction proposes.
RAG/discovery finds source context.
Source repair restores evidence context.
Deterministic verification decides.
GIS consumes only verified rules.
```

The final release phase is **M7**. M7 packages the consolidated matrix-aware
extraction pipeline (on `google/gemini-3.1-flash-lite`), the M7 scored
measurement layer, and the 4-tab Civic Console dashboard into one reproducible
handoff. The product verification path is full-bylaw source discovery plus
RAG/evidence packs, matrix-aware native extraction, source repair, and
deterministic verification. Pipeline 5 and Pipeline 9 are historical names for
shared upstream code, not separate product lanes. Every extraction path feeds
the same verifier contract: `rule_candidates` plus `evidence_units`.
Re-anchoring, RAG, SQLite, and LLM/examiner tools are support layers only; none
of them can promote a rule.

## Safety Contract

The core rule is simple:

```text
Extraction proposes.
Verification proves.
GIS consumes only verified rules.
```

No upstream confidence score, `review_required=false` flag, or extraction
label ever promotes a candidate.

The verifier checks each candidate field against cited evidence:

```text
rule_object, value, unit, operator, scope, applies_to, condition, exception
```

If evidence is incomplete, ambiguous, contradicted, or outside the current
verification contract, the rule is not promoted to `verified_rules.json`.

## Current Results

M7 release status, the per-city before/after story, scored coverage, and the C5
verifier-recall finding are documented in:

```text
docs/M7_FINAL_RELEASE.md
```

The current release gate uses `extraction_coverage_recall` /
`release_candidate_recall`, not raw candidate artifact recall. Raw candidate
artifact recall remains diagnostic because rules can move directly into
verified, review, rejected, or not-used output buckets after extraction.

The current product run (M7, `google/gemini-3.1-flash-lite`) is evaluated by:

```bash
.venv/bin/python benchmark/evaluate_benchmark.py --city burnaby_r1 --output-dir outputs/m7_runs/burnaby_r1/google_gemini_3_1_flash_lite --report-dir outputs/eval/burnaby_r1
```

`--report-dir` (added 2026-11-18) keeps the committed run artifacts
byte-identical to `outputs/m7_runs/MANIFEST.sha256`. Without it the evaluator
rewrites `benchmark_report.*` inside the run directory.

M7 per-city benchmark status (from
`outputs/m7_runs/<city>/google_gemini_3_1_flash_lite/benchmark_report.json`):

| City | Verified | Review | Coverage recall | Verified precision | False verified | Source-support failures | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Burnaby R1 | 87 | 57 | 0.975 | 1.000 | 0 | 0 | pass |
| Calgary RCG | 29 | 42 | 1.000 | 1.000 | 0 | 0 | pass |
| Vancouver RS | 10 | 31 | 1.000 | 1.000 | 0 | 0 | pass |

(Calgary corrected on 2026-11-18 from a stale 30 / 41 to the committed 29 / 42.
The generated table in `../README.md` is the current source of truth.)

The Burnaby proposal benchmark holds `proposal_decision_accuracy = 1.0` and
`false_approval_count = 0`.

This is a safety-ready verification story, not a claim that every possible
municipal rule has been extracted. The verifier is fail-closed with zero false
verified rules in all benchmarked cities. Remaining work is recall and review
efficiency, not loosening the verifier.

## Quick Start

From this folder:

```bash
make setup        # Python 3.12 venv, setuptools, requirements, editable install
make fetch-sources  # optional: official bylaw PDFs, SHA-256 checked against provenance.json
make test
```

`make setup` installs `setuptools` before `pip install -e . --no-build-isolation`;
on a fresh Python 3.12 venv the bare command fails without it.

Build the M7 status report, then print it (`status` needs the report first):

```bash
.venv/bin/python scripts/run_consolidated_prototype.py report
.venv/bin/python scripts/run_consolidated_prototype.py status
```

Run the current extraction/discovery path without an LLM call (needs the
source PDF: run `make fetch-sources` first):

```bash
.venv/bin/python scripts/run_m7_bakeoff.py --city calgary_rcg --models google/gemini-3.1-flash-lite --dry-run
```

Run extraction with full-bylaw discovery and verification. This makes paid
model calls (needs `OPENROUTER_API_KEY` and the source PDF). Recipe:
`make extract CITY=<city> CONFIRM_PAID=yes`, which writes to
`outputs/extract_runs/` so the committed `outputs/m7_runs/` stays untouched.
Budget: the recorded M7 runs cost US$0.014857 (Burnaby), US$0.044801 (Calgary)
and US$0.032056 (Vancouver) per `model_cost_report.json` (estimated from
character counts; OpenRouter billing is authoritative). Status on 2026-11-18:
NOT RUN on this branch.

```bash
.venv/bin/python scripts/run_m7_bakeoff.py --city burnaby_r1 --models google/gemini-3.1-flash-lite
```

Run the main verifier directly:

```bash
.venv/bin/python scripts/run_slim_verifier.py --city burnaby_r1 \
  --native-extraction outputs/m7_runs/burnaby_r1/google_gemini_3_1_flash_lite \
  --output-dir outputs/reverify/burnaby_r1
.venv/bin/python benchmark/evaluate_benchmark.py --city burnaby_r1 \
  --output-dir outputs/reverify/burnaby_r1 --report-dir outputs/reverify/burnaby_r1
```

(Changed 2026-11-18: the bare `run_slim_verifier.py --city burnaby_r1` needs a
teammate's Pipeline 5 `final_rule_registry.json`, which is not in this repo, and
raised FileNotFoundError. The command above re-verifies the committed M7
candidates and evidence into a scratch directory.)

Run the M7 measurement layer (scored legal-slot coverage). Removed from the
README on 2026-11-18: on a clean clone it writes `outputs/m7_measure/` and exits 1
because the Burnaby benchmark quality gate `proposal_field_expectations_match`
fails against the M7 artifacts (see `upgrade/STATUS.md`, Findings):

```bash
.venv/bin/python scripts/run_m7_measure.py --run-id m7_gemini31_20260616 --changed-component m7_matrix_pipeline_gemini_3_1 --model google/gemini-3.1-flash-lite --overwrite
```

A refresh variant reuses existing extraction artifacts and refreshes only the
deterministic verifier (`--refresh-verifier`), so it improves proof traces
without a new LLM call. GIS-facing exports deduplicate exact source-aware
duplicate verified rows; the raw audit trail remains `verified_rules.json`.

"Pipeline 5" and "Pipeline 9" are historical names for shared upstream code,
not separate product paths.

Run the test suite:

```bash
.venv/bin/python -m pytest -q
```

Run the local dashboard:

```bash
make demo   # streamlit on http://localhost:8631, no API key needed
```

For Streamlit Cloud, set the app entrypoint to `streamlit_app.py` (repo root).

## Main Outputs

Current M7 product outputs are written to:

```text
outputs/m7_runs/<city>/google_gemini_3_1_flash_lite/
```

The most important files are:

```text
verified_rules.json          source-supported rules only
review_needed.json           plausible but incomplete or ambiguous rules
rejected_rules.json          contradicted or unsafe malformed candidates
not_used.json                traceability-only or out-of-contract candidates
gis_rule_contract.json       slim verified-only, deduplicated GIS contract
gis_felt_export.json         richer deduplicated map/dashboard export from verified rules
benchmark_report.md          readable benchmark result
validation_report.json       compact dashboard-ready run summary
```

Downstream GIS should consume only:

```text
gis_rule_contract.json
```

`gis_felt_export.json` is a convenience projection for map dashboards. It is
derived only from verified rules.

## Decision Buckets

```text
verified
```

All required claims are supported by cited evidence.

```text
review_needed
```

The candidate may be correct, but scope, condition, exception, operator, or
evidence context is incomplete.

```text
rejected
```

The candidate has a hard contradiction or unsafe malformed field, such as a
wrong value, incompatible unit, missing evidence ID, or refuted operator.

```text
not_used
```

The candidate is useful for traceability but outside the active verification or
GIS contract, such as a cross-reference or administrative/process rule.

## Project Layout

```text
benchmark/      gold rules, proposal cases, evaluators, adversarial tests
configs/        city/zone config; vocabulary only, not answer keys
dashboard/      Streamlit review and export dashboard
docs/           concise architecture and output documentation
outputs/        reproducible demo outputs
archive/        pre-M7 records and historical comparison artifacts
schemas/        JSON schemas for verified exports
scripts/        CLI entrypoints and post-processing tools
src/            adapter, verifier, proof, triage, and export code
tests/          unit tests for verifier, adapters, exports, and safety gates
```

For the consolidated handoff map, see:

```text
docs/M7_SYSTEM_HANDOFF.md
docs/M7_PROJECT_STRUCTURE.md
```

For folder-level navigation, see:

```text
docs/README.md
scripts/README.md
src/burnaby_prototype/README.md
outputs/README.md
```

## What Is Advisory Only

These modules help a human reviewer but never promote rules:

```text
review_router
evidence_repair
evidence_rerun
safe_tuning
llm_review_assistant
archived examiner    (preserved under archive/pre_m7_records/)
bylaw_rag            (Ask-the-bylaw retrieval)
review_ranker        (learned queue ordering, JSON model)
nli_semantics        (entailment second opinion)
native_extraction    (our proposer-tier extraction path)
```

Only deterministic verification can write `verified_rules.json`.

## Generalization Guardrails

The verifier must not use:

```text
gold-rule answers
known final thresholds
page-specific expected values
city-specific hardcoded legal outcomes
```

The verifier may use:

```text
candidate fields
cited evidence
local source context
generic zoning vocabulary
city terminology and aliases
unit aliases
operator cues
```

Gold rules are benchmark-only.
