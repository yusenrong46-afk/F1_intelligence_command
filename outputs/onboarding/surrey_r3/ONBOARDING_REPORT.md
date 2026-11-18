# Onboarding report: surrey_r3

Status: **exploratory**. This city has no reviewed gold benchmark, so no
number from it may be reported as accuracy.

Command: `make onboard CITY=surrey_r3`
Run on: 2026-11-18 (timings below are wall-clock seconds)

## Source

- URL: https://www.surrey.ca/sites/default/files/bylaws/BYL_Zoning_12000.pdf
- SHA-256 (committed provenance): `b18d03c1b07b8e39fd582fb07e8811b50fc02d733aab43f18b8f5ad1a659a3cd`
- Pages in PDF: 369; scoped pages: [143, 154]
- Fetched at (provenance): 2026-07-05T19:44:00Z

## Steps

| Step | Status | Seconds | Detail |
|---|---|---:|---|
| config | PASS | 0.0 | kept existing reviewed config configs/surrey_r3.json unchanged |
| source | FAIL | 0.17 | source hash no longer matches committed provenance (not rewritten): surrey_r3: downloaded 3299125 bytes from https://www.surrey.ca/sites/default/files/bylaws/BYL_Zoning_12000.pdf with sha256 9b696693d30864cf27e8f9ca458b5be66fe15f98c9f300bb71011217cb14ea6c, but provenance.json records b18d03c1b07b8e39fd582fb07e8811b50fc02d733aab43f18b8f5ad1a659a3cd. Nothing was written. |
| validate_config | PASS | 0.03 | exit 0: all configs structurally valid (trust model: configs are reviewed artifacts) |
| locate | NOT RUN |  | no LOCATE given |
| page_text | NOT RUN |  | needs a source PDF that matches provenance |
| dry_run | NOT RUN |  | needs a source PDF that matches provenance and a valid config |
| gold_draft | PASS | 0.0 | created an empty draft for review |

## NOT RUN

- Real-model extraction (`make extract CITY=surrey_r3 CONFIRM_PAID=yes`): paid, not authorized here.
- Verification of model-extracted candidates and any benchmark score: needs the extraction above and a reviewed gold set.
- Human review of `benchmark/gold/surrey_r3_gold_rules.DRAFT.json`.

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

Delete `configs/surrey_r3.json`, `data/bylaws/surrey_r3/`, `outputs/onboarding/surrey_r3/` and
`benchmark/gold/surrey_r3_gold_rules.DRAFT.json` (only those this run created).
