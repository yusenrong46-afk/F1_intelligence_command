# M8 Upgrade Plan

Date: 2026-06-29
Baseline commit: `c70b2e2`

## Purpose

M7 is safety-ready. M8 should improve coverage, reduce manual review, and make the dashboard/chatbot more analytical without weakening the verifier.

The operating rule stays:

```text
Extraction proposes.
Retrieval finds missing context.
Repair patches weak candidates.
Verification proves or rejects.
Dashboard explains.
Chatbot analyzes.
GIS consumes only verified rules.
```

M8 is additive. It should live beside the current M7 pipeline until measured results prove it is safe to promote as the default path.

## M7 Measured Baseline

These results were re-run before this plan was created.

| Gate | Result |
|---|---|
| Compile active code | Pass |
| Consolidated status | `m7_safety_ready` |
| Current false verified total | `0` |
| Burnaby verified precision | `1.00` |
| Burnaby false verified | `0` |
| Burnaby false approvals | `0` |
| Burnaby extraction coverage recall | `0.97` |
| Adversarial cases | `24/24` blocked |
| Adversarial bundles | `3/3` blocked |
| M7 chatbot gold | `15/15`, hard failures `0` |
| Full tests | `590 passed, 3 subtests passed` |

M8 targets must be labeled as targets until measured outputs exist.

## Architecture Boundary

Current M7 flow:

```text
PDF/source corpus
-> M7 source discovery and evidence packs
-> M7 extraction candidates
-> source repair and matrix anchoring
-> deterministic verification
-> verified/review/rejected/not_used buckets
-> verified-only GIS/dashboard exports
```

M8 flow:

```text
M7 artifacts or source blocks
-> M8 structured contracts with source spans
-> hybrid retrieval and evidence bundles
-> bounded repair loop for weak candidates
-> dependency-aware M8 verification wrapper
-> M7 vs M8 analytics
-> dashboard data providers and analytic chatbot
```

The M8 verifier may wrap or call M7 verification, but it must not loosen any existing M7 check. New M8 statuses such as `context_required` and `repaired_successfully` are additive and must never silently map to current M7 `verified`.

## Proposed Module Layout

```text
src/burnaby_prototype/m8/
  __init__.py
  ingestion/source_blocks.py
  ingestion/source_span_store.py
  retrieval/hybrid_index.py
  retrieval/query_planner.py
  retrieval/evidence_bundle.py
  retrieval/reranker.py
  extraction/rule_schema.py
  extraction/rule_decomposer.py
  extraction/definition_extractor.py
  extraction/condition_extractor.py
  extraction/exception_extractor.py
  repair/repair_judge.py
  repair/repair_planner.py
  repair/patch_generator.py
  repair/patch_applier.py
  repair/repair_loop.py
  verification/structured_rule.py
  verification/dependency_checker.py
  verification/m8_verifier.py
  verification/verification_report.py
  analytics/coverage_metrics.py
  analytics/repair_metrics.py
  analytics/m7_m8_compare.py
  chatbot/analyst_tools.py
  chatbot/answer_policy.py
  chatbot/citation_builder.py
```

Dashboard work should prefer small data-provider modules and optional Streamlit pages instead of adding more orchestration to `dashboard/streamlit_app.py`.

## Checkpoint 1: M8 Data Contracts

Safest first checkpoint.

Create typed, serializable contracts:

| Contract | Purpose |
|---|---|
| `SourceSpan` | Exact source location: city, document ID, page, section, block type, char offsets, text |
| `EvidencePointer` | Pointer from a rule field to a source span |
| `EvidenceBundle` | Query, retrieved spans, ranking signals, source provenance |
| `StructuredRule` | Normalized rule claim with field-level evidence pointers |
| `RepairCritique` | Why a candidate failed or needs context |
| `RepairPatch` | Minimal candidate change proposed by repair |
| `RepairAttempt` | Critique, retrieval query, patch, verifier result |
| `VerificationDecision` | Status, reason, evidence IDs, unresolved dependencies, repair history |
| `M8RunSummary` | Run-level safety and coverage summary |

Tests:

- defaults fail closed
- missing source evidence cannot verify
- unknown status is rejected by validation
- JSON round trip preserves evidence pointers
- repair history is immutable enough for audit

