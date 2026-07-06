# M8.5 Upgrade Plan

Date: 2026-06-29
Scope: M8.5 MVP planning and baseline preservation

## Purpose

M8 made the verifier output more structured, explainable, and repair-aware.
M8.5 should turn that diagnostic scaffold into a stronger verification
workbench.

Core message:

```text
M8 explained blocked rules.
M8.5 helps resolve blocked rules safely.
```

The trust boundary remains unchanged:

```text
Extraction proposes.
Retrieval finds missing context.
Repair patches weak candidates.
Verification proves or rejects.
Dashboard explains.
Chatbot analyzes.
GIS consumes only verified rules.
```

M8.5 is additive. It must live beside M7 and M8 until measured evidence proves
it is safe to promote as a default path.

## Current Baseline To Preserve

These are measured M8/M7 baseline values before any M8.5 runtime behavior was
implemented.

| Metric | Baseline |
|---|---:|
| M7 consolidated status | `m7_safety_ready` |
| Current false verified total | `0` |
| M8 structured rules | `144` |
| M8 verified | `85` |
| M8 repaired successfully | `2` |
| M8 verified-like total | `87` |
| M8 context required | `9` |
| M8 review needed | `48` |
| M8 false verified | `0` |
| M8 false approvals | `0` |
| M8 repair attempts | `171` |
| M8 new-loop successful repairs | `0` |
| M8 safety preserved | `true` |

Checkpoint 1 baseline validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_consolidated_prototype.py status` | Pass, `m7_safety_ready`, false verified total `0` |
| `.venv/bin/python scripts/run_m8_release_check.py` | Pass, M7 safety preserved `true` |
| `.venv/bin/python -m pytest -q` | Pass, `609 passed, 3 subtests passed` |

## M8.5 Goals

M8.5 should improve the ability to resolve blocked rules safely, especially
rules blocked by:

- table row or column ambiguity
- missing scope
- missing conditions
- missing exceptions
- definitions
- covenants
- heritage constraints
- cross-references
- city-specific rule wording

M8.5 should improve:

- evidence precision
- table lineage
- legal dependency resolution
- repair quality
- reviewer efficiency
- cross-city generalization
- artifact-grounded explanations

## Non-Goals

- Do not replace M7 verification.
- Do not weaken M7 or M8 safety gates.
- Do not let LLM output directly mark a rule as verified.
- Do not let repair directly promote a rule.
- Do not let dashboard actions directly promote a rule.
- Do not let chatbot answers override verifier decisions.
- Do not export `review_needed` or `context_required` rules into verified GIS output.
- Do not start by editing `dashboard/streamlit_app.py`.
- Do not claim measured improvement until the relevant command actually ran.

## Target Module Layout

```text
src/burnaby_prototype/m8_5/
  __init__.py

  tables/
    __init__.py
    table_block.py
    table_lineage.py
    table_parser.py
    table_rule_mapper.py
    table_confidence.py

  dependencies/
    __init__.py
    dependency_graph.py
    dependency_types.py
    cross_reference_index.py
    definition_linker.py
    exception_linker.py
    dependency_resolver.py

  repair_evaluation/
    __init__.py
    repair_evaluation.py
    patch_safety_checker.py
    verifier_ready_gate.py
    repair_scorecard.py

  review/
    __init__.py
    review_packet.py
    reviewer_actions.py
    review_state.py
    verifier_rerun_request.py

  multi_city/
    __init__.py
    city_run_matrix.py
    city_format_profile.py
    stress_test_runner.py
    generalization_report.py

  chatbot/
    __init__.py
    m8_5_analyst.py
    grounded_answer_policy.py
    review_workflow_answers.py

  analytics/
    __init__.py
    m8_5_summary.py
    table_metrics.py
    dependency_metrics.py
    repair_quality_metrics.py
    m8_to_m8_5_compare.py
