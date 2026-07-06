# F1 Final Readiness Report

Date: 2026-07-06

F1 is now the active product surface for the Burnaby R1 bylaw command center.
The M-series remains archived research. The current F1 run is:

```text
outputs/f1_runs/burnaby_r1/checkpoint_16_product_operations/
```

## Final Stage

F1 is finalized as a **Burnaby benchmark-safe command center** with:

- verified-rule browsing;
- source and evidence navigation;
- human review workbench;
- non-promoting review action drafts;
- guarded repair evidence;
- verified-only GIS handoff;
- scoped scenario checks;
- source-grounded chatbot answers;
- benchmark and safety audit pages.

It is not a permit-approval product. It is a bylaw intelligence and verification
command center.

## Commandments Audit

| Commandment | F1 status | Evidence |
|---|---|---|
| Source documents are ground truth | Pass | `source_registry.json`, SHA/provenance gate |
| Extraction proposes candidate rules | Pass | `candidate_rules.json`, extraction promotes `0` directly |
| RAG retrieves evidence, not truth | Pass | `retrieval_report.json` feeds evidence only |
| Repair proposes patches, never approval | Pass | repair routes through verifier reruns |
| Verification is the only promotion authority | Pass | `verified_rules.json` comes from deterministic verification |
| Chatbot explains and navigates only | Pass | chat refuses approval/promotion requests |
| GIS and compliance consume verified-only rules | Pass | `gis_rule_contract.json` excludes review items |
| No dry-run result is called measured | Pass | checkpoint 16 is a real local run |
| Every upgrade is benchmarked or labeled exploratory | Pass | `f1_benchmark_report.json` gates passed |
| Non-gold cities are exploratory only | Pass | Burnaby is the benchmark-safe release city |

## Measured Result

| Metric | Value |
|---|---:|
| Quality gates passed | `true` |
| Verified rules | `38` |
| Review items | `13` |
| Review action templates | `13` |
| Scenario templates | `38` |
| Evidence navigation rows | `77` |
| Retrieval recall at 6 | `0.95` |
| Candidate recall | `0.975` |
| Verified precision | `1.0` |
| Verified recall | `0.85` |
| False verified | `0` |
| False approvals | `0` |
| Writes rule status from operations | `false` |
| Writes GIS contract from operations | `false` |

## Product Improvements In Final Pass

The dashboard was revised from a functional prototype into a cleaner civic
command-center interface:

- stronger first-screen status strip: verified, review, precision, false
  verified;
- clearer page hierarchy and benchmark-safe label;
- less generic card styling, tighter spacing, lower-radius civic UI treatment;
- better first-screen explanation of what F1 does;
- better next-action cards for the user journey;
- checkpoint 16 operations surfaced as product capability, not hidden artifact
  trivia;
- live chatbot answers now render as answer cards with direct answer,
  supporting facts, next step, and citations;
- phrase-aware chat matching separates `lot area` from `lot coverage`;
- review actions remain local draft notes and cannot mutate verifier outputs.

## Chatbot Boundary

The chatbot is intentionally open-ended over the loaded F1 artifacts, but it is
not a legal authority. It can:

- answer plain-language bylaw questions from verified rules;
- explain review gaps;
- explain source evidence;
- explain GIS/compliance boundaries;
- cite evidence IDs where available.

It cannot:

- approve a permit;
- say a project is legal to build;
- promote a review item;
- mark a rule verified;
- edit GIS outputs.

## Visual Audit Evidence

Live screenshots were captured from `http://localhost:8631/`:

```text
docs/f1_product_audit_2026_07_06/01-overview-chat.png
docs/f1_product_audit_2026_07_06/02-human-review.png
docs/f1_product_audit_2026_07_06/03-gis-handoff.png
docs/f1_product_audit_2026_07_06/04-quality-audit.png
```

## Remaining Gaps

These are not blockers for finalized F1, but they define the next product stage:

- live model-backed chat inside the Streamlit UI is not yet connected;
- multi-city release safety still requires gold benchmarks per city;
- parcel-specific GIS drawing is still a future product layer;
- review draft actions are local JSON, not authenticated workflow records;
- verified recall is `0.85`, so coverage can improve without loosening
  verification.

## Final Position

F1 is ready to be treated as the first productized Burnaby command center:
measured, benchmark-safe, visually improved, and strict about the safety
boundary.