Do not connect this to the M7 verifier yet. This checkpoint should be pure logic and tests.

## Checkpoint 2: Hybrid Retrieval MVP

Build local, deterministic retrieval over existing source chunks.

Required behavior:

- exact lexical search
- BM25 when available
- deterministic fallback if BM25 is missing
- metadata filters for city, page, section, rule family, block type
- query planner that emits exact phrases and semantic variants
- evidence bundle builder that preserves source provenance
- reranker/vector adapter interfaces without requiring online APIs

Tests:

- `maximum height R1` finds relevant local blocks
- metadata filters narrow results
- evidence bundles preserve source spans
- retrieval never writes verified outputs

## Checkpoint 3: Smart Repair Loop

Create a bounded repair loop for `review_needed` and `context_required` candidates.

Loop:

```text
judge failure
-> plan retrieval query
-> retrieve evidence
-> generate minimal patch
-> apply patch to candidate copy
-> rerun deterministic verification
-> keep best result
-> stop after fixed budget
```

Repair is not verification. Only the verifier can promote a rule.

Tests:

- missing evidence patch
- failed repair budget
- unit mismatch remains review-needed
- conflicting evidence cannot promote
- repair history is written
- repaired rule cannot bypass verifier

## Checkpoint 4: Dependency-Aware M8 Verification

Add an M8 verification wrapper that keeps M7 authoritative and adds dependency statuses.

Checks:

- value appears in evidence
- unit consistency
- comparator validity
- zone/scope consistency
- condition completeness
- exception completeness
- definition dependency
- overlay or cross-reference dependency
- conflicting source spans

Statuses:

```text
verified
repaired_successfully
context_required
review_needed
rejected
not_used
```

Rules:

- unresolved overlay/context means `context_required`, not `verified`
- repaired candidates become `repaired_successfully` only after deterministic checks pass
- contradictory spans remain `rejected` or `review_needed`

## Checkpoint 5: M7 vs M8 Analytics

Produce comparison summaries:

```text
outputs/m8_runs/<city>/m8_summary.json
outputs/m8_runs/<city>/m7_m8_comparison.json
```

Metrics:

- M7 verified count
- M8 verified count
- M8 repaired_successfully count
- review_needed before and after repair
- rejected count
- context_required count
- false verified count
- adversarial blocked count
- chatbot gold pass count
- rule coverage by city
- rule coverage by rule type
- repair success rate
- repair failure reasons

## Checkpoint 6: M8 Pipeline Script

Create `scripts/run_m8_pipeline.py`.

Required arguments:

```bash
--config configs/burnaby_r1.json
--city burnaby_r1
--input-dir outputs/m7_runs/burnaby_r1/google_gemini_3_1_flash_lite
--output-dir outputs/m8_runs/burnaby_r1/local_m8
--max-repair-attempts 3
--dry-run
```

The script must fail clearly if required M7 inputs are missing.

## Checkpoint 7: M8 Release Check

Create `scripts/run_m8_release_check.py`.

It should report pass/fail for:

- compileall
- M7 status
- M7 Burnaby benchmark
- M7 adversarial benchmark
- M7 chatbot gold
- M8 unit tests
- M8 pipeline smoke
- M8 comparison summary generation

Failures must be shown, not hidden.

## Checkpoint 8: Dashboard Upgrade

Do not start by editing the large Streamlit file.

First create pure dashboard data providers for:

- M7 vs M8 summary
- repaired rules
- review-needed reduction
- context-required rules
- unresolved dependencies
- evidence spans
- repair attempt history

Then connect them to optional pages:

```text
dashboard/pages/m8_overview.py
dashboard/pages/m8_rule_explorer.py
dashboard/pages/m8_repair_inspector.py
dashboard/pages/m8_benchmark_compare.py
dashboard/pages/m8_chatbot.py
```

Dashboard remains inspect-only.

## Checkpoint 9: Analytic Chatbot Upgrade

Build M8 chatbot tools over M8 artifacts, not over free-form guesses.

Questions it should answer:

- What changed from M7 to M8?
- Which rules were repaired?
- Why is this rule under review?
- Which rule types have weakest coverage?
- Which city has the most unresolved dependencies?
- What evidence supports this verified rule?
- How many review-needed rules were reduced by repair?
- Did M8 preserve the M7 zero-false-verified guarantee?
- What should a reviewer inspect next?

