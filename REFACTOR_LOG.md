# Refactor Log

Date: 2026-06-29

## Baseline Read

Files and surfaces inspected:

- `README.md`, `pyproject.toml`, `requirements.txt`, `.streamlit/config.toml`, `.gitignore`.
- Main CLI entrypoints: `scripts/run_consolidated_prototype.py`, `scripts/run_m7_status_report.py`, `scripts/run_m7_bakeoff.py`, `scripts/run_m7_bakeoff_engine.py`.
- Main app entrypoint: `dashboard/streamlit_app.py`.
- Retrieval/chat surface: `dashboard/bylaw_retrieval.py`, `src/burnaby_prototype/bylaw_chat.py`.
- Core package surfaces: `src/burnaby_prototype/config.py`, `verification.py`, `slim_pipeline.py`, `m7_measure.py`, M7 extraction/discovery modules.
- Tests: 31 `tests/test_*.py` files.
- City data/configs: `configs/{burnaby_r1,calgary_rcg,vancouver_rs}.json` and matching `data/bylaws/<city>/source.pdf`.

Observed structure:

- Python package under `src/burnaby_prototype`.
- Streamlit dashboard under `dashboard`.
- CLI orchestration under `scripts`.
- Benchmark and safety gates under `benchmark`.
- Current M7 outputs under `outputs/m7_*`.
- Historical records under `archive/pre_m7_records`.

Important module sizes:

| File | Lines | Risk |
|---|---:|---|
| `dashboard/streamlit_app.py` | 5745 | Large UI/orchestration coupling point |
| `src/burnaby_prototype/m7_measure.py` | 2403 | Measurement/reporting complexity |
| `src/burnaby_prototype/verification.py` | 1336 | Safety-critical verifier |
| `src/burnaby_prototype/bylaw_chat.py` | 1257 | Chat policy/retrieval logic |
| `src/burnaby_prototype/slim_pipeline.py` | 999 | Main verifier orchestration |
| `scripts/run_m7_bakeoff_engine.py` | 542 | Extraction/discovery orchestration |

## Checkpoint 1: M7 Naming And Archive Cleanup

What changed:

- Active scripts/modules/tests/docs were renamed to M7-facing names.
- Pre-M7 docs/scripts/advisory module/output records were moved under `archive/pre_m7_records/`.
- Current generated output names were normalized from old `v3_gap_report.*` to `m7_gap_report.*`.
- Current status labels now report `m7_safety_ready`, not MVP wording.
- Disposable caches were removed after validation.

Why:

- M7.5 work needs one current surface. Old V2/V3/M4/M5/M6/MVP names in active paths made the architecture harder to understand and raised the risk of importing the wrong layer.

Validation:

| Command | Result |
|---|---|
| `rg` stale active names across README/docs/scripts/src/dashboard/benchmark/tests/current outputs | Pass, no active old M4/M5/M6/V2/V3/MVP names found |
| `.venv/bin/python scripts/run_consolidated_prototype.py status` | Pass, `m7_safety_ready`, false verified total `0` |
| `.venv/bin/python -m pytest -q` | Pass, `590 passed, 3 subtests passed` |

Remaining risks:

- Some valid adapter/provenance references still use Pipeline 5/Pipeline 9 terminology. Those should remain only where they describe upstream input formats or historical provenance.

## Checkpoint 2: Install And Dependency Surface

What changed:

- Added `pypdf>=4.0` and `rank-bm25>=0.2.2` to `requirements.txt`.
- Added `pytest>=8.0` and `hypothesis>=6.100` to `requirements.txt` so the documented full test command is reproducible.
- Added `pypdf>=4.0` to package dependencies in `pyproject.toml`.
- Updated dashboard extra to include `streamlit>=1.46` and `plotly>=5.24`.
- Updated `dev` extra to include Streamlit, Plotly, pytest, and Hypothesis.
- Reworded optional extraction comments so M7 is the current product path.
- Renamed an old source-version alias to `M7_SOURCE_VERSION` in `scripts/run_m7_bakeoff_engine.py`.
- Updated README quick start to use `pip install -r requirements.txt`, editable install, and `pytest`.

Why:

- The documented commands imported `pypdf`, `rank_bm25`, Streamlit, Plotly, pytest, and Hypothesis, but not all were declared in install files.
- The M7 engine still had an old internal variable name that did not match the renamed module.

Validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pip show pypdf rank-bm25 pytest hypothesis streamlit plotly jsonschema` | Pass, packages present |
| `.venv/bin/python -m pip check` | Pass, no broken requirements |
| `.venv/bin/python -m pip install -r requirements.txt --no-index` | Pass, all requirements already satisfied offline |
| `.venv/bin/python -m pip install -e .` | Fails in sandbox: build isolation tries to fetch `setuptools>=68` from PyPI and DNS is blocked |
| `.venv/bin/python -m pip install -e . --no-build-isolation` | Pass, editable install built and installed locally |
| `.venv/bin/python -m pip wheel --no-deps --no-build-isolation . -w /private/tmp/burnaby_m7_wheel` | Pass, wheel built |

Remaining risks:

- In an offline environment, use `--no-build-isolation` after creating the venv. In a normal networked environment, plain `pip install -e .` should work.
- The repo has no lockfile; dependency versions are lower-bounded, not pinned.

## Checkpoint 3: Build, Safety, Dashboard, And Test Validation

What changed:

- No behavior change in verifier/dashboard logic.
- Refactor artifacts added: `REFACTOR_PLAN.md` and `REFACTOR_LOG.md`.

Validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_consolidated_prototype.py status` | Pass, `m7_safety_ready`, false verified total `0` |
| `.venv/bin/python benchmark/evaluate_benchmark.py --city burnaby_r1 --output-dir outputs/m7_runs/burnaby_r1/google_gemini_3_1_flash_lite` | Pass, verified precision `1.00`, false verified `0`, false approvals `0` |
| `.venv/bin/python benchmark/evaluate_adversarial.py --config configs/burnaby_r1.json --cases benchmark/gold/burnaby_r1_adversarial_cases.json --bundle-cases benchmark/gold/burnaby_r1_adversarial_bundles.json` | Pass, 24/24 cases blocked, 3/3 bundles blocked |
| `.venv/bin/python benchmark/evaluate_m7_chatbot.py --cases benchmark/gold/m7_chatbot_gold_cases.json` | Pass, 15/15, hard failures `0` |
| `.venv/bin/python -m pytest -q` | Pass, 590 tests and 3 subtests |
| Streamlit startup on port 8620 plus `curl -s http://127.0.0.1:8620/_stcore/health` | Pass with elevated local socket permission, returned `ok` |

