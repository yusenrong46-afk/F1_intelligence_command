# F1 checkpoint 3 Report

Checkpoint: F1 checkpoint 3

Purpose: Build proof-aware retrieval over F1 source spans without giving retrieval promotion authority.

## Safety

| Metric | Value |
|---|---:|
| Existing safety reproduced | `true` |
| Overall status | `m7_safety_ready` |
| Current false verified total | `0` |
| F1 promotes rules in this checkpoint | `false` |
| F1 exports GIS in this checkpoint | `false` |

## Source Registry

| Metric | Value |
|---|---:|
| Source count | `1` |
| Validation status | `pass` |
| Source PDF exists | `true` |
| Provenance exists | `true` |
| SHA-256 matches | `true` |


## Document Intelligence

| Metric | Value |
|---|---:|
| Ingest backend | `docling` |
| Pages parsed | `7` |
| Document blocks | `112` |
| Source spans | `112` |
| Table blocks | `4` |


## Proof-Aware RAG

| Metric | Value |
|---|---:|
| Retrieval method | `lexical_bm25_rrf` |
| Reranker | `lexical_overlap` |
| Queries | `6` |
| Queries with hits | `6` |
| Total hits | `36` |
| Retrieval status | `pass` |


## Constitution

1. Source documents are ground truth.
2. Extraction proposes candidate rules.
3. RAG retrieves evidence, not truth.
4. Repair proposes patches, never approval.
5. Verification is the only promotion authority.
6. Chatbot explains and navigates, but cannot verify or approve.
7. GIS and compliance consume verified-only rules.
8. No dry-run result may be described as a real measured result.
9. Every upgrade must be proven by benchmark or clearly labeled exploratory.
10. A city without gold benchmark is exploratory only.

## Canonical Artifacts

- `source_registry.json`
- `document_blocks.json`
- `source_spans.json`
- `retrieval_report.json`
- `candidate_rules.json`
- `verification_decisions.json`
- `verified_rules.json`
- `review_queue.json`
- `repair_attempts.json`
- `repair_rerun_report.json`
- `gis_rule_contract.json`
- `compliance_decisions.json`
- `chatbot_eval.json`
- `f1_summary.json`
