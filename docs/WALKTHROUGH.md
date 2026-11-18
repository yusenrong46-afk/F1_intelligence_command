# Code walkthrough: ten questions about verification

Each answer is under 120 words and points to the code that does it, written as
`file::symbol`. `make walkthrough-check` (`scripts/check_walkthrough.py`) fails if
a pointed-to file or symbol no longer exists or an answer grows past 120 words.

## 1. How does a proposed rule become verified?

An extractor (an LLM or a deterministic table reader) only proposes a candidate:
a value, unit, operator, rule family, scope and the evidence id it cites. The
verifier re-checks each field against the cited evidence text and records every
failure as a named support gap. The bucket is then a pure function of those gaps:
no blocking gap means verified; a critical gap (value absent, unit incompatible,
operator refuted) means rejected; a gap outside the rule contract means not used;
anything else means review needed. No model output can change the bucket.

Code: `src/burnaby_prototype/verification.py::verify_candidates`,
`src/burnaby_prototype/decision_policy.py::verification_decision_from_gaps`

## 2. Why is a table cell with the right number not automatically verified?

Zoning tables are matrices: the same row holds different values per column, and
some columns only apply under a condition. A number that appears on the page can
still belong to the wrong column, or be one branch of a conditional cell ("Lots
≤ 567 m²: 40% / Lots > 567 m²: 30%"). The matrix binding ties the claimed column
to the cell. Wrong column is rejected (`column_value_mismatch`); a dropped
condition or qualifier is held for review (`conditional_cell_condition_missing`,
`column_qualifier_not_claimed`).

Code: `src/burnaby_prototype/verification.py::_matrix_column_binding`,
`src/burnaby_prototype/decision_policy.py::CRITICAL_REJECTION_GAPS`

## 3. What was the "1 to 3 units" bug, and what guards it?

When a table is flattened into text ("1 to 3 Units; 4 to 6 Units"), an extractor
can read the lower range bound as the lot maximum (`dwelling_units <= 3` when the
maximum is 6). The guard adds `range_bound_not_maximum` when a larger count or
range appears nearby and the scope has no disambiguator such as front or rear.
The original pattern needed the unit noun right after the number, so "1 to 3
small-scale multi-unit dwelling units" escaped. The fixed pattern looks ahead up
to 40 characters, stopping at a clause break.

Code: `src/burnaby_prototype/decision_policy.py::_UNIT_RANGE_IN_TEXT_RE`,
`src/burnaby_prototype/decision_policy.py::evidence_shape_gaps`,
`tests/test_adversarial_hardening.py::test_range_bound_not_verified_as_lot_maximum`

## 4. What do the 34 poisoned cases contain?

Hand-written candidates that look plausible but must never verify: 24 for
Burnaby, 6 for Calgary and 4 for Vancouver. They include a height in percent, a
value absent from its evidence, a flipped operator, a missing evidence id, a
definition posing as a rule, a value taken from the wrong table column, a
conditional cell with its condition dropped, and a minimum clause turned into a
maximum by a blank operator. Each case states the expected decision (review or
rejected). Three more poisoned evidence bundles test cross-table stitching.

Code: `benchmark/evaluate_adversarial.py::run`,
`benchmark/evaluate_adversarial.py::run_bundle_cases`,
`tests/test_adversarial_hardening.py::test_all_city_adversarial_cases_blocked`

## 5. What does "review needed" mean for the client?

It means the rule is probably real but not proven: the evidence is ambiguous, a
condition or column is missing, or a range bound might not be the maximum. The
rule never reaches the GIS contract or proposal checks. A planner opens it in the
Review Workbench, which shows the support gaps, the cited evidence and the
closest related rule, and decides what to inspect next. Review is the safe
outcome, not an error: the system holds rather than guesses.

Code: `dashboard/f1_command_center.py::_review_detail`,
`src/burnaby_prototype/decision_policy.py::verification_decision_from_gaps`

## 6. What exactly does GIS receive?

Only verified rules, projected to a slim contract (rule family, value, unit,
operator, scope, condition, and a citation with page, evidence id and quote),
with exact duplicates collapsed.
The full audit trail stays in `verified_rules.json`. A CI test regenerates the
GIS contract and Felt export from the committed verified rules and requires an
exact match, so a hand edit or stale file fails the build.

Code: `src/burnaby_prototype/slim_pipeline.py::project_gis_contract_rule`,
`src/burnaby_prototype/slim_pipeline.py::deduplicate_verified_rules_for_export`,
`tests/test_m7_safety_gates.py::test_gis_contract_and_felt_export_match_fresh_regen`

## 7. How is a new city onboarded?

`make onboard CITY=<id> URL=<pdf> PAGES=<a-b>` creates a config from a generic
template, downloads the whole official PDF and records its SHA-256 and page scope,
validates the config, extracts the scoped page text, runs a no-key extraction dry
run, and creates an empty gold draft labelled `agent_draft_unreviewed`. Each step
is timed and written to an onboarding report. An existing city must match its
recorded hash; a mismatch fails and provenance is never rewritten. No source code
changes.

Code: `scripts/onboard_city.py::main`, `scripts/onboard_city.py::get_source`,
`scripts/fetch_bylaw.py::fetch_verified_source`

## 8. Why does the page scope matter?

Calgary's bylaw is 1,053 pages and covers many districts. Without a page scope,
retrieval pulled numbers from other districts into the evidence. The page range
in `provenance.json` restricts extraction to the target district while keeping
the official page numbers, so every citation stays checkable. A test fails if any
gold rule falls outside its city's scoped pages, because recall could otherwise
drop silently.

Code: `src/burnaby_prototype/extraction/pdf_ingest.py::page_ranges_from_provenance`,
`src/burnaby_prototype/extraction/pdf_ingest.py::restrict_intermediate_to_pages`,
`tests/test_page_scope_coverage.py::PageScopeCoverageTests`

## 9. Where could a false verification still come from?

From the inputs the verifier trusts. Evidence text that is not really on the
source page (source repair re-anchors it only when the cached PDF is present). A
wrong `rule_family_direction` in a city config, which decides whether a family is
a minimum or maximum. A published PDF that changed after provenance was recorded.
A gold benchmark mistake that hides an error. And any future gap added to the
advisory set, which never blocks.

Code: `src/burnaby_prototype/source_repair.py::source_pdf_for_config`,
`src/burnaby_prototype/verification.py::_family_direction_mismatch`,
`src/burnaby_prototype/decision_policy.py::ADVISORY_GAPS`,
`configs/_template.json::rule_family_direction`

## 10. How do you know a change did not weaken safety?

`make eval` re-scores the committed runs offline and writes a byte-stable
summary. `make gate-l3` then fails if any city has a false verified rule,
precision below 1.0, a poisoned case leaking, coverage below its baseline, or a
verified or review count that moved. The README results are generated from the
same summary, and `make check-docs` fails on a hand edit.

Code: `scripts/run_eval.py::build_summary`, `scripts/check_eval_baseline.py::check`,
`scripts/render_results.py::render`