Policy:

- cite evidence IDs or source spans when possible
- distinguish verified from review-needed
- refuse unsupported claims
- explain uncertainty clearly
- never approve, verify, reject, or mutate rules

## Checkpoint 10: Documentation And Results

Create or update:

```text
M8_RESULTS.md
docs/m8_upgrade_explanation.html
```

Required split:

- M7 measured baseline
- M8 target outcomes
- M8 measured results, only after commands run
- remaining risks
- reviewer next steps

## Validation Cadence

Before and after safety-touching work:

```bash
.venv/bin/python -m compileall -q src scripts dashboard benchmark tests
.venv/bin/python scripts/run_consolidated_prototype.py status
.venv/bin/python benchmark/evaluate_benchmark.py --city burnaby_r1 --output-dir outputs/m7_runs/burnaby_r1/google_gemini_3_1_flash_lite
.venv/bin/python benchmark/evaluate_adversarial.py --config configs/burnaby_r1.json --cases benchmark/gold/burnaby_r1_adversarial_cases.json --bundle-cases benchmark/gold/burnaby_r1_adversarial_bundles.json
.venv/bin/python benchmark/evaluate_m7_chatbot.py --cases benchmark/gold/m7_chatbot_gold_cases.json
.venv/bin/python -m pytest -q
```

For pure M8 modules, run targeted M8 tests first, then the full M7 safety gates when integration begins.

## Risk Register

| Risk | Mitigation |
|---|---|
| M8 repair accidentally becomes verification | Keep repair outputs as candidates plus history; only verifier decisions can change status |
| Dashboard grows more coupled | Add pure data providers and optional pages first |
| M8 statuses confuse GIS consumers | Keep GIS export M7-compatible and verified-only until M8 release gates exist |
| Retrieval finds plausible but wrong context | Require field-level evidence pointers and deterministic verifier checks |
| New tests create broad churn | Scope tests to new M8 modules first |
| LLM/chatbot overclaims measured results | Force target vs measured wording in docs and answer policy |

## Definition Of Done For M8 MVP

M8 MVP is complete only when:

1. M7 validation still passes.
2. M8 data contracts exist and are tested.
3. Hybrid retrieval MVP exists and is tested.
4. Smart repair loop exists and is tested.
5. Dependency-aware M8 verifier exists and is tested.
6. M8 pipeline writes outputs.
7. M8 comparison analytics are generated.
8. M8 release check exists.
9. Dashboard has M8 analytic views or tested data providers.
10. Chatbot answers M8 analytic questions from artifacts.
11. `REFACTOR_LOG.md` documents every checkpoint.
12. `M8_RESULTS.md` separates measured results from targets.
13. No false verified rule is introduced.

## Implementation Status

Updated: 2026-06-29

| Requirement | Status |
|---|---|
| M8 data contracts | Implemented under `src/burnaby_prototype/m8/extraction/rule_schema.py` and tested |
| Hybrid retrieval MVP | Implemented under `src/burnaby_prototype/m8/retrieval/` and tested |
| Smart repair loop | Implemented under `src/burnaby_prototype/m8/repair/` and tested |
| Dependency-aware verification | Implemented under `src/burnaby_prototype/m8/verification/` and tested |
| M7 vs M8 analytics | Implemented under `src/burnaby_prototype/m8/analytics/` and tested |
| M8 pipeline script | Implemented at `scripts/run_m8_pipeline.py` |
| M8 bakeoff script | Implemented at `scripts/run_m8_bakeoff.py` |
| M8 release check | Implemented at `scripts/run_m8_release_check.py` |
| Dashboard data/views | Implemented in `dashboard/m8_data.py` and `dashboard/pages/m8_*.py` |
| Analytic chatbot | Implemented under `src/burnaby_prototype/m8/chatbot/` with `benchmark/evaluate_m8_chatbot.py` |
| Results documentation | Implemented in `M8_RESULTS.md` and `docs/m8_upgrade_explanation.html` |

Current M8 measured Burnaby R1 result:

| Metric | Value |
|---|---:|
| verified | 85 |
| repaired_successfully | 2 |
| context_required | 9 |
| review_needed | 48 |
| false_verified | 0 |
| false_approvals | 0 |