```

Planned scripts:

```text
scripts/run_m8_5_pipeline.py
scripts/run_m8_5_release_check.py
scripts/run_m8_5_multi_city_stress.py
```

Planned dashboard surfaces:

```text
dashboard/pages/m8_5_table_explorer.py
dashboard/pages/m8_5_dependency_graph.py
dashboard/pages/m8_5_repair_workbench.py
dashboard/pages/m8_5_reviewer_queue.py
dashboard/pages/m8_5_multi_city_compare.py
```

## Checkpoints

### Checkpoint 1: Planning And Baseline Preservation

Status: completed in planning form.

Deliverables:

- `M8_5_PLAN.md`
- `M8_5_RESULTS.md`
- M8.5 section in `REFACTOR_LOG.md`
- Baseline validation results recorded

No verifier, pipeline, dashboard, or chatbot behavior changes are allowed in
this checkpoint.

### Checkpoint 2: Table-Aware Parsing And Row/Column Lineage

Lowest-risk first implementation checkpoint.

Status: implemented as pure contracts and tests; not yet connected to the M8.5
pipeline or verifier.

Built pure table lineage contracts and tests before connecting anything to the
verifier:

- `TableBlock`
- `TableCell`
- `TableCellLineage`
- `TableDerivedRule`
- `TableParseDiagnostic`

Implemented modules:

- `src/burnaby_prototype/m8_5/__init__.py`
- `src/burnaby_prototype/m8_5/tables/__init__.py`
- `src/burnaby_prototype/m8_5/tables/table_block.py`
- `src/burnaby_prototype/m8_5/tables/table_confidence.py`
- `src/burnaby_prototype/m8_5/tables/table_lineage.py`
- `src/burnaby_prototype/m8_5/tables/table_parser.py`
- `src/burnaby_prototype/m8_5/tables/table_rule_mapper.py`

Each table-derived rule must preserve:

- source document
- page
- section ID
- table ID
- row index
- column index
- row label
- column label
- cell text
- normalized value
- normalized unit
- inferred rule type
- confidence
- parse warnings
- source span reference

Required tests:

- row label preserved
- column label preserved
- wrong column does not map to wrong rule type
- merged or blank cells produce review diagnostics
- value without row context cannot be verifier-ready
- table lineage serializes to JSON
- table-derived rules preserve source spans

Measured validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_table_lineage.py tests/test_m8_5_table_rule_mapper.py` | Pass, `9 passed` |
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_consolidated_prototype.py status` | Pass, `m7_safety_ready`, false verified total `0` |
| `.venv/bin/python scripts/run_m8_release_check.py` | Pass |
| `.venv/bin/python -m pytest -q` | Pass, `618 passed, 3 subtests passed` |

Safety note:

- Table-derived rules are emitted as `candidate_only` M8.5 objects.
- `to_verifier_candidate()` sets `verification_decision` to `review_needed`.
- Table-derived rules cannot mark themselves verified.
- Value-only cells without row context are not verifier-ready.

### Checkpoint 3: Legal Dependency Graph

Status: implemented as pure contracts, lookup, resolver, and tests; not yet
connected to the M8.5 pipeline or dashboard.

Built dependency contracts and lookup without promoting rules:

- `RuleDependency`
- `DependencyGraph`
- `DependencyResolver`
- `CrossReferenceIndex`
- `DefinitionLinker`
- `ExceptionLinker`

Implemented modules:

- `src/burnaby_prototype/m8_5/dependencies/__init__.py`
- `src/burnaby_prototype/m8_5/dependencies/dependency_types.py`
- `src/burnaby_prototype/m8_5/dependencies/dependency_graph.py`
- `src/burnaby_prototype/m8_5/dependencies/cross_reference_index.py`
- `src/burnaby_prototype/m8_5/dependencies/definition_linker.py`
- `src/burnaby_prototype/m8_5/dependencies/exception_linker.py`
- `src/burnaby_prototype/m8_5/dependencies/dependency_resolver.py`

Dependency statuses:

- `resolved`
- `unresolved`
- `conflicting`
- `not_applicable`

Dependency types:

- `definition`
- `condition`
- `exception`
- `cross_reference`
- `overlay`
- `covenant`
- `heritage`
- `measurement_method`
- `rule_family`
- `table_context`
- `city_specific_scope`

Measured validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_dependency_graph.py tests/test_m8_5_dependency_resolver.py` | Pass, `8 passed` |
| `.venv/bin/python -m pytest -q tests/test_m8_5_*.py` | Pass, `17 passed` |
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_consolidated_prototype.py status` | Pass, `m7_safety_ready`, false verified total `0` |
| `.venv/bin/python scripts/run_m8_release_check.py` | Pass |
| `.venv/bin/python -m pytest -q` | Pass, `626 passed, 3 subtests passed` |

Safety note:

- The dependency resolver only creates graph artifacts and a recommended status.
- Unresolved dependencies recommend `context_required`.
- Conflicting dependencies recommend `review_needed`.
- Resolved dependencies allow the existing verifier status to stand.
- Dependency artifacts do not promote rules and do not modify GIS exports.

### Checkpoint 4: Repair Evaluator

Status: implemented as pure contracts, patch safety checks, verifier-ready gate,
scorecard, and tests; not yet connected to the M8.5 pipeline.

Built a safety evaluator for proposed patches.

It must answer:

- What was the original failure?
- What fields changed?
- Which evidence supports the changed fields?
- Did the patch introduce a dependency?
- Did it create contradiction risk?
- Is it ready for deterministic verification?
- Should it go to human review?

Patch safety categories:

- `safe_for_verifier`
- `needs_human_review`
- `insufficient_evidence`
- `contradictory_evidence`
- `introduced_dependency`
- `unsafe_field_change`
- `unsupported_patch`

The evaluator still cannot promote a rule.

Implemented modules:

- `src/burnaby_prototype/m8_5/repair_evaluation/__init__.py`
- `src/burnaby_prototype/m8_5/repair_evaluation/repair_evaluation.py`
- `src/burnaby_prototype/m8_5/repair_evaluation/patch_safety_checker.py`
- `src/burnaby_prototype/m8_5/repair_evaluation/verifier_ready_gate.py`
- `src/burnaby_prototype/m8_5/repair_evaluation/repair_scorecard.py`

Measured validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_repair_evaluator.py` | Pass, `8 passed` |
| `.venv/bin/python -m pytest -q tests/test_m8_5_*.py` | Pass, `25 passed` |
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_consolidated_prototype.py status` | Pass, `m7_safety_ready`, false verified total `0` |
| `.venv/bin/python scripts/run_m8_release_check.py` | Pass |
| `.venv/bin/python -m pytest -q` | Pass, `634 passed, 3 subtests passed` |

Safety note:

- `safe_for_verifier` means ready for deterministic verifier submission, not
  verified.
- The evaluator cannot recommend `verified`.
- Missing evidence, wrong zone context, contradictions, introduced exceptions,
  and unsafe exception removal all fail closed.
- Repair history is preserved for audit.

### Checkpoint 5: Reviewer Workbench Data Model

Status: implemented as pure review packet, reviewer action, state, and verifier
rerun request contracts; connected to the M8.5 pipeline as generated artifacts,
but not yet connected to dashboard pages.

Built auditable review artifacts:

- `ReviewPacket`
- `ReviewerAction`
- `ReviewState`
- `VerifierRerunRequest`

Reviewer actions may approve evidence or context, but must trigger verifier
rerun. They cannot directly mark a rule as verified.

Implemented modules:

- `src/burnaby_prototype/m8_5/review/__init__.py`
- `src/burnaby_prototype/m8_5/review/review_packet.py`
- `src/burnaby_prototype/m8_5/review/reviewer_actions.py`
- `src/burnaby_prototype/m8_5/review/review_state.py`
- `src/burnaby_prototype/m8_5/review/verifier_rerun_request.py`

Measured validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_review_packet.py` | Pass, `7 passed` |
| `.venv/bin/python -m pytest -q tests/test_m8_5_*.py` | Pass, `32 passed` |
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_consolidated_prototype.py status` | Pass, `m7_safety_ready`, false verified total `0` |
| `.venv/bin/python scripts/run_m8_release_check.py` | Pass |

Safety note:

- Direct verification actions such as `mark_verified` raise `ValueError`.
- Evidence/context approvals create `VerifierRerunRequest` artifacts.
- Rejected evidence keeps the rule in review.
- Reviewer notes are preserved for audit.
- Review packets serialize enough context for dashboard display.
- Reviewer workflow artifacts cannot promote a rule.

### Checkpoint 6: M8.5 Pipeline Script

Status: implemented and measured on the Burnaby M8 input artifacts.

Created `scripts/run_m8_5_pipeline.py`.

Required default command shape:

```bash
.venv/bin/python scripts/run_m8_5_pipeline.py \
  --city burnaby_r1 \
  --config configs/burnaby_r1.json \
  --m8-input-dir outputs/m8_runs/burnaby_r1/local_m8 \
  --output-dir outputs/m8_5_runs/burnaby_r1/local_m8_5 \
  --max-repair-attempts 3 \
  --enable-table-parsing \
  --enable-dependency-graph \
  --enable-review-packets \
  --dry-run