Lint/type status:

| Command | Result |
|---|---|
| `.venv/bin/python -m ruff check .` | Not configured: `No module named ruff` |
| `.venv/bin/python -m mypy src scripts dashboard benchmark tests` | Not configured: `No module named mypy` |
| Search for lint/type config in `pyproject.toml` and active docs/code | No configured lint/type gate found |

Remaining risks:

- Add a real lint gate only after agreeing on the style baseline; running a new linter cold on this codebase would likely create broad churn.
- Add a typecheck gate incrementally around pure logic modules first, not the entire Streamlit app.
- Dashboard health proves startup, not full browser rendering or interaction coverage.

## Self-Review Notes

- No verifier safety rule was loosened.
- No dashboard user flow was redesigned.
- Dependency changes are directly tied to imported modules and documented validation commands.
- The only code rename in this checkpoint is a local constant alias from V2 to M7; behavior is unchanged.
- Historical records remain archived, not deleted.
- `.env` is ignored and untracked; it contains `OPENROUTER_API_KEY`, so it must stay out of commits.

## M8 Planning Checkpoint: Baseline And Execution Plan

Date: 2026-06-29
Baseline commit: `c70b2e2`

What was inspected:

- `REFACTOR_LOG.md`
- `REFACTOR_PLAN.md`
- `README.md`
- `pyproject.toml`
- `requirements.txt`
- `scripts/run_consolidated_prototype.py`
- `scripts/run_m7_status_report.py`
- `scripts/run_m7_bakeoff.py`
- `scripts/run_m7_bakeoff_engine.py`
- `src/burnaby_prototype/verification.py`
- `src/burnaby_prototype/slim_pipeline.py`
- `src/burnaby_prototype/m7_measure.py`
- `src/burnaby_prototype/bylaw_chat.py`
- `dashboard/streamlit_app.py`
- `dashboard/bylaw_retrieval.py`
- `benchmark/`
- `configs/`
- `tests/`

Baseline validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_consolidated_prototype.py status` | Pass, `m7_safety_ready`, false verified total `0` |
| `.venv/bin/python benchmark/evaluate_benchmark.py --city burnaby_r1 --output-dir outputs/m7_runs/burnaby_r1/google_gemini_3_1_flash_lite` | Pass, verified precision `1.00`, false verified `0`, false approvals `0`, extraction coverage recall `0.97` |
| `.venv/bin/python benchmark/evaluate_adversarial.py --config configs/burnaby_r1.json --cases benchmark/gold/burnaby_r1_adversarial_cases.json --bundle-cases benchmark/gold/burnaby_r1_adversarial_bundles.json` | Pass, 24/24 cases blocked, 3/3 bundles blocked |
| `.venv/bin/python benchmark/evaluate_m7_chatbot.py --cases benchmark/gold/m7_chatbot_gold_cases.json` | Pass, 15/15 cases, hard failures `0` |
| `.venv/bin/python -m pytest -q` | Pass, 590 tests and 3 subtests |

What changed:

- Added `M8_PLAN.md`, a checkpoint-by-checkpoint execution plan for the M8 upgrade.
- No runtime code was changed in this checkpoint.
- No dashboard behavior was changed.
- No verifier rule was loosened.

Safest first checkpoint:

- Start with M8 data contracts under `src/burnaby_prototype/m8/`.
- Keep the work pure and additive: typed records, JSON round trips, fail-closed defaults, and unit tests.
- Do not connect M8 contracts to the M7 verifier until the contracts and tests are stable.

M8 principle recorded:

```text
Extraction proposes.
Retrieval finds missing context.
Repair patches weak candidates.
Verification proves or rejects.
Dashboard explains.
Chatbot analyzes.
GIS consumes only verified rules.
```

Remaining risks:

- `dashboard/streamlit_app.py` remains a large coupling point and should not be the first M8 edit target.
- `m7_measure.py` remains a broad measurement/reporting module; M8 analytics should be smaller and tested separately.
- Repair logic is the highest safety-risk M8 feature; it must remain candidate-only until deterministic verification accepts a result.
- M8 target outcomes must not be described as measured until M8 output artifacts and release checks exist.

## M8 Implementation Checkpoint: MVP Artifacts

Date: 2026-06-29

What changed:

- Added additive M8 package modules under `src/burnaby_prototype/m8/`.
- Added typed source-span and structured-rule contracts with fail-closed defaults.
- Added deterministic local hybrid retrieval with BM25/fallback support and evidence-bundle construction.
- Added bounded repair loop modules. Repair only patches candidates and records history; it cannot promote directly.
- Added dependency-aware M8 verifier wrapper. M7 verification remains the proof gate.
- Added M7-vs-M8 analytics, M8 chatbot analysis helpers, and an M8 chatbot benchmark.
- Added `scripts/run_m8_pipeline.py` and `scripts/run_m8_release_check.py`.
- Added `scripts/run_m8_bakeoff.py` as the concise M8 comparison entrypoint.
- Added pure dashboard data providers and optional M8 Streamlit pages.
- Added M8 tests and `M8_RESULTS.md`.

Validation so far:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_*.py` | Pass, 19 tests |
| `.venv/bin/python scripts/run_m8_pipeline.py --city burnaby_r1 --config configs/burnaby_r1.json --input-dir outputs/m7_runs/burnaby_r1/google_gemini_3_1_flash_lite --output-dir outputs/m8_runs/burnaby_r1/local_m8 --max-repair-attempts 3 --dry-run` | Pass |
| `.venv/bin/python benchmark/evaluate_m8_chatbot.py --cases benchmark/gold/m8_chatbot_gold_cases.json --output-dir outputs/m8_runs/burnaby_r1/local_m8` | Pass, 3/3 |

M8 measured Burnaby R1 output:

| Metric | Value |
|---|---:|
| structured rules | 144 |
| verified | 85 |
| repaired_successfully | 2 |
| context_required | 9 |
| review_needed | 48 |
| rejected | 0 |
| false_verified | 0 |
| false_approval | 0 |
| repair attempts | 171 |

Interpretation:

- M8 preserved M7 safety and created a more explicit context bucket.
- M8 preserved two verifier-backed guarded bundle promotions as `repaired_successfully`; the new M8 repair loop did not create additional promotions.
- M8 reduced generic `review_needed` from 57 to 48 by separating dependency/context work into `context_required` and preserving repaired-successfully provenance.

