# Consolidated Prototype

This document is the current handoff map for the prototype. It separates the
parts that decide from the parts that propose, explain, cache, or display.

## Trust Boundary

```text
Extractors propose.
RAG/discovery finds source context.
Source repair restores source-backed evidence.
The deterministic verifier decides.
GIS consumes only verified rules.
```

No extractor confidence score, LLM response, RAG rank, or dashboard action can
promote a rule into `verified_rules.json`.

## Front Door

Use the consolidated script for demos and handoff checks:

```bash
.venv/bin/python scripts/run_consolidated_prototype.py status
```

Refresh the benchmark/status report:

```bash
.venv/bin/python scripts/run_consolidated_prototype.py report
```

Dry-run the current M7 full-bylaw discovery path without calling an LLM:

```bash
.venv/bin/python scripts/run_m7_bakeoff.py --city calgary_rcg --models google/gemini-2.5-flash-lite --dry-run
```

Run the current M7 extraction path with one OpenRouter model:

```bash
.venv/bin/python scripts/run_m7_bakeoff.py --city burnaby_r1 --models google/gemini-2.5-flash-lite
```

The consolidated script wraps existing specialist scripts. It does not contain
verification logic.

## Current M7 Status

Source: `outputs/m7_status_report/m7_status_report.md`

| Lane | Candidates | Verified | Review | Rejected | Not used | False verified | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Burnaby M7 matrix-aware extraction | 144 | 87 | 57 | 0 | 0 | 0 | pass |
| Vancouver M7 matrix-aware extraction | 56 | 10 | 31 | 15 | 0 | 0 | pass |
| Calgary M7 matrix-aware extraction | 150 | 29 | 42 | 27 | 52 | 0 | pass |

Overall status is `m7_safety_ready`. Archived P5 and P9 rows are retained as
historical/upstream references only, not as the product path.

## Source Inventory

| City | Current PDF size |
|---|---:|
| Burnaby R1 | 7 pages |
| Vancouver RS | 22 pages |
| Calgary R-CG | 1,053 pages |

Calgary must always be treated as the full 1,053-page bylaw unless a command
explicitly says it is testing a slice.

## Authoritative Outputs

These files are the important handoff artifacts in each verifier output dir:

```text
verified_rules.json
review_needed.json
rejected_rules.json
not_used.json
benchmark_report.json
benchmark_report.md
validation_report.json
gis_rule_contract.json
```

`gis_rule_contract.json` is the only verification output GIS should consume.

## What To Keep

Keep these as first-class pieces:

| Piece | Purpose |
|---|---|
| `scripts/run_consolidated_prototype.py` | One stable command surface for status, M7 status refresh, and native extraction runs |
| `scripts/run_m7_status_report.py` | Honest benchmark/status report across current lanes |
| `scripts/run_slim_verifier.py` | Main verifier entrypoint for M7 candidate sets |
| `scripts/run_m7_bakeoff.py` | Current M7 full-bylaw extraction/discovery runner |
| `scripts/build_m7_source_corpus.py` | Full-PDF source-corpus and coverage-audit snapshots |
| `src/burnaby_prototype/verification.py` | Authority layer |
| `src/burnaby_prototype/decision_policy.py` | Final bucket policy |
| `src/burnaby_prototype/support_checks.py` | Deterministic source-support checks |
| `src/burnaby_prototype/source_repair.py` | Source-backed evidence repair |
| `src/burnaby_prototype/pipeline9_adapter.py` | Archived graph-RAG candidate adapter |
| `src/burnaby_prototype/native_extraction.py` | Our own extraction candidate generator |
| `src/burnaby_prototype/m7_source_discovery.py` | Full-bylaw evidence discovery and pack building |
| `src/burnaby_prototype/m7_evidence_discovery.py` | M7 discovery expansion and repair-pack construction |
| `src/burnaby_prototype/m7_run_store.py` | SQLite cache and run ledger |
| `dashboard/streamlit_app.py` | Review and reporting console |

Past comparison lanes are archived under archive/pre_m7_records; the active route is M7.

## What To Defer

These can be done after M7 is stable:

| Cleanup | Why defer |
|---|---|
| Moving all modules into subpackages | Many scripts/tests import the current flat module paths; move with an import-migration PR |
| Deleting old scripts | Some are still useful for audit, demo history, and comparison |
| LLM review assistant polish | It is advisory and lower priority than extraction/verification coverage |
| GIS dashboard expansion | Final deliverable needs GIS maps, but the verifier dashboard should stay focused on rule proof/review |

## Recommended Folder Shape Later

When ready, consolidate the `src/burnaby_prototype` modules by responsibility:

```text
adapters/       pipeline5, pipeline9, native extraction contracts
discovery/      RAG, source chunks, evidence packs, SQLite cache
repair/         source repair and page re-anchoring
verifier/       normalization, support checks, proof gates, decision policy
review/         advisory routing, examiner, LLM assistant
exports/        GIS contract, Felt export, reports
```

Do this only after the current command and test suite stay green.