```

The script fails clearly if required input artifacts are missing.

Implemented outputs:

- `outputs/m8_5_runs/burnaby_r1/local_m8_5/table_blocks.json`
- `outputs/m8_5_runs/burnaby_r1/local_m8_5/table_cell_lineage.json`
- `outputs/m8_5_runs/burnaby_r1/local_m8_5/table_derived_rules.json`
- `outputs/m8_5_runs/burnaby_r1/local_m8_5/dependency_graph.json`
- `outputs/m8_5_runs/burnaby_r1/local_m8_5/dependency_resolutions.json`
- `outputs/m8_5_runs/burnaby_r1/local_m8_5/repair_evaluations.json`
- `outputs/m8_5_runs/burnaby_r1/local_m8_5/review_packets.json`
- `outputs/m8_5_runs/burnaby_r1/local_m8_5/verifier_rerun_requests.json`
- `outputs/m8_5_runs/burnaby_r1/local_m8_5/m8_5_structured_rules.json`
- `outputs/m8_5_runs/burnaby_r1/local_m8_5/m8_5_verification_decisions.json`
- `outputs/m8_5_runs/burnaby_r1/local_m8_5/m8_m8_5_comparison.json`
- `outputs/m8_5_runs/burnaby_r1/local_m8_5/m8_5_summary.json`
- `outputs/m8_5_runs/burnaby_r1/local_m8_5/m8_5_chatbot_context.json`
- `outputs/m8_5_runs/burnaby_r1/local_m8_5/m8_5_summary.md`

Measured Burnaby output:

| Metric | Measured |
|---|---:|
| Table-derived rules | `137` |
| Dependencies | `4` |
| Repair evaluations | `171` |
| Verifier-ready patches | `78` |
| Review packets | `57` |
| False verified | `0` |
| False approvals | `0` |
| M7/M8 safety preserved | `true` |

Measured validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_*.py` | Pass, `34 passed` |
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_consolidated_prototype.py status` | Pass, `m7_safety_ready`, false verified total `0` |
| `.venv/bin/python scripts/run_m8_release_check.py` | Pass |
| `.venv/bin/python scripts/run_m8_5_pipeline.py --city burnaby_r1 --config configs/burnaby_r1.json --m8-input-dir outputs/m8_runs/burnaby_r1/local_m8 --output-dir outputs/m8_5_runs/burnaby_r1/local_m8_5 --max-repair-attempts 3 --enable-table-parsing --enable-dependency-graph --enable-review-packets --dry-run` | Pass |
| `.venv/bin/python -m pytest -q` | Pass, `643 passed, 3 subtests passed` |

Safety note:

- Table-derived rules are appended as candidate records, not verified records.
- Repair evaluations can mark patches `ready_for_verifier`, but cannot mark a
  rule `verified`.
- Reviewer packets and rerun requests are artifacts only.
- The M7/M8 verifier code was not weakened.

### Checkpoint 7: M8.5 Analytics

Status: implemented as reusable analytics modules, wired into
`scripts/run_m8_5_pipeline.py`, and tested.

Compare M8 to M8.5 with explicit measured-vs-target labeling.

Required metrics include:

- verified-like count
- false verified count
- false approval count
- review-needed count
- context-required count
- table-derived rule counts
- dependency status counts
- repair evaluation counts
- verifier-ready patch counts
- reviewer packet counts
- coverage by rule type
- coverage by city
- coverage by dependency type
- coverage by table vs prose source

Implemented modules:

- `src/burnaby_prototype/m8_5/analytics/__init__.py`
- `src/burnaby_prototype/m8_5/analytics/m8_5_summary.py`
- `src/burnaby_prototype/m8_5/analytics/table_metrics.py`
- `src/burnaby_prototype/m8_5/analytics/dependency_metrics.py`
- `src/burnaby_prototype/m8_5/analytics/repair_quality_metrics.py`
- `src/burnaby_prototype/m8_5/analytics/m8_to_m8_5_compare.py`

Measured Burnaby analytics:

| Metric | Measured |
|---|---:|
| M8 verified-like count | `87` |
| M8.5 verified-like count | `87` |
| Table-derived rules | `137` |
| Table-derived verified | `0` |
| Table-derived review/candidate count | `137` |
| Dependency total | `4` |
| Dependency unresolved | `4` |
| Repair evaluations | `171` |
| Verifier-ready patches | `78` |
| Review packets | `57` |
| False verified | `0` |
| False approvals | `0` |

Measured-vs-not-run labeling:

- `m8_verified_like_count`, `m8_5_verified_like_count`, false verified,
  false approvals, table-derived rule count, dependency total, repair
  evaluations, and reviewer packets are labeled `measured`.
- At Checkpoint 7, M8.5 chatbot gold and M8.5 multi-city stress were labeled
  as not run. They are now measured in Checkpoints 9 and 10.

Measured validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_analytics.py tests/test_m8_5_pipeline.py` | Pass, `8 passed` |
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_m8_5_pipeline.py --city burnaby_r1 --config configs/burnaby_r1.json --m8-input-dir outputs/m8_runs/burnaby_r1/local_m8 --output-dir outputs/m8_5_runs/burnaby_r1/local_m8_5 --max-repair-attempts 3 --enable-table-parsing --enable-dependency-graph --enable-review-packets --dry-run` | Pass |

### Checkpoint 8: Dashboard Pages

Status: implemented as modular data provider plus optional Streamlit pages.
No logic was added to `dashboard/streamlit_app.py`.

Added modular data providers and optional pages. Do not collapse logic into
`dashboard/streamlit_app.py`.

Dashboard can inspect review actions and verifier rerun requests, but it cannot
promote rules.

Implemented files:

- `dashboard/m8_5_data.py`
- `dashboard/pages/m8_5_table_explorer.py`
- `dashboard/pages/m8_5_dependency_graph.py`
- `dashboard/pages/m8_5_repair_workbench.py`
- `dashboard/pages/m8_5_reviewer_queue.py`
- `dashboard/pages/m8_5_multi_city_compare.py`
- `tests/test_m8_5_dashboard_data.py`

Dashboard views:

- table-derived rules and row/column lineage
- dependency graph per rule
- repair evaluation scorecard rows
- reviewer queue with priority sorting
- M8.5 metric states and coverage comparison

Measured validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_dashboard_data.py tests/test_m8_5_analytics.py` | Pass, `10 passed` |
| `.venv/bin/python -m pytest -q tests/test_m8_5_*.py` | Pass, `44 passed` |
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_m8_5_pipeline.py --city burnaby_r1 --config configs/burnaby_r1.json --m8-input-dir outputs/m8_runs/burnaby_r1/local_m8 --output-dir outputs/m8_5_runs/burnaby_r1/local_m8_5 --max-repair-attempts 3 --enable-table-parsing --enable-dependency-graph --enable-review-packets --dry-run` | Pass |

Safety note:

- Dashboard pages are read-only artifact inspectors.
- Review priority sorting is a display helper, not a status change.
- Dashboard code cannot mark a rule verified.

### Checkpoint 9: Artifact-Grounded M8.5 Chatbot

Status: implemented as deterministic artifact-grounded chatbot, evaluator, and
25 gold cases.

Add at least 25 gold cases:

- 5 safety questions
- 5 table lineage questions
- 5 dependency graph questions
- 5 repair evaluation questions
- 5 reviewer workflow questions

The chatbot must answer from artifacts only and must say `not available` when
required artifacts are missing.

Implemented files:

- `src/burnaby_prototype/m8_5/chatbot/__init__.py`
- `src/burnaby_prototype/m8_5/chatbot/grounded_answer_policy.py`
- `src/burnaby_prototype/m8_5/chatbot/m8_5_analyst.py`
- `src/burnaby_prototype/m8_5/chatbot/review_workflow_answers.py`
- `benchmark/gold/m8_5_chatbot_gold_cases.json`
- `benchmark/evaluate_m8_5_chatbot.py`
- `tests/test_m8_5_chatbot_grounding.py`

Measured validation:

| Command | Result |
|---|---|
| `.venv/bin/python scripts/run_m8_5_pipeline.py --city burnaby_r1 --config configs/burnaby_r1.json --m8-input-dir outputs/m8_runs/burnaby_r1/local_m8 --output-dir outputs/m8_5_runs/burnaby_r1/local_m8_5 --max-repair-attempts 3 --enable-table-parsing --enable-dependency-graph --enable-review-packets --dry-run` | Pass |
| `.venv/bin/python -m pytest -q tests/test_m8_5_chatbot_grounding.py tests/test_m8_5_pipeline.py` | Pass, `8 passed` |
| `.venv/bin/python benchmark/evaluate_m8_5_chatbot.py --output-dir outputs/m8_5_runs/burnaby_r1/local_m8_5` | Pass, `25/25`, hard failures `0` |

Safety note:

- The chatbot refuses legal overrides and direct verification requests.
- It answers from M8.5 artifacts only.
- It says `not available` when required artifacts are missing.
- `ready_for_verifier` is explained as not verified.

### Checkpoint 10: Multi-City Stress Test

Status: implemented and measured for available cities only.

Support available cities only:

- `burnaby_r1`
- `vancouver_rs`
- `calgary_rcg`

Do not invent Surrey data. Missing city data should produce a clear skip reason.

Implemented files:

- `src/burnaby_prototype/m8_5/multi_city/__init__.py`
- `src/burnaby_prototype/m8_5/multi_city/city_run_matrix.py`
- `src/burnaby_prototype/m8_5/multi_city/city_format_profile.py`
- `src/burnaby_prototype/m8_5/multi_city/generalization_report.py`
- `src/burnaby_prototype/m8_5/multi_city/stress_test_runner.py`
- `scripts/run_m8_5_multi_city_stress.py`
- `tests/test_m8_5_multi_city_metrics.py`

Measured output:

| City | Status | Table-derived rules | Dependencies | Review packets | False verified |
|---|---|---:|---:|---:|---:|
| `burnaby_r1` | measured | `137` | `4` | `57` | `0` |
| `vancouver_rs` | measured | `0` | `3` | `32` | `0` |
| `calgary_rcg` | measured | `0` | `1` | `46` | `0` |

Cross-city summary:

| Metric | Measured |
|---|---:|
| Measured cities | `3` |
| Skipped cities | `0` |
| Failed cities | `0` |
| False verified total | `0` |
| False approval total | `0` |

Measured validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_multi_city_metrics.py tests/test_m8_5_chatbot_grounding.py` | Pass, `10 passed` |
| `.venv/bin/python scripts/run_m8_5_multi_city_stress.py --dry-run` | Pass, measured `3`, skipped `0`, failed `0`, false verified total `0` |
| `.venv/bin/python benchmark/evaluate_m8_5_chatbot.py --output-dir outputs/m8_5_runs/burnaby_r1/local_m8_5` | Pass, `25/25`, hard failures `0` |