Final validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | Pass, 609 tests and 3 subtests |
| `.venv/bin/python scripts/run_m8_release_check.py --city burnaby_r1 --m7-output-dir outputs/m7_runs/burnaby_r1/google_gemini_3_1_flash_lite --m8-output-dir outputs/m8_runs/burnaby_r1/local_m8` | Pass |
| `git diff --check -- . ':(exclude)outputs/m8_runs'` | Pass |

The M8 release check covered compileall, M7 status, M7 Burnaby benchmark, M7 adversarial benchmark, M7 chatbot gold, M8 unit tests, M8 pipeline smoke, M8 chatbot gold, and M8 summary existence.

## M8.5 Checkpoint 1: Planning And Baseline Preservation

Date: 2026-06-29

Goal:

- Start the M8.5 upgrade without changing M7 or M8 verifier behavior.
- Preserve the current M8 safety baseline.
- Create the M8.5 implementation plan and placeholder results record.
- Identify the lowest-risk first implementation checkpoint.

What was inspected:

- `REFACTOR_LOG.md`
- `M8_PLAN.md`
- `M8_RESULTS.md`
- `docs/M8_CANVA_STAKEHOLDER_REPORT.md`
- `README.md`
- `src/burnaby_prototype/verification.py`
- `src/burnaby_prototype/slim_pipeline.py`
- `src/burnaby_prototype/m7_measure.py`
- `src/burnaby_prototype/bylaw_chat.py`
- `src/burnaby_prototype/m8/`
- `dashboard/`
- `scripts/run_m8_pipeline.py`
- `scripts/run_m8_release_check.py`
- `benchmark/`
- `configs/`
- `tests/`

