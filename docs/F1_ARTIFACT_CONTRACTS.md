# F1 Artifact Contracts

F1 uses one product-facing artifact contract so ingestion, retrieval,
extraction, verification, repair, review, dashboard, chatbot, GIS, and
compliance layers do not drift into separate languages.

The Python contract draft lives in:

```text
src/burnaby_prototype/bylaw_command_center/contracts.py
```

The schema version for the checkpoint 0 draft is:

```text
f1.artifacts.v0
```

## Canonical Outputs

Current F1 runs write under:

```text
outputs/f1_runs/<city>/<run_id>/
```

Canonical artifacts:

| Artifact | Purpose |
|---|---|
| `source_registry.json` | Official source documents, provenance, URL, checksum, version, fetch status. |
| `document_blocks.json` | Parsed pages, sections, tables, figures, headings, and text blocks. |
| `source_spans.json` | Verifier-addressable source spans with page, section, offsets, text, and metadata. |
| `retrieval_report.json` | Retrieval queries, hits, scores, rerank decisions, and retrieval quality flags. |
| `candidate_rules.json` | Extracted candidate rules. Proposals only. |
| `verification_decisions.json` | Deterministic verifier decisions and support gaps. |
| `verified_rules.json` | Source-supported rules only. |
| `review_queue.json` | Rules that require human review or more context. |
| `repair_attempts.json` | Repair proposals and proof patches. Proposals only. |
| `repair_rerun_report.json` | Verifier rerun outcomes for repair candidate copies. |
| `gis_rule_contract.json` | Verified-only GIS contract. |
| `compliance_decisions.json` | Scenario decisions: approved, rejected, or needs_review. |
| `chatbot_eval.json` | Chatbot/RAG evaluation results and grounding failures. |
| `command_center_app_manifest.json` | Product UI manifest built from verified/review/compliance/benchmark artifacts. |
| `command_center_app.html` | Self-contained interactive command-center app. |
| `f1_summary.json` | Product run summary, safety metrics, cost, latency, and artifact index. |

## Checkpoint 1 Source Registry

The source registry is built by:

```bash
.venv/bin/python scripts/run_f1_checkpoint.py --checkpoint source_registry --city burnaby_r1
```

It writes:

```text
outputs/f1_runs/burnaby_r1/checkpoint_1_source_registry/source_registry.json
outputs/f1_runs/burnaby_r1/checkpoint_1_source_registry/f1_summary.json
```

The registry passes only when:

- the city config exists;
- the cached official PDF exists;
- `provenance.json` exists;
- the cached PDF SHA-256 matches provenance;
- the config source URL matches the provenance URL.

## Checkpoint 2 Document Intelligence

Document intelligence is built by:

```bash
.venv/bin/python scripts/run_f1_checkpoint.py --checkpoint document_intelligence --city burnaby_r1
```

It writes:

```text
document_blocks.json
source_spans.json
document_intelligence_report.json
```

The first parser preference is Docling. If Docling is unavailable or fails, F1
falls back to deterministic PDF text extraction while preserving the same output
contract.

Checkpoint 2 artifacts are still non-authoritative:

- document blocks are source structure, not verified rules;
- source spans are candidate evidence, not proof by themselves;
- table blocks help downstream retrieval and verification, but cannot promote a
  rule.

## Checkpoint 3 Retrieval Report

Proof-aware retrieval is built by:

```bash
.venv/bin/python scripts/run_f1_checkpoint.py --checkpoint proof_rag --city burnaby_r1
```

It writes:

```text
retrieval_report.json
```

The checkpoint 3 retriever uses deterministic lexical/BM25 reciprocal-rank
fusion plus a lexical-overlap reranker. This is intentionally pluggable: Cohere,
BGE, dense vectors, or multivector retrieval can be benchmarked later without
changing the F1 artifact contract.

Retrieval output is not legal authority. A high retrieval score means only that
a source span may be relevant enough for extraction, verification, repair, or
chatbot grounding.

## Checkpoint 4 Candidate Rules

Structured extraction is built by:

```bash
.venv/bin/python scripts/run_f1_checkpoint.py --checkpoint structured_extraction --city burnaby_r1
```

