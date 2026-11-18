# Onboarding report: toronto_rd

Status: **exploratory**. This city has no reviewed gold benchmark, so no
number from it may be reported as accuracy.

Command: `make onboard CITY=toronto_rd URL=https://www.toronto.ca/legdocs/bylaws/2013/law0569-schedule-a-vol1-ch1-800.pdf PAGES=61-66`
Run on: 2026-11-18 (timings below are wall-clock seconds)

## Source

- URL: https://www.toronto.ca/legdocs/bylaws/2013/law0569-schedule-a-vol1-ch1-800.pdf
- SHA-256 (committed provenance): `f19ca4cedf780abe91d192f90f934af5cc4c7e3851e2c954fdcf1651b99b11c7`
- Pages in PDF: 328; scoped pages: [61, 66]
- Fetched at (provenance): 2026-11-18T20:19:00+00:00

## Steps

| Step | Status | Seconds | Detail |
|---|---|---:|---|
| config | PASS | 0.0 | created configs/toronto_rd.json from the template |
| source | PASS | 0.27 | fetched 1218396 bytes, sha256 f19ca4cedf780abe91d192f90f934af5cc4c7e3851e2c954fdcf1651b99b11c7, 328 pages; recorded new provenance |
| validate_config | PASS | 0.03 | exit 0: all configs structurally valid (trust model: configs are reviewed artifacts) |
| locate | NOT RUN |  | no LOCATE given |
| page_text | PASS | 2.95 | pages 61-66 written to source_pages.txt (gitignored) |
| dry_run | PASS | 41.42 | exit 0; no API key in env; log dry_run.log; [m7] built 70 evidence packs / [m7] model=dry_run output=outputs/onboarding/toronto_rd/bakeoff_dry_run/toronto_rd/dry_run / [m7] wrote outputs/onboarding/toronto_rd/bakeoff_dry_run/toronto_rd/bakeoff_summary.json |
| gold_draft | PASS | 0.0 | created an empty draft for review |

## Dry run summary (no model call)

- cache_hit_count: 0
- candidate_rule_count: 0
- city: toronto_rd
- discovery_mode: exhaustive
- dry_run: True
- evidence_unit_count: 0
- extraction_error_count: 0
- matrix_candidate_count: 0
- model: None
- pass1_candidate_rule_count: 0
- pipeline: native_rag_llm_extraction_m7
- repair_candidate_rule_count: 0
- repair_pack_count: 0
- retrieval_pack_count: 70
- safety_contract: EXHAUSTIVE extraction proposes candidates only. Deterministic verification decides.
- seed_pack_count: 70
- estimated_cost_usd reported by the dry run: 0.0

## NOT RUN

- Real-model extraction (`make extract CITY=toronto_rd CONFIRM_PAID=yes`): paid, not authorized here.
- Verification of model-extracted candidates and any benchmark score: needs the extraction above and a reviewed gold set.
- Human review of `benchmark/gold/toronto_rd_gold_rules.DRAFT.json`.

## Config knobs

Every knob is a reviewed trust decision (see `scripts/validate_config.py`).

- structured_table_verification = true
- table_scope_pattern_mode = "deny_ambiguous"
- structured_table_scope_patterns = []
- auto_verify_table_fallback_candidates = false
- auto_verify_table_cell_candidates = false
- auto_verify_table_evidence_candidates = false
- verify_text_candidates = true
- require_text_consensus = false
- cross_family_sibling_groups = [["lot_coverage", "impervious_surface"]]
- gis_text_rule_contract = ["setback", "building_separation", "lot_area", "height", "storeys", "lot_coverage", "floor_area", "dwelling_units"]
- single_source_text_rule_contract = ["height", "setback", "building_separation", "floor_area"]
- direction building_separation = min
- direction dwelling_units = max
- direction floor_area = max
- direction height = max
- direction impervious_surface = max
- direction lot_area = min
- direction lot_coverage = max
- direction setback = min
- direction storeys = max
- normalization knobs set: none (all empty)

## Roll back

Delete `configs/toronto_rd.json`, `data/bylaws/toronto_rd/`, `outputs/onboarding/toronto_rd/` and
`benchmark/gold/toronto_rd_gold_rules.DRAFT.json` (only those this run created).