Baseline validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_consolidated_prototype.py status` | Pass, `m7_safety_ready`, false verified total `0` |
| `.venv/bin/python scripts/run_m8_release_check.py` | Pass, M7 safety preserved `true` |
| `.venv/bin/python -m pytest -q` | Pass, `609 passed, 3 subtests passed` |

M8 baseline to preserve:

| Metric | Value |
|---|---:|
| structured rules | 144 |
| verified | 85 |
| repaired_successfully | 2 |
| verified-like total | 87 |
| context_required | 9 |
| review_needed | 48 |
| false_verified | 0 |
| false_approval | 0 |
| repair attempts | 171 |
| M8 new-loop successful repairs | 0 |
| M7 safety preserved | true |

What changed:

- Added `M8_5_PLAN.md`.
- Added `M8_5_RESULTS.md`.
- Added this M8.5 checkpoint section to `REFACTOR_LOG.md`.

What did not change:

- No M7 verifier behavior changed.
- No M8 verifier behavior changed.
- No pipeline behavior changed.
- No dashboard behavior changed.
- No chatbot behavior changed.
- No GIS export behavior changed.

Safest next implementation checkpoint:

- Build M8.5 table-aware parsing and row/column lineage as pure additive data
  contracts under `src/burnaby_prototype/m8_5/tables/`.
- Add tests before integrating with a pipeline.
- Do not verify or promote table-derived rules directly.
- Keep table-derived candidates as verifier inputs only after lineage contracts
  are stable.

Remaining risks:

- The worktree is already dirty from the uncommitted M8 implementation, so M8.5
  changes should stay tightly scoped and clearly named.
- Table parsing can create false confidence if row labels, column labels, or
  merged-cell diagnostics are incomplete.
- Dependency and reviewer workflows must keep the verifier authoritative.
- M8.5 target outcomes must not be described as measured until M8.5 commands
  exist and have run.

## M8.5 Checkpoint 2: Table-Aware Parsing And Row/Column Lineage

Date: 2026-06-29

Goal:

- Add pure table-aware lineage models that preserve row/column/source context.
- Generate table-derived candidate rules without direct verification or
  promotion.
- Keep the verifier authoritative and unchanged.

What changed:

- Added `src/burnaby_prototype/m8_5/__init__.py`.
- Added `src/burnaby_prototype/m8_5/tables/__init__.py`.
- Added `src/burnaby_prototype/m8_5/tables/table_block.py`.
- Added `src/burnaby_prototype/m8_5/tables/table_confidence.py`.
- Added `src/burnaby_prototype/m8_5/tables/table_lineage.py`.
- Added `src/burnaby_prototype/m8_5/tables/table_parser.py`.
- Added `src/burnaby_prototype/m8_5/tables/table_rule_mapper.py`.
- Added `tests/test_m8_5_table_lineage.py`.
- Added `tests/test_m8_5_table_rule_mapper.py`.
- Updated `M8_5_PLAN.md`.
- Updated `M8_5_RESULTS.md`.

Implemented contracts:

| Contract | Purpose |
|---|---|
| `TableBlock` | Table-level source, header, cell, and diagnostic container |
| `TableCell` | Row/column-scoped raw cell with row label and column label |
| `TableCellLineage` | Verifier-facing lineage for one table value |
| `TableDerivedRule` | Candidate-only rule claim derived from one lineage cell |
| `TableParseDiagnostic` | Review diagnostic for ambiguous table extraction |

Safety behavior:

- Table-derived rules use status `candidate_only`.
- `TableDerivedRule.to_verifier_candidate()` emits `verification_decision="review_needed"`.
- Table-derived rules cannot mark themselves verified.
- Value-only cells without row label context are not verifier-ready.
- The M7/M8 verifier code was not changed.
- GIS exports were not changed.

Validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_table_lineage.py tests/test_m8_5_table_rule_mapper.py` | Pass, `9 passed` |
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_consolidated_prototype.py status` | Pass, `m7_safety_ready`, false verified total `0` |
| `.venv/bin/python scripts/run_m8_release_check.py` | Pass |
| `.venv/bin/python -m pytest -q` | Pass, `618 passed, 3 subtests passed` |

Behavior covered by tests:

- row labels are preserved
- column labels are preserved
- wrong columns do not map to unrelated rule types
- merged-like/ragged rows and blank body cells produce review diagnostics
- value without row context cannot be verifier-ready
- table lineage serializes to JSON
- table-derived rules preserve source spans
- generated verifier candidates remain review-needed

Remaining risks:

- The parser currently handles simple extracted table rows, not full PDF layout
  reconstruction.
- Merged-cell diagnostics are conservative and signal review; they do not infer
  missing row/column spans yet.
- Table-derived candidates are not yet produced by an M8.5 pipeline run.
- This checkpoint does not change measured verified/review counts.

Next checkpoint:

- Build the M8.5 legal dependency graph as pure contracts and tests before
  connecting it to pipeline or dashboard code.

## M8.5 Checkpoint 3: Legal Dependency Graph

Date: 2026-06-29

Goal:

- Add pure legal dependency graph contracts and resolver helpers.
- Detect cross-reference, definition, and exception dependencies.
- Recommend `context_required` or `review_needed` for blocked dependencies
  without changing verifier outputs.
- Keep M7/M8 safety behavior unchanged.

What changed:

- Added `src/burnaby_prototype/m8_5/dependencies/__init__.py`.
- Added `src/burnaby_prototype/m8_5/dependencies/dependency_types.py`.
- Added `src/burnaby_prototype/m8_5/dependencies/dependency_graph.py`.
- Added `src/burnaby_prototype/m8_5/dependencies/cross_reference_index.py`.
- Added `src/burnaby_prototype/m8_5/dependencies/definition_linker.py`.
- Added `src/burnaby_prototype/m8_5/dependencies/exception_linker.py`.
- Added `src/burnaby_prototype/m8_5/dependencies/dependency_resolver.py`.
- Added `tests/test_m8_5_dependency_graph.py`.
- Added `tests/test_m8_5_dependency_resolver.py`.
- Updated `M8_5_PLAN.md`.
- Updated `M8_5_RESULTS.md`.

Implemented contracts:

| Contract | Purpose |
|---|---|
| `RuleDependency` | One rule-level legal dependency with status, evidence, reason, confidence, and reviewer note |
| `DependencyGraph` | JSON-exportable dependency collection with rule lookup and metrics |
| `DependencyResolver` | Creates dependency artifacts and advisory recommended status |
| `CrossReferenceIndex` | Extracts and resolves `Section X.Y` references |
| `DefinitionLinker` | Links detected defined terms to definition evidence |
| `ExceptionLinker` | Detects exception/override wording such as `unless` or `except` |

Dependency statuses:

- `resolved`
- `unresolved`
- `conflicting`
- `not_applicable`

Safety behavior:

- Unresolved dependencies recommend `context_required`.
- Conflicting dependencies recommend `review_needed`.
- Resolved dependencies allow the existing verifier status to stand.
- The resolver does not verify, promote, approve, or export rules.
- The M7/M8 verifier code was not changed.
- GIS exports were not changed.

Validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_dependency_graph.py tests/test_m8_5_dependency_resolver.py` | Pass, `8 passed` |
| `.venv/bin/python -m pytest -q tests/test_m8_5_*.py` | Pass, `17 passed` |
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_consolidated_prototype.py status` | Pass, `m7_safety_ready`, false verified total `0` |
| `.venv/bin/python scripts/run_m8_release_check.py` | Pass |
| `.venv/bin/python -m pytest -q` | Pass, `626 passed, 3 subtests passed` |

Behavior covered by tests:

- unresolved cross-reference produces `context_required`
- resolved cross-reference attaches evidence
- resolved definition allows verifier status to continue
- exception dependency blocks verification until resolved
- conflicting dependency prevents verified status
- dependency graph exports JSON and round-trips
- dependency graph supports rule-level lookup
- dependency graph supports dependency-type metrics

Remaining risks:

- The dependency resolver is intentionally simple and deterministic; it does not
  yet parse full legal section hierarchy or city-specific reference formats.
- Exception dependencies currently fail closed as unresolved unless a future
  resolver attaches evidence.
- Dependency artifacts are not yet produced by an M8.5 pipeline run.
- This checkpoint does not change measured verified/review counts.

Next checkpoint:

- Build the M8.5 repair evaluator as pure contracts and tests so patch safety
  can be assessed before verifier reruns.

## M8.5 Checkpoint 4: Repair Evaluator

Date: 2026-06-29

Goal:

- Add a pure repair evaluator that determines whether a patch is safe to submit
  to the deterministic verifier.
- Preserve repair history and explain patch safety findings.
- Keep repair from promoting rules directly.

What changed:

- Added `src/burnaby_prototype/m8_5/repair_evaluation/__init__.py`.
- Added `src/burnaby_prototype/m8_5/repair_evaluation/repair_evaluation.py`.
- Added `src/burnaby_prototype/m8_5/repair_evaluation/patch_safety_checker.py`.
- Added `src/burnaby_prototype/m8_5/repair_evaluation/verifier_ready_gate.py`.
- Added `src/burnaby_prototype/m8_5/repair_evaluation/repair_scorecard.py`.
- Added `tests/test_m8_5_repair_evaluator.py`.
- Updated `M8_5_PLAN.md`.
- Updated `M8_5_RESULTS.md`.

Implemented contracts:

| Contract | Purpose |
|---|---|
| `RepairEvaluation` | Auditable result of comparing original and patched rule |
| `PatchSafetyChecker` | Finds unsupported field changes, contradictions, zone mismatch, and introduced dependencies |
| `VerifierReadyGate` | Converts safety category/findings into verifier-ready boolean |
| `RepairScorecard` | Aggregates repair-evaluation categories and readiness counts |

Safety behavior:

- The evaluator cannot recommend `verified`.
- `ready_for_verifier` means the patch may be submitted to deterministic
  verification; it is not a verifier decision.
- Missing evidence fails closed as `insufficient_evidence`.
- Wrong zone/source context fails closed as `unsupported_patch`.
- Contradictory evidence fails closed as `contradictory_evidence`.
- Introduced exceptions become `context_required`.
- Repair history is preserved.
- The M7/M8 verifier code was not changed.
- GIS exports were not changed.

Validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_repair_evaluator.py` | Pass, `8 passed` |
| `.venv/bin/python -m pytest -q tests/test_m8_5_*.py` | Pass, `25 passed` |
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_consolidated_prototype.py status` | Pass, `m7_safety_ready`, false verified total `0` |
| `.venv/bin/python scripts/run_m8_release_check.py` | Pass |
| `.venv/bin/python -m pytest -q` | Pass, `634 passed, 3 subtests passed` |

Behavior covered by tests:

- patch changing value without evidence is rejected
- patch adding evidence from the wrong zone is not verifier-ready
- patch with exact row/column lineage is verifier-ready
- patch introducing exception becomes `context_required`
- patch with contradiction becomes `review_needed`
- repair history is preserved
- evaluator cannot promote directly
- scorecard aggregates repair-safety categories

Remaining risks:

- The repair evaluator is not yet integrated into an M8.5 pipeline run.
- Evidence support checks are intentionally deterministic and conservative, but
  still simpler than the full verifier.
- `safe_for_verifier` should not be interpreted as approval.
- This checkpoint does not change measured verified/review counts.

Next checkpoint:

- Build the reviewer workbench data model so unresolved legal context can be
  reviewed through auditable actions and verifier rerun requests.

## M8.5 Checkpoint 5: Reviewer Workbench Data Model

Date: 2026-06-29

Goal:

- Add auditable reviewer workflow models.
- Allow reviewer actions to approve evidence/context or request follow-up.
- Require verifier rerun for any action that could affect rule status.
- Keep reviewer actions from directly verifying or promoting rules.

What changed:

- Added `src/burnaby_prototype/m8_5/review/__init__.py`.
- Added `src/burnaby_prototype/m8_5/review/review_packet.py`.
- Added `src/burnaby_prototype/m8_5/review/reviewer_actions.py`.
- Added `src/burnaby_prototype/m8_5/review/review_state.py`.
- Added `src/burnaby_prototype/m8_5/review/verifier_rerun_request.py`.
- Added `tests/test_m8_5_review_packet.py`.
- Added `RepairEvaluation.from_dict(...)` so review packets can round-trip repair-evaluation context.
- Updated `M8_5_PLAN.md`.
- Updated `M8_5_RESULTS.md`.

Implemented contracts:

| Contract | Purpose |
|---|---|
| `ReviewPacket` | Rule-level review context with evidence, lineage, dependencies, repair evaluations, and notes |
| `ReviewerAction` | Auditable reviewer action constrained to allowed non-promoting operations |
| `ReviewState` | Immutable-style action history plus generated verifier rerun requests |
| `VerifierRerunRequest` | Pending deterministic verifier rerun artifact |

Safety behavior:

- Direct verification actions such as `mark_verified` raise `ValueError`.
- Approved evidence creates a verifier rerun request, not a verified rule.
- Resolved dependencies create a verifier rerun request, not a verified rule.
- Rejected evidence keeps the rule in review.
- Reviewer notes are preserved.
- The M7/M8 verifier code was not changed.
- GIS exports were not changed.

Validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_review_packet.py` | Pass, `7 passed` |
| `.venv/bin/python -m pytest -q tests/test_m8_5_*.py` | Pass, `32 passed` |
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_consolidated_prototype.py status` | Pass, `m7_safety_ready`, false verified total `0` |
| `.venv/bin/python scripts/run_m8_release_check.py` | Pass |

Behavior covered by tests:

- reviewer cannot directly verify
- approved evidence triggers verifier rerun request
- rejected evidence keeps rule `review_needed`
- resolved dependency can be passed to verifier
- reviewer note is preserved
- review packet serializes to JSON
- review packet contains dashboard display context

Remaining risks:

- Reviewer packets are not yet produced by an M8.5 pipeline run.
- Dashboard pages do not yet load or render these packets.
- Verifier rerun requests are artifacts only until the pipeline consumes them.
- This checkpoint does not change measured verified/review counts.

Next checkpoint:

- Build `scripts/run_m8_5_pipeline.py` so table lineage, dependency graph,
  repair evaluations, and review packets are emitted as run artifacts.

## M8.5 Checkpoint 6: Pipeline Script

Date: 2026-06-30

Goal:

- Connect the Checkpoint 2-5 M8.5 contracts into a runnable artifact pipeline.
- Read existing M8 artifacts without replacing M8.
- Emit table lineage, dependency, repair-evaluation, review-packet, summary,
  comparison, and chatbot-context artifacts.
- Preserve the verifier authority boundary and verified-only GIS boundary.

What changed:

- Added `scripts/run_m8_5_pipeline.py`.
- Generated Burnaby output under `outputs/m8_5_runs/burnaby_r1/local_m8_5/`.
- Updated `M8_5_PLAN.md`.
- Updated `M8_5_RESULTS.md`.

Pipeline command:

```bash
.venv/bin/python scripts/run_m8_5_pipeline.py --city burnaby_r1 --config configs/burnaby_r1.json --m8-input-dir outputs/m8_runs/burnaby_r1/local_m8 --output-dir outputs/m8_5_runs/burnaby_r1/local_m8_5 --max-repair-attempts 3 --enable-table-parsing --enable-dependency-graph --enable-review-packets --dry-run
```

Generated artifacts:

| Artifact | Purpose |
|---|---|
| `table_blocks.json` | Parsed table-block artifacts from M8 source spans |
| `table_cell_lineage.json` | Row/column/cell source lineage |
| `table_derived_rules.json` | Candidate-only table-derived rule claims |
| `dependency_graph.json` | Legal dependency graph export |
| `dependency_resolutions.json` | Per-rule dependency resolver output |
| `repair_evaluations.json` | Patch safety and verifier-readiness evaluations |
| `review_packets.json` | Reviewer workbench packets |
| `verifier_rerun_requests.json` | Verifier rerun request artifact placeholder |
| `m8_5_structured_rules.json` | M8 rules plus table-derived candidates |
| `m8_5_verification_decisions.json` | Preserved M8 decision set with M8.5 metadata |
| `m8_m8_5_comparison.json` | M8-vs-M8.5 measured comparison |
| `m8_5_summary.json` | Run-level M8.5 summary |
| `m8_5_chatbot_context.json` | Consolidated artifact context for future chatbot work |
| `m8_5_summary.md` | Reader-facing summary |

Measured output:

| Metric | Value |
|---|---:|
| Table-derived rules | `137` |
| Dependencies | `4` |
| Repair evaluations | `171` |
| Verifier-ready patches | `78` |
| Review packets | `57` |
| False verified | `0` |
| False approvals | `0` |
| M7/M8 safety preserved | `true` |

Validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_*.py` | Pass, `34 passed` |
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_consolidated_prototype.py status` | Pass, `m7_safety_ready`, false verified total `0` |
| `.venv/bin/python scripts/run_m8_release_check.py` | Pass |
| `.venv/bin/python scripts/run_m8_5_pipeline.py --city burnaby_r1 --config configs/burnaby_r1.json --m8-input-dir outputs/m8_runs/burnaby_r1/local_m8 --output-dir outputs/m8_5_runs/burnaby_r1/local_m8_5 --max-repair-attempts 3 --enable-table-parsing --enable-dependency-graph --enable-review-packets --dry-run` | Pass |
| `.venv/bin/python -m pytest -q` | Pass, `643 passed, 3 subtests passed` |

Safety behavior:

- Table-derived rules are emitted as candidate-only records.
- Repair evaluations can mark patches as `ready_for_verifier`, but cannot
  promote to `verified`.
- Reviewer packets cannot directly verify rules.
- `verifier_rerun_requests.json` is an artifact surface; no dashboard or
  reviewer action bypasses deterministic verification.
- GIS exports were not changed.
- M7/M8 verifier behavior was not weakened.

Remaining risks:

- At the end of Checkpoint 6, the dedicated M8.5 analytics package, dashboard
  pages, chatbot gold cases, multi-city stress, and release check still
  remained as future checkpoints. They are now implemented in Checkpoints 7-11.

Next checkpoint:

- Build the M8.5 analytics package with reusable metric modules and tests,
  then use it from the pipeline comparison/summary path.

## M8.5 Checkpoint 7: Analytics Layer

Date: 2026-06-30

Goal:

- Move M8.5 comparison logic out of the pipeline script and into reusable
  analytics modules.
- Count table, dependency, repair, reviewer, status, source-type, and
  measured-vs-not-run metrics consistently.
- Keep analytics read-only: count and explain artifacts, do not change
  verifier outcomes.

What changed:

- Added `src/burnaby_prototype/m8_5/analytics/__init__.py`.
- Added `src/burnaby_prototype/m8_5/analytics/m8_5_summary.py`.
- Added `src/burnaby_prototype/m8_5/analytics/table_metrics.py`.
- Added `src/burnaby_prototype/m8_5/analytics/dependency_metrics.py`.
- Added `src/burnaby_prototype/m8_5/analytics/repair_quality_metrics.py`.
- Added `src/burnaby_prototype/m8_5/analytics/m8_to_m8_5_compare.py`.
- Added `tests/test_m8_5_analytics.py`.
- Updated `scripts/run_m8_5_pipeline.py` to use
  `compare_m8_to_m8_5(...)`.
- Updated `M8_5_PLAN.md`.
- Updated `M8_5_RESULTS.md`.

Measured analytics now include:

| Metric | Value |
|---|---:|
| M8 verified-like count | `87` |
| M8.5 verified-like count | `87` |
| M8.5 review needed | `48` |
| M8.5 context required | `9` |
| Table-derived rules | `137` |
| Table-derived verified | `0` |
| Table-derived review/candidate count | `137` |
| Dependency total | `4` |
| Dependency unresolved | `4` |
| Repair evaluations | `171` |
| Verifier-ready patches | `78` |
| Reviewer packets | `57` |
| False verified | `0` |
| False approvals | `0` |

Comparison artifact improvements:

- `m8_m8_5_comparison.json` now includes reusable metric states.
- At Checkpoint 7, M8.5 chatbot gold and M8.5 multi-city stress were
  explicitly labeled as not run. They are now measured in Checkpoints 9 and 10.
- Coverage by rule type, city, dependency type, and table-vs-prose source is
  included.

Validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_analytics.py tests/test_m8_5_pipeline.py` | Pass, `8 passed` |
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_m8_5_pipeline.py --city burnaby_r1 --config configs/burnaby_r1.json --m8-input-dir outputs/m8_runs/burnaby_r1/local_m8 --output-dir outputs/m8_5_runs/burnaby_r1/local_m8_5 --max-repair-attempts 3 --enable-table-parsing --enable-dependency-graph --enable-review-packets --dry-run` | Pass |

Safety behavior:

- Analytics modules do not mutate rules or decisions.
- Verified-like is counted only as `verified + repaired_successfully`.
- `context_required` stays separate from `review_needed`.
- Table-derived candidates are counted as candidates/review, not verified.
- Repair `ready_for_verifier` is not counted as verified.

Remaining risks:

- Dashboard pages do not yet load these M8.5 analytics artifacts.
- M8.5 chatbot gold cases are still not implemented.
- Multi-city stress and release check scripts are still not implemented.

Next checkpoint:

- Add M8.5 dashboard data providers/pages for table lineage, dependency graph,
  repair workbench, reviewer queue, and M8-vs-M8.5 comparison.

## M8.5 Checkpoint 8: Dashboard Data Providers And Pages

Date: 2026-06-30

Goal:

- Add M8.5 dashboard inspection surfaces without adding business logic to
  `dashboard/streamlit_app.py`.
- Let reviewers inspect table lineage, dependencies, repair evaluations,
  review packets, and comparison metrics from generated artifacts.
- Keep dashboard behavior read-only and non-promoting.

What changed:

- Added `dashboard/m8_5_data.py`.
- Added `dashboard/pages/m8_5_table_explorer.py`.
- Added `dashboard/pages/m8_5_dependency_graph.py`.
- Added `dashboard/pages/m8_5_repair_workbench.py`.
- Added `dashboard/pages/m8_5_reviewer_queue.py`.
- Added `dashboard/pages/m8_5_multi_city_compare.py`.
- Added `tests/test_m8_5_dashboard_data.py`.
- Updated `M8_5_PLAN.md`.
- Updated `M8_5_RESULTS.md`.

Dashboard view models:

| View model | Purpose |
|---|---|
| `m8_5_metric_cards` | Summary metrics for reader scan |
| `status_count_rows` | M8.5 status counts |
| `table_lineage_rows` | Row/column/cell lineage display |
| `table_derived_rule_rows` | Candidate-only table-derived rule display |
| `dependency_graph_rows` | Rule dependency graph display |
| `repair_evaluation_rows` | Repair safety and verifier-readiness display |
| `review_queue_rows` | Reviewer queue with priority sorting |
| `comparison_metric_rows` | Measured/target/not-run metric states |
| `coverage_rows` | Rule/source/city/dependency coverage displays |

Validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_dashboard_data.py tests/test_m8_5_analytics.py` | Pass, `10 passed` |
| `.venv/bin/python -m pytest -q tests/test_m8_5_*.py` | Pass, `44 passed` |
| `.venv/bin/python -m compileall -q src scripts dashboard benchmark tests` | Pass |
| `.venv/bin/python scripts/run_m8_5_pipeline.py --city burnaby_r1 --config configs/burnaby_r1.json --m8-input-dir outputs/m8_runs/burnaby_r1/local_m8 --output-dir outputs/m8_5_runs/burnaby_r1/local_m8_5 --max-repair-attempts 3 --enable-table-parsing --enable-dependency-graph --enable-review-packets --dry-run` | Pass |