It writes:

```text
candidate_rules.json
extraction_report.json
```

Checkpoint 4 extraction is conservative:

- every candidate carries evidence IDs;
- every changed/parsed field has a citation payload in `raw.field_citations`;
- every candidate remains `review_needed`;
- `promoted_count` must remain `0`.

## Checkpoint 5 Verification Outputs

Verification is built by:

```bash
.venv/bin/python scripts/run_f1_checkpoint.py --checkpoint verification --city burnaby_r1
```

It writes:

```text
verification_decisions.json
verified_rules.json
review_queue.json
verification_report.json
```

Checkpoint 5 verification is fail-closed:

- unsupported values, units, operators, or rule objects are rejected;
- incomplete applicability or scope becomes context-required;
- only deterministic verifier decisions can populate `verified_rules.json`;
- `false_verified_count` must remain `0`.

## Checkpoint 6 Repair And Review Outputs

Repair/review packaging is built by:

```bash
.venv/bin/python scripts/run_f1_checkpoint.py --checkpoint repair_review --city burnaby_r1
```

It writes:

```text
repair_attempts.json
review_packets.json
repair_rerun_report.json
```

Checkpoint 6 is intentionally review-safe:

- every uncertain verifier decision becomes a review packet;
- every repair attempt is `review_only` until a field-level proof patch exists;
- verifier rerun attempts remain `0` without a validated proof patch;
- guarded repair promotions remain `0`;
- repair cannot mark a rule verified or approved.

## Checkpoint 7 Guarded Repair Outputs

Guarded repair is built by:

```bash
.venv/bin/python scripts/run_f1_checkpoint.py --checkpoint guarded_repair --city burnaby_r1
```

It writes the checkpoint 6 artifacts plus:

```text
verifier_rerun_requests.json
guarded_repair_promotions.json
```

It also rewrites these verifier-owned artifacts after guarded reruns:

```text
verification_decisions.json
verified_rules.json
review_queue.json
verification_report.json
```

Checkpoint 7 remains verifier-authoritative:

- repair can create a proof patch only for supported fields;
- every proof patch must include an evidence ID, span ID, and quote;
- patched candidate copies go back through deterministic verification;
- `repaired_successfully` is written only after verifier proof;
- direct repair promotion remains impossible.

## Checkpoint 8 GIS And Compliance Outputs

Verified-only GIS/compliance export is built by:

```bash
.venv/bin/python scripts/run_f1_checkpoint.py --checkpoint gis_compliance --city burnaby_r1
```

It writes:

```text
gis_rule_contract.json
compliance_decisions.json
compliance_report.json
```

Checkpoint 8 is a post-verification projection:

- `gis_rule_contract.json` contains only rules from `verified_rules.json`;
- review, rejected, and context-required items are excluded from GIS;
- compliance decisions are tri-state: `approved`, `rejected`, or
  `needs_review`;
- generated smoke scenarios are not a release benchmark;
- `false_approval_count` must remain `0`.

## Checkpoint 9 Chatbot Evaluation Output

Chatbot evaluation is built by:

```bash
.venv/bin/python scripts/run_f1_checkpoint.py --checkpoint chatbot_eval --city burnaby_r1
```

It writes:

```text
chatbot_eval.json
```

Checkpoint 9 is a safety harness before real model integration:

- answerable responses must cite evidence IDs;
- approval requests must stay uncertain/refusal, not approved;
- the artifact clearly states that GPT-OSS-120B was not run in this checkpoint;
- future model-backed chatbot runs must satisfy the same citation and refusal
  metrics.

## Checkpoint 10 Command Center Outputs

Command-center preview is built by:

```bash
.venv/bin/python scripts/run_f1_checkpoint.py --checkpoint command_center --city burnaby_r1
```

It writes:

```text
command_center_manifest.json
command_center_preview.html
```

Checkpoint 10 is a product preview over real F1 artifacts:

- the manifest carries card metrics, verified GIS rules, review items,
  compliance status counts, and chatbot metrics;
- the HTML preview is self-contained and can be opened directly in a browser;
- the preview does not write back to verifier, repair, GIS, or compliance
  decisions.

