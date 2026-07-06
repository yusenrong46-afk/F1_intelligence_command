# F1 checkpoint 13 Report

Checkpoint: F1 checkpoint 13

Purpose: Run F1 artifact generation across multiple cities and label benchmark coverage honestly.

## Safety

| Metric | Value |
|---|---:|
| Existing safety reproduced | `true` |
| Overall status | `m7_safety_ready` |
| Current false verified total | `0` |
| F1 promotes rules in this checkpoint | `false` |
| F1 exports GIS in this checkpoint | `false` |










## Multi-City

| Metric | Value |
|---|---:|
| Parser mode | `fallback` |
| Cities | `4` |
| Completed cities | `4` |
| Failed cities | `0` |
| Release-safe benchmark cities | `1` |
| Exploratory/partial cities | `3` |
| False verified total | `0` |
| False approval total | `0` |
| Runtime seconds | `56.274` |



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