Safety behavior:

- Dashboard pages are artifact readers.
- No dashboard action can verify or promote a rule.
- Review priority sorting does not change status.
- No GIS exports were changed.
- No code was added to `dashboard/streamlit_app.py`.

Remaining risks:

- Browser-level Streamlit smoke has not yet been rerun for M8.5 pages.
- M8.5 chatbot still needs artifact-grounded answer policy and gold cases.
- Multi-city stress and release check scripts remain unimplemented.

Next checkpoint:

- Build the M8.5 artifact-grounded chatbot with at least 25 gold cases and
  tests for safety, table lineage, dependencies, repair evaluation, and
  reviewer workflow answers.

## M8.5 Checkpoint 9: Artifact-Grounded Chatbot

Date: 2026-06-30

Goal:

- Add an M8.5 analyst chatbot that answers only from generated M8.5 artifacts.
- Cover safety, table lineage, dependency graph, repair evaluation, and
  reviewer workflow questions.
- Refuse direct legal overrides, direct verification, promotion, and GIS export
  requests.
- Return `not available` when required artifacts are missing.

What changed:

- Added `src/burnaby_prototype/m8_5/chatbot/__init__.py`.
- Added `src/burnaby_prototype/m8_5/chatbot/grounded_answer_policy.py`.
- Added `src/burnaby_prototype/m8_5/chatbot/m8_5_analyst.py`.
- Added `src/burnaby_prototype/m8_5/chatbot/review_workflow_answers.py`.
- Added `benchmark/gold/m8_5_chatbot_gold_cases.json`.
- Added `benchmark/evaluate_m8_5_chatbot.py`.
- Added `tests/test_m8_5_chatbot_grounding.py`.
- Updated `scripts/run_m8_5_pipeline.py` so `m8_5_chatbot_context.json`
  contains table lineage, table-derived rules, dependency graph, repair
  evaluations, and review packets.
