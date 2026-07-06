# M7 Source Module Map

## Current Working Path

Treat this as the only current product path:

```text
scripts/run_consolidated_prototype.py
-> scripts/run_m7_bakeoff.py
-> scripts/run_m7_bakeoff_engine.py --discovery-mode exhaustive
-> native_extraction.py + m7_matrix_candidates.py + m7_clause_candidates.py
-> slim_pipeline.py
-> verification.py / support_checks.py / decision_policy.py
-> outputs/m7_runs/<city>/google_gemini_3_1_flash_lite/
-> dashboard/streamlit_app.py
```

In plain language:

- `run_consolidated_prototype.py` is the handoff command surface.
- `run_m7_bakeoff.py` is the current native full-bylaw extraction entrypoint.
- `run_m7_bakeoff_engine.py` is the shared M7 engine for discovery, extraction,
  verification, and gap reporting.
- `verification.py`, `support_checks.py`, and `decision_policy.py` are the
  deterministic trust gate.
- `dashboard/streamlit_app.py` reads artifacts only; it does not verify rules.

Canonical modules remain at the package top level so existing imports stay
simple: `burnaby_prototype.<module>`. Folder skeletons document ownership and
boundaries; they are not separate runtime packages yet.

## Core Verifier

These files decide whether a candidate rule is proven, review-only, rejected,
or out of scope.

| File | Purpose |
|---|---|
| `verification.py` | Main verification loop. Loads evidence, normalizes candidates, runs support/proof checks, and emits decision buckets. |
| `decision_policy.py` | Maps support gaps to `verified`, `review_needed`, `rejected`, or `not_used`. Also holds global safety gates for known false-verify patterns. |
| `support_checks.py` | Deterministic value/unit/operator/scope/evidence checks. |
| `normalization.py` | Cleans candidate fields into canonical rule objects, operators, units, and scopes. |
| `normalization_rules.py` | Config-driven normalization helpers. |
| `domain_schema.py` | Shared rule families, units, operators, and numeric parsing. |
| `verification_cache.py` | Cache keys and diagnostics for verifier reuse; does not skip verification by default. |

## Table And Text Proof

These files explain or prove evidence support. They are important: recent real
LLM runs showed that flattened table text can leak false rules unless table
geometry is preserved.

| File | Purpose |
|---|---|
| `table_matrix.py` | Recovers row/column/cell structure from matrix-style tables and attaches `matrix_anchor` evidence. |
| `m7_matrix_candidates.py` | Proposes deterministic matrix-table candidates for M7 extraction. |
| `table_natural_logic.py` | Table-aware proof/refutation helpers. |
| `text_span_proof.py` | Prose evidence span and material-condition checks. |
| `proof_trace.py` | Human-readable proof traces and gap labels. |
| `proof_dag.py` | Proof DAG sidecar for explanation/reporting. |
| `rule_claims.py` | Claim labels, proof diagnostics, and evidence-strength helpers. |

## Intake And Extraction

These modules propose candidates or adapt outside extractor output. They do not
verify their own results.

| File | Purpose |
|---|---|
| `zihao_adapter.py` | Converts Pipeline 5-style registry output into `rule_candidates` + `evidence_units`. |
| `pipeline9_adapter.py` | Converts Pipeline 9 graph-RAG output, preserves provenance, and re-anchors evidence to source PDFs. |
| `native_extraction.py` | Current LLM extraction candidate parser/caller used by M7. |
| `m7_run_store.py` | SQLite cache/run ledger for source chunks, packs, and model outputs. |
| `m7_source_discovery.py` | Source-chunk helper functions. |
| `m7_model_extraction.py` | Shared model-call assembly for M7 candidate extraction. |
| `m7_evidence_discovery.py` | Discovery wrapper for exhaustive rule-signal sweeps, section neighbors, target-section expansion, and repair packs. |
| `m7_gap_report.py` | Gap report builder for M7 evaluation output. |
| `extraction/` | Legacy internal PDF-to-registry helper path. |

## Source Repair And RAG

These improve evidence packets and reviewer search. They are advisory or
pre-verification support layers.

| File | Purpose |
|---|---|
| `source_repair.py` | Source-backed repair: page re-anchoring, nearby context, table/heading context, mismatch flags. |
| `bylaw_rag.py` | BM25/RAG retrieval support for source search and dashboard Q&A. |
| `evidence_contract.py` | Evidence type constants and lightweight evidence contract helpers. |

## Advisory Review

These help humans understand or triage review items. They must not promote
rules into `verified_rules.json`.

| File | Purpose |
|---|---|
| `evidence_intelligence.py` | Evidence bundle scoring and diagnostics. |
| `evidence_repair.py` | Searches for better evidence among existing packets. |
| `evidence_rerun.py` | Advisory reruns with stronger evidence bundles. |
| `review_router.py` | Unified review queue and reviewer next-action labels. |
| `review_resolution.py` | Operational resolution labels for remaining review items. |
| `review_assistant_packets.py` | Deterministic packets for dashboard/assistant review. |
| `llm_review_assistant.py` | Optional LLM review summaries; advisory only. |
| `semantic_review.py` | Deterministic semantic comparison of review vs verified rules. |
| `embedding_semantics.py` | Optional sentence-embedding ranking for review support. |
| `nli_semantics.py` | Optional entailment second opinion; advisory only. |
| `review_ranker.py` | Optional learned review ranking; advisory only. |
| `safe_tuning.py` | Candidate safe-tuning report; planning support only. |

## Reports And Exports

These turn verified/review outputs into reports, dashboard data, or downstream
GIS artifacts.

| File | Purpose |
|---|---|
| `slim_pipeline.py` | Main orchestrator/writer for verifier outputs and sidecar reports. |
| `coverage_report.py` | Coverage/gap matrix reporting. |
| `rule_graph.py` | Diagnostic graph linking candidates, evidence, verified rules, and review items. |
| `gis_felt_export.py` | Verified-only Felt/GIS export. |
| `geometry_operator.py` | Maps verified rule families into coarse GIS operations. |
| `compliance.py` | Proposal/compliance checker against verified GIS contract. |
| `applicability.py` | Structured applicability parsing for dwelling/unit-range table columns. |
| `conflict_guard.py` | Cross-family collision detection. |
| `consensus.py` | Agreement/conflict diagnostics across evidence sources. |
| `rule_text.py` | Shared rule sentence rendering. |
| `review_text.py` | Shared reviewer-facing wording helpers. |

## Folder Skeleton

These folders now exist with local README files:

```text
adapters/
discovery/
repair/
verifier/
review/
exports/
reports/
```

For now they document ownership and boundaries. The current top-level modules
remain canonical until a later package-layout migration updates scripts,
dashboard code, tests, and external handoff notes together.