Safety note:

- Only configured cities are run.
- Missing city data is skipped with a reason.
- The stress script does not invent Surrey or any unavailable city.
- Cross-city safety aggregates false verified and false approval counts.

### Checkpoint 11: M8.5 Release Check

Status: implemented and passing.

Created `scripts/run_m8_5_release_check.py`.

It should run:

- compileall
- M7 status
- M8 release check if available
- M8.5 unit tests
- M8.5 pipeline smoke test
- M8.5 chatbot gold
- M8.5 multi-city dry run
- summary artifact existence checks

Measured validation:

| Check | Return code |
|---|---:|
| compileall | `0` |
| M7 status | `0` |
| M8 release check | `0` |
| M8.5 unit tests | `0` |
| M8.5 pipeline smoke | `0` |
| M8.5 multi-city dry run | `0` |
| M8.5 chatbot gold | `0` |
| artifact existence | `0` |

Release safety:

| Metric | Measured |
|---|---:|
| False verified count | `0` |
| False approval count | `0` |
| Cross-city false verified total | `0` |
| Cross-city false approval total | `0` |
| Passed | `true` |

### Checkpoint 12: Documentation And Stakeholder Explanation

Status: implemented.

Created or updated:

- `M8_5_PLAN.md`
- `M8_5_RESULTS.md`
- `docs/m8_5_upgrade_explanation.html`
- optional Canva/Figma-ready stakeholder section