- Updated `M8_5_PLAN.md`.
- Updated `M8_5_RESULTS.md`.

Gold cases:

| Category | Cases |
|---|---:|
| Safety | `5` |
| Table lineage | `5` |
| Dependency graph | `5` |
| Repair evaluation | `5` |
| Reviewer workflow | `5` |

Validation:

| Command | Result |
|---|---|
| `.venv/bin/python scripts/run_m8_5_pipeline.py --city burnaby_r1 --config configs/burnaby_r1.json --m8-input-dir outputs/m8_runs/burnaby_r1/local_m8 --output-dir outputs/m8_5_runs/burnaby_r1/local_m8_5 --max-repair-attempts 3 --enable-table-parsing --enable-dependency-graph --enable-review-packets --dry-run` | Pass |
| `.venv/bin/python -m pytest -q tests/test_m8_5_chatbot_grounding.py tests/test_m8_5_pipeline.py` | Pass, `8 passed` |
| `.venv/bin/python benchmark/evaluate_m8_5_chatbot.py --output-dir outputs/m8_5_runs/burnaby_r1/local_m8_5` | Pass, `25/25`, hard failures `0` |

Safety behavior:

- The chatbot cannot mark a rule verified.
- The chatbot refuses direct legal override requests.
- The chatbot distinguishes `ready_for_verifier` from `verified`.
- The chatbot distinguishes M8 measured results from M8.5 measured results.
- The chatbot cites artifact concepts such as rule IDs, dependency IDs, table
  lineage IDs, and review packets.