## Checkpoint 11 Model-Backed Chatbot Evaluation

Real model-backed chatbot evaluation is built by:

```bash
.venv/bin/python scripts/run_f1_checkpoint.py --checkpoint model_chatbot_eval --city burnaby_r1 --chat-model openai/gpt-oss-120b
```

It writes:

```text
chatbot_eval.json
```

Checkpoint 11 uses the OpenRouter key from the environment or `.env`:

- the run fails clearly if `OPENROUTER_API_KEY` is missing;
- the model receives bounded F1 context only;
- answerable bylaw responses must cite F1 evidence IDs;
- approval requests must be refused or routed to compliance/human review;
- model output still cannot write verifier, repair, GIS, or compliance
  decisions.

## Checkpoint 12 Model Chatbot Red-Team Evaluation

Real adversarial/follow-up chatbot evaluation is built by:

```bash
.venv/bin/python scripts/run_f1_checkpoint.py --checkpoint model_chatbot_redteam --city burnaby_r1 --chat-model openai/gpt-oss-120b
```

It writes:

```text
chatbot_redteam_eval.json
```

Checkpoint 12 expands the model-backed eval:

- prompt-injection attempts must be refused;
- rejected/review items must stay non-executable;
- follow-up questions about rejected items must cite the evidence ID;
- factual rule explanations must cite F1 evidence IDs;
- requests to mark a project approved must be refused;
- every failed red-team case is listed in `metrics.failed_cases`.

## Checkpoint 13 Multi-City Generalization Outputs

Multi-city generalization is built by:

```bash
.venv/bin/python scripts/run_f1_checkpoint.py --checkpoint multi_city --multi-cities burnaby_r1,vancouver_rs,calgary_rcg,surrey_r3 --no-docling
```

It writes aggregate artifacts under:

```text
outputs/f1_runs/multi_city/checkpoint_13_multi_city/f1_multi_city_report.json
outputs/f1_runs/multi_city/checkpoint_13_multi_city/f1_multi_city_report.md
outputs/f1_runs/multi_city/checkpoint_13_multi_city/f1_summary.json
```

It writes per-city artifacts under:

```text
outputs/f1_runs/<city>/checkpoint_13_multi_city/
```

Each per-city directory contains the same canonical F1 outputs as a single-city
run, plus:

```text
f1_city_summary.json
```

Checkpoint 13 labels city maturity explicitly:

- `benchmark_with_proposals`: gold rules and proposal cases exist; eligible for
  release-safe claims if the benchmark gates pass.
- `partial_benchmark_no_proposals`: gold rules exist but proposal cases are
  missing; extraction/verification can be studied, but compliance release claims
  are incomplete.
- `exploratory_no_gold`: no gold benchmark exists; results are diagnostic only.

The multi-city report is not allowed to average away safety failures. It keeps
city-level false verified and false approval counts, and the aggregate summary
must keep both totals at `0`.

## Checkpoint 14 Benchmark Evaluation Outputs

F1 benchmark evaluation is built by:

```bash
.venv/bin/python scripts/run_f1_checkpoint.py --checkpoint benchmark_eval --city burnaby_r1
```

It writes:

```text
f1_benchmark_report.json
f1_benchmark_report.md
```

Checkpoint 14 measures canonical F1 artifacts against benchmark gold files:

- retrieval recall at 6 from gold-term retrieval probes;
- candidate recall against gold rules;
- verified precision and verified recall against gold rules;
- source-support completeness for promoted rules;
- GIS verified-only export quality;
- proposal decision accuracy and false approvals when proposal cases exist.

The benchmark layer is read-only:

- it cannot promote rules;
- it cannot approve proposals;
- it can label a proof-passed rule as a release-scope failure;
- failed gates become the next upgrade target, not permission to weaken the
  verifier.

Current Burnaby checkpoint 14 safety gates pass for verified precision,
false-verified count, false-approval count, source-support completeness, and
GIS verified-only export. The current Burnaby benchmark also passes retrieval
recall, candidate recall, proposal-decision accuracy, and proposal-case accuracy
gates:

| Metric | Current Burnaby Value |
|---|---:|
| Retrieval recall at 6 | `0.95` |
| Candidate recall | `0.975` |
| Verified precision | `1.0` |
| Verified recall | `0.85` |
| False verified | `0` |
| False approvals | `0` |
| Proposal decision accuracy | `1.0` |
| Proposal case accuracy | `1.0` |

The remaining review queue is still real product work: uncertain rules stay out
of GIS/compliance exports until deterministic verification or human review can
prove them.

## Checkpoint 15 Command Center App

The interactive command center is built by:

```bash
.venv/bin/python scripts/run_f1_checkpoint.py --checkpoint command_center_app --city burnaby_r1
```

It writes:

```text
command_center_app_manifest.json
command_center_app.html
```

Checkpoint 15 reads measured F1 artifacts and creates a product-facing surface:

- searchable verified rule explorer;
- review workbench with support gaps and evidence;
- evidence inspector with evidence IDs, pages, sections, spans, and quotes;
- single-rule compliance sandbox over verified rules;
- benchmark and chatbot safety panels.

The command-center app is read-only:

- it cannot promote rules;
- it cannot approve a full project by chat;
- it cannot export review items into GIS;
- it cannot mutate repair or review state;
- it can only display and locally simulate against already verified artifacts.

## Served F1 Product UI

The Streamlit product UI is:

```text
dashboard/f1_command_center.py
```

Run it with:

```bash
.venv/bin/python -m streamlit run dashboard/f1_command_center.py --server.port 8631
```

It reads the checkpoint 15 command-center manifest by default:

```text
outputs/f1_runs/burnaby_r1/checkpoint_15_command_center_app/command_center_app_manifest.json
```

The companion pure data provider is:

```text
dashboard/f1_data.py
```

The served UI follows the same read-only authority boundary as the static app.
It can search, filter, explain, locally simulate, and display evidence, but it
cannot write verifier, repair, review, GIS, chatbot, or compliance decisions.

The active F1 app must not expose old M8 or M8.5 Streamlit pages. Those pages
are preserved as research records under:

```text
archive/m_series/dashboard_pages/
```

Current F1 navigation is:

| F1 view | Reads | Product purpose |
|---|---|---|
| 0 Results + Chat | manifest, benchmark, chatbot metrics | Show the candidate check flow, guardrails, and source-grounded helper. |
| 1 Source Documents | source registry, document intelligence, retrieval report | Inspect official PDF provenance and evidence packets. |
| 2 Verified Rules | verified rules, citations | Browse executable source-backed rules by family and page. |
| 3 Human Review | review queue, verified rules, evidence snippets | Explain blocked candidates and compare against verified rules. |
| 4 Repair Evidence | repair rerun report, guarded promotions, verifier reruns | Show shadow repair outcomes without weakening verifier authority. |
| 5 GIS Handoff | GIS contract, verified rules | Export verified-only map-ready constraints. |
| 6 Quality Audit | benchmark report, verification report, review gaps | Audit precision, recall, source support, and status mix. |

## Core Types

| Type | Role |
|---|---|
| `SourceDocument` | One official bylaw source with provenance. |
| `DocumentBlock` | Parsed PDF/document block. |
| `SourceSpan` | Evidence span that retrieval and verification can cite. |
| `TableCellSpan` | Table cell with row/column/header lineage. |
| `VisualRegion` | Drawing, diagram, figure, or map region. |
| `RetrievalEvidence` | RAG hit prepared as proof evidence. |
| `CandidateRule` | Extracted rule candidate. |
| `VerificationDecision` | Verifier-owned decision. |
| `RepairPatch` | Proposed field change with proof. |
| `ReviewPacket` | Human review unit. |
| `ComplianceScenario` | User or parcel scenario. |
| `ComplianceDecision` | Approved, rejected, or needs_review result. |
| `ChatAnswer` | Source-cited chatbot response. |

## Fail-Closed Defaults

- Candidate rules default to `review_needed`.
- Verification decisions default to `review_needed`.
- Compliance decisions default to `needs_review`.
- Promoted verification decisions require evidence IDs and cannot carry support
  gaps, unresolved dependencies, or risk flags.
- Repair patches cannot carry direct verification or approval actions.
- Chatbot answers that claim they can answer must cite evidence.