Implemented documentation:

- `M8_5_PLAN.md` records checkpoints, safety constraints, measured
  validation, and acceptance criteria.
- `M8_5_RESULTS.md` separates measured results from targets and records
  Checkpoints 1-11.
- `REFACTOR_LOG.md` documents every implemented checkpoint.
- `docs/m8_5_upgrade_explanation.html` provides a stakeholder and worker
  explanation with diagrams, tables, measured results, limitations, and M9
  direction.

Documentation coverage:

- M8 baseline
- M8.5 problem statement
- what M8.5 adds
- why table lineage matters
- why dependency graph matters
- why repair evaluator matters
- why reviewer workbench matters
- M8-vs-M8.5 comparison
- measured results
- target/future results clearly labeled
- remaining limitations
- M9 direction

## Acceptance Criteria For M8.5 MVP

M8.5 MVP is done only when:

1. M7 safety still passes.
2. Existing M8 safety still passes or failures are clearly documented.
3. Table lineage models exist and are tested.
4. Table-derived rules can be generated without direct promotion.
5. Dependency graph exists and is tested.
6. Dependency-aware outcomes are visible in artifacts.
7. Repair evaluator exists and is tested.
8. Reviewer packets exist and are tested.
9. M8.5 pipeline script writes outputs.
10. M8.5 analytics compare M8 and M8.5.
11. Dashboard data providers/pages can inspect table lineage, dependencies,
    repair evaluations, and reviewer packets.
