# Outputs Folder Map

`outputs/` stores reproducible verifier runs, model bakeoffs, and dashboard
artifacts. Treat these as generated artifacts, not source code.

The current product generation is **M7**: the consolidated matrix-aware pipeline
on `google/gemini-3.1-flash-lite`. Historical and comparison records now live
under `archive/pre_m7_records/`; the visible `outputs/` folder is for current
M7 status, runs, audits, measurement, and chatbot evaluation.

## Current High-Signal Outputs

| Path | Purpose |
|---|---|
| `m7_status_report/` | Current cross-city status report. Start with `m7_status_report.md`. |
| `m7_runs/<city>/google_gemini_3_1_flash_lite/` | Current product M7 verifier output for each city (gemini-3.1-flash-lite). |
| `m7_runs/<city>/` | M7 discovery summaries and evidence packs for each city. |
| `m7_measure/m7_final_gemini31_2026_06_16/<city>/` | M7 scored-coverage measurement run (honest scored legal-slot denominator). |
| `m7_audits/2026_06_24/` | Latest M7 audit and Surrey probe records. |
| `m7_audits/strictness_audit.md` | Current strictness/gap audit from `scripts/audit_strictness.py`. |
| `m7_advisory/review_ranker_model.json` | Optional learned review-queue ranker; advisory only, never a verifier gate. |
| `m7_chatbot_eval/current/` | Current chatbot evaluation results. |
| `benchmark/source_corpus/<city>/rag_index.json` | Compact RAG index used by the dashboard's Ask the Bylaw panel. |

Use these first when presenting the project:

```text
outputs/m7_status_report/m7_status_report.md
outputs/m7_runs/<city>/google_gemini_3_1_flash_lite/
outputs/m7_measure/m7_final_gemini31_2026_06_16/<city>/
outputs/m7_audits/2026_06_24/
```

## Archived Reference Outputs

Past records are preserved under `archive/pre_m7_records/`. They are kept for
comparison and reproducibility, not as current product surfaces.

## Important Files Inside A Run

| File | Meaning |
|---|---|
| `verified_rules.json` | Rules proven by deterministic verification (raw audit trail). |
| `review_needed.json` | Plausible rules with missing/ambiguous evidence. |
| `rejected_rules.json` | Unsafe, contradicted, or malformed candidates. |
| `not_used.json` | Traceability/out-of-scope artifacts. |
| `gis_rule_contract.json` | Verified-only, deduplicated GIS input. |
| `gis_felt_export.json` | Richer deduplicated map/dashboard projection from verified rules. |
| `benchmark_report.json` / `.md` | Precision, false-verified, recall, proposal metrics, and gate status. |
| `slim_summary.json` | Compact run counts for dashboard/reporting. |
| `source_repair_report.json` | Evidence repair/re-anchoring diagnostics. |
| `review_assistant_packets.json` | Deterministic review packets for dashboard/human review. |
| `model_cost_report.json` | Model cost/latency summary where applicable. |

`gis_rule_contract.json` and `gis_felt_export.json` are a pure deterministic
projection of `verified_rules.json`; `tests/test_m7_safety_gates.py` fails CI if
either committed export drifts from a fresh regen.

## Cleanup Rule

`.gitignore` keeps only curated M7 status/audit outputs visible for release
commits. Do not use `git add -A`; stage source, docs, tests, configs, and the
curated output paths explicitly.

Do not delete output folders just because they look old. First decide whether
they are:

1. current reporting artifacts,
2. comparison baselines,
3. reproducibility evidence,
4. dashboard inputs, or
5. disposable local experiments.

Only category 5 should be removed, and only after checking `git status` and the
dashboard/tests.
