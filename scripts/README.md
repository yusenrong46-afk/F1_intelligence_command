# Scripts

All commands run from the repo root with `.venv/bin/python` unless noted.
Start with `run_consolidated_prototype.py`; most other scripts are specialist
M7 tools or audit helpers.

Current generation is **M7**: the consolidated matrix-aware pipeline on
`google/gemini-3.1-flash-lite`, writing to
`outputs/m7_runs/<city>/google_gemini_3_1_flash_lite/`. Measurement runs land
under `outputs/m7_measure/<run_id>/` (`run_m7_measure.py`). The verifier itself
is model-agnostic and deterministic; the model only proposes candidates.

## Primary Commands

| Script | Purpose |
|---|---|
| `run_consolidated_prototype.py` | One handoff entrypoint for current status, M7 status report refresh, and native extraction/discovery runs. |
| `run_m7_status_report.py` | Builds the honest cross-city M7 status report from current M7 current outputs at `outputs/m7_status_report/m7_status_report.md`; archived pre-M7 are reference rows only. |
| `run_m7_bakeoff.py` | Current M7 entrypoint: exhaustive full-bylaw discovery, native extraction, deterministic verification, and reports. |
| `run_slim_verifier.py` | Main deterministic verifier entrypoint. M7 calls it after candidate extraction. |

## Engine Internals

These scripts exist because M7 separates the public command from the shared
engine. Do not present engine internals as separate product paths.

| Script | Purpose |
|---|---|
| `run_m7_bakeoff_engine.py` | Shared M7 engine used through `run_m7_bakeoff.py` with `--discovery-mode exhaustive`. |
| archived native bakeoff | Preserved under `archive/pre_m7_records/scripts/` for regression analysis. Not a final-demo command. |

## Extraction / Source Helpers

| Script | Purpose |
|---|---|
| `fetch_bylaw.py` | Fetch/cache a source PDF with sha256 provenance. |
| `build_m7_source_corpus.py` | Writes full-bylaw M7 source-corpus snapshots and coverage audits without reading gold. |
| `run_extraction.py` | Adapter helper for regenerating candidate/evidence inputs when a legacy extraction record must be replayed. Not the product path. |
| `run_pipeline5_extraction.py` | Preflight/refresh helper for upstream extraction records. Not the product path. |
| `run_native_extraction.py` | Smaller native extraction wrapper; prefer `run_consolidated_prototype.py native` for handoff. |
| `build_rag_index.py` | Build bylaw RAG index for dashboard/source search. |

## Reports / Exports

| Script | Purpose |
|---|---|
| `build_proof_graph.py` | Render the proof graph HTML sidecar. |
| `build_buildable_envelope.py` | Build simplified verified-only buildable-envelope JSON. |
| `build_envelope_3d.py` | Build optional 3D envelope visualization. |
| `run_m7_measure.py` | Create fresh `outputs/m7_measure/<run_id>/` benchmark snapshots, scoreboard rows, source registry, RAG retrieval report, and bottleneck diagnosis; use `--refresh-verifier` after verifier/proof changes. |
| `audit_bylaw_coverage.py` | Audit bylaw/source coverage. |
| `audit_strictness.py` | Audit verifier strictness/gap patterns; writes `outputs/m7_audits/strictness_audit.md`. |
| `minimize_evidence.py` | Minimize evidence text for proof explanation. |

## Advisory / Learning

| Script | Purpose |
|---|---|
| `run_review_assistant.py` | Advisory LLM/offline briefs for review items. Cannot verify rules. |
| `train_review_ranker.py` | Optional learned review ranking experiment; writes `outputs/m7_advisory/review_ranker_model.json`. Not part of the verifier gate. |
| `suggest_gold_candidates.py` | Suggest candidate gold items for human curation. |
| `run_m7_chatbot_redteam.py` | Report-only chatbot red-team harness; writes `outputs/m7_chatbot_eval/redteam/<timestamp>/`. |

## Specialized Utilities

Pre-M7 holdout/demo wrappers live under `archive/pre_m7_records/scripts/`.
Active M7 transfer checks use `benchmark/evaluate_benchmark.py --city <city>`
against `outputs/m7_runs/<city>/google_gemini_3_1_flash_lite/`.

| Script | Purpose |
|---|---|
| `validate_config.py` | Validate city config structure. |

## Benchmarks

Benchmark entrypoints live under `benchmark/`.

| Script | Purpose |
|---|---|
| `benchmark/evaluate_benchmark.py` | Core M7 rule/retrieval/GIS/proposal evaluator. |
| `benchmark/evaluate_adversarial.py` | M7 adversarial verifier and bundle-safety evaluator. |
| `benchmark/evaluate_m7_chatbot.py` | Offline source-grounded chatbot policy evaluator; writes `outputs/m7_chatbot_eval/current/`. |