- Missing artifacts return `not available`.

Remaining risks:

- The current chatbot is deterministic and coverage-oriented; LLM wording can
  be layered later only if bounded by the same artifact policy.
- Multi-city stress and release check scripts remain unimplemented.

Next checkpoint:

- Build the M8.5 multi-city stress script for available cities only:
  `burnaby_r1`, `vancouver_rs`, and `calgary_rcg`.

## M8.5 Checkpoint 10: Multi-City Stress

Date: 2026-06-30

Goal:

- Run M8.5 across the available configured cities only.
- Generate per-city summaries and cross-city comparison artifacts.
- Produce clear skip reasons when data is missing.
- Preserve false verified and false approval safety across the aggregate.

What changed:

- Added `src/burnaby_prototype/m8_5/multi_city/__init__.py`.
- Added `src/burnaby_prototype/m8_5/multi_city/city_run_matrix.py`.
- Added `src/burnaby_prototype/m8_5/multi_city/city_format_profile.py`.
- Added `src/burnaby_prototype/m8_5/multi_city/generalization_report.py`.
- Added `src/burnaby_prototype/m8_5/multi_city/stress_test_runner.py`.
- Added `scripts/run_m8_5_multi_city_stress.py`.
- Added `tests/test_m8_5_multi_city_metrics.py`.
- Updated `benchmark/evaluate_m8_5_chatbot.py` to write measured chatbot
  metric state back into `m8_m8_5_comparison.json`.
- Updated `scripts/run_m8_5_multi_city_stress.py` to mark multi-city stress as
  measured in each measured city comparison artifact.
- Updated `M8_5_PLAN.md`.
- Updated `M8_5_RESULTS.md`.

Generated artifacts:

| Artifact | Purpose |
|---|---|
| `outputs/m8_5_runs/multi_city/city_run_matrix.json` | Per-city measured/skipped/failed matrix |
| `outputs/m8_5_runs/multi_city/cross_city_summary.json` | Cross-city safety and coverage summary |
| `outputs/m8_5_runs/multi_city/city_format_profiles.json` | Format profile by city |
| `outputs/m8_5_runs/multi_city/generalization_report.json` | JSON wrapper for report text |
| `outputs/m8_5_runs/multi_city/generalization_report.md` | Reader-facing generalization report |

Measured output:

| City | Status | Table-derived rules | Dependencies | Review packets | False verified |
|---|---|---:|---:|---:|---:|
| `burnaby_r1` | measured | `137` | `4` | `57` | `0` |
| `vancouver_rs` | measured | `0` | `3` | `32` | `0` |
| `calgary_rcg` | measured | `0` | `1` | `46` | `0` |

Cross-city safety:

| Metric | Value |
|---|---:|
| Measured cities | `3` |
| Skipped cities | `0` |
| Failed cities | `0` |
| False verified total | `0` |
| False approval total | `0` |
| Safety preserved | `true` |