12. Chatbot can answer M8.5 analytic questions from artifacts.
13. Multi-city dry run or stress test exists.
14. M8.5 release check exists.
15. `REFACTOR_LOG.md` documents every checkpoint.
16. `M8_5_RESULTS.md` separates measured results from targets.
17. False verified remains `0`.
18. False approvals remain `0`.
19. Repair still cannot promote directly.
20. GIS verified-only boundary remains preserved.

## Validation Commands

Baseline and recurring gates:

```bash
.venv/bin/python -m compileall -q src scripts dashboard benchmark tests
.venv/bin/python scripts/run_consolidated_prototype.py status
.venv/bin/python scripts/run_m8_release_check.py
.venv/bin/python -m pytest -q
```

Future M8.5 gates:

```bash
.venv/bin/python -m pytest -q tests/test_m8_5_*.py
.venv/bin/python scripts/run_m8_5_pipeline.py --city burnaby_r1 --config configs/burnaby_r1.json --m8-input-dir outputs/m8_runs/burnaby_r1/local_m8 --output-dir outputs/m8_5_runs/burnaby_r1/local_m8_5 --max-repair-attempts 3 --enable-table-parsing --enable-dependency-graph --enable-review-packets --dry-run
.venv/bin/python scripts/run_m8_5_multi_city_stress.py --dry-run
.venv/bin/python scripts/run_m8_5_release_check.py
```

## Known Risks

- Table parsing can create false confidence if row/column labels are dropped.
- Cross-references and exceptions may require source sections not present in the
  current M8 artifact bundle.
- Repair evaluation is safety-critical and must be fail-closed.
- Reviewer workflow may appear to "approve" a rule unless action names and
  rerun requests make the verifier boundary explicit.
- Multi-city outputs may expose format assumptions that only hold for Burnaby.
- Dashboard and chatbot changes can accidentally imply authority if they do not
  cite verifier artifacts.

## Rollback Strategy

- Keep M8.5 under `src/burnaby_prototype/m8_5/` and `outputs/m8_5_runs/`.
- Do not edit M7 verifier behavior to support M8.5 checkpoints.
- Do not replace M8 outputs; read them as inputs.
- If an M8.5 checkpoint fails safety gates, leave M7/M8 artifacts as the
  authoritative current outputs and mark M8.5 results as failed or not measured.
- Keep dashboard pages optional and artifact-backed.
- Preserve the ability to run:

```bash
.venv/bin/python scripts/run_consolidated_prototype.py status
.venv/bin/python scripts/run_m8_release_check.py
```

without any M8.5 artifacts.
