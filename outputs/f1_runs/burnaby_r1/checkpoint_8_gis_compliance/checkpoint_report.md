# F1 checkpoint 8 Report

Checkpoint: F1 checkpoint 8

Purpose: Project verifier-promoted rules into verified-only GIS and tri-state compliance artifacts.

## Safety

| Metric | Value |
|---|---:|
| Existing safety reproduced | `true` |
| Overall status | `m7_safety_ready` |
| Current false verified total | `0` |
| F1 promotes rules in this checkpoint | `true` |
| F1 exports GIS in this checkpoint | `true` |

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
| Queries | `15` |
| Queries with hits | `15` |
| Total hits | `85` |
| Retrieval status | `pass` |


## Structured Extraction

| Metric | Value |
|---|---:|
| Method | `retrieval_measurement_candidate_extractor` |
| Candidate rules | `51` |
| Skipped query families | `6` |
| Promoted count | `0` |
| All candidates review-needed | `true` |


## Verification

| Metric | Value |
|---|---:|
| Candidate count | `51` |
| Verified count | `38` |
| Review queue count | `13` |
| False verified count | `0` |
| Status counts | `{'verified': 35, 'context_required': 5, 'rejected': 7, 'repaired_successfully': 3, 'not_used': 1}` |


## Repair And Review

| Metric | Value |
|---|---:|
| Repair attempts | `16` |
| Review packets | `16` |
| Eligible proof patches | `4` |
| Verifier rerun attempts | `4` |
| Guarded repair promotions | `3` |
| False verified count | `0` |


## GIS And Compliance

| Metric | Value |
|---|---:|
| Verified-only contract | `true` |
| GIS export rules | `38` |
| Excluded review rules | `13` |
| Compliance smoke scenarios | `77` |
| Compliance status counts | `{'approved': 38, 'rejected': 38, 'needs_review': 1}` |
| False approval count | `0` |






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