Validation:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_m8_5_multi_city_metrics.py tests/test_m8_5_chatbot_grounding.py` | Pass, `10 passed` |
| `.venv/bin/python scripts/run_m8_5_multi_city_stress.py --dry-run` | Pass, measured `3`, skipped `0`, failed `0`, false verified total `0` |
| `.venv/bin/python benchmark/evaluate_m8_5_chatbot.py --output-dir outputs/m8_5_runs/burnaby_r1/local_m8_5` | Pass, `25/25`, hard failures `0` |

Safety behavior:

- Only available configured cities are run.
- Missing artifacts produce skipped rows with reasons.
- No Surrey or unknown city data is invented.
- M8.5 stress aggregates false verified and false approval counts.
- Multi-city stress does not change verifier logic or promote rules.

Remaining risks:

- Vancouver and Calgary M8 artifacts were bootstrapped through the deterministic
  M8 dry-run path because only Burnaby had M8 artifacts at the start of this
  checkpoint.
- Vancouver and Calgary generated no table-derived candidates under the current
  simple table parser, which is a useful generalization signal but not a final
  limitation claim.
- Release check and documentation/stakeholder explanation remain incomplete.

Next checkpoint:

- Build `scripts/run_m8_5_release_check.py` to run the full M8.5 acceptance
  gate in one command.

## M8.5 Checkpoint 11: Release Check

Date: 2026-06-30

Goal:

- Provide a single M8.5 release gate command.
- Run compile, M7 status, M8 release, M8.5 unit tests, M8.5 pipeline smoke,
  M8.5 multi-city dry run, M8.5 chatbot gold, and artifact checks.
- Report command status, output tails, measured metrics, safety state, and
  remaining risks.

What changed:

- Added `scripts/run_m8_5_release_check.py`.
- Generated `outputs/m8_5_runs/release_check/m8_5_release_check.json`.
- Generated `outputs/m8_5_runs/release_check/m8_5_release_check.md`.
- Updated `M8_5_PLAN.md`.
- Updated `M8_5_RESULTS.md`.

Validation:

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

Release metrics:

| Metric | Value |
|---|---:|
| Burnaby verified-like count | `87` |
| Burnaby review needed | `48` |
| Burnaby context required | `9` |
| Burnaby table-derived rules | `137` |
| Burnaby dependencies | `4` |
| Burnaby repair evaluations | `171` |
| Burnaby review packets | `57` |
| Chatbot gold | `25/25` |
| Multi-city measured cities | `3` |
| False verified count | `0` |
| False approval count | `0` |
| Cross-city false verified total | `0` |
| Cross-city false approval total | `0` |

Safety behavior:

- Release check fails if any command fails.
- Release check fails if false verified or false approval totals are nonzero.
- Release check confirms repair and reviewer paths still cannot promote
  directly.
- Release check confirms GIS verified-only boundary remains preserved.

Remaining risks:

- M8.5 resolves workbench visibility and review readiness, but does not
  automatically promote blocked legal rules.
- Browser-level Streamlit smoke for each optional M8.5 page is still useful.
- Vancouver and Calgary table-derived counts are zero under the current simple
  table parser.

Next checkpoint:

- Finish M8.5 documentation and stakeholder explanation, including
  `docs/m8_5_upgrade_explanation.html`.

## M8.5 Checkpoint 12: Documentation And Stakeholder Explanation

Date: 2026-06-30

Goal:

- Finish the M8.5 documentation layer.
- Explain the upgrade for stakeholders, future workers, and future LLM agents.
- Clearly separate measured results from future targets.
- Include limitations and M9 direction.

What changed:

- Added `docs/m8_5_upgrade_explanation.html`.
- Updated `M8_5_PLAN.md`.
- Updated `M8_5_RESULTS.md`.
- Updated `REFACTOR_LOG.md`.

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
- recommended M9 direction

HTML report contents:

- architecture SVG
- measured metric cards
- M8-vs-M8.5 table
- table/dependency/repair/reviewer explanation
- multi-city stress table
- validation commands
- release-check table
- limitations and M9 roadmap

Safety behavior:

- Documentation states that M8.5 is a verification workbench, not an automatic
  legal approval engine.
- Documentation preserves the trust boundary: extraction proposes, verifier
  decides, GIS consumes verified-only.

## M8.5 Checkpoint 13: Guarded Repair Rerun

Date: 2026-06-30

Goal:

- Convert verifier-ready repair evaluations into deterministic verifier reruns.
- Apply guarded promotions only when the verifier proves a repaired candidate.
- Preserve the M7/M8 safety boundary and keep false verified/approval counts at
  zero.

What changed:

- Added the M8.5 `repair_rerun` module.
- Added `--enable-repair-rerun` and `--apply-guarded-repair-promotions` to the
  M8.5 pipeline.
- Added `repair_rerun_report.json`, `repair_rerun_report.md`,
  `guarded_repair_promotions.json`, and populated verifier rerun requests.
- Added repair-rerun metrics to M8.5 summary, comparison, chatbot context, and
  release-check outputs.
- Added unit and pipeline tests for repair selection, verifier rerun, guarded
  promotion, and missing M7 evidence failure.

Measured Burnaby R1 result:

| Metric | Measured |
|---|---:|
| Eligible repair-ready rules | `26` |
| Repair-rerun attempts | `26` |
| Promotion-ready repairs | `0` |
| Guarded repair promotions | `0` |
| Reruns still review-needed | `13` |
| Reruns rejected | `13` |
| False verified count | `0` |
| False approval count | `0` |

Validation:

- `.venv/bin/python -m pytest -q tests/test_m8_5_repair_rerun.py tests/test_m8_5_pipeline.py`
  passed with `8 passed`.
- `.venv/bin/python -m pytest -q tests/test_m8_5_*.py` passed with `60 passed`.
- `.venv/bin/python -m pytest -q` passed with `669 passed, 3 subtests passed`.
- `.venv/bin/python scripts/run_consolidated_prototype.py status` reported
  `m7_safety_ready` and false verified total `0`.
- `.venv/bin/python scripts/run_m8_5_release_check.py` passed.

Safety behavior:

- Repair evaluation still cannot promote directly.
- Guarded promotion requires deterministic verifier proof.
- All 26 current repair reruns failed verifier promotion, so visible
  verified-like count stayed `87`.
- The significant remaining gap is repair quality, not rerun orchestration.
