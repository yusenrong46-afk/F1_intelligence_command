# Onboarding a new city, and the `bylaw-verify` interface

Two ways to connect this project to other work:

1. **`bylaw-verify`**, a versioned command-line contract over the verifier, for
   any extractor that produces rule candidates and evidence.
2. **`make onboard`**, which sets up a new city from config alone (no source
   edits) and reports what it did.

A city without a reviewed gold benchmark is **exploratory**. Its outputs are
not accuracy numbers.

## 1. `bylaw-verify` (contract 1.0)

```bash
bylaw-verify --candidates rule_candidates.json --evidence evidence_units.json \
  --config configs/<city>.json --out-dir outputs/cli/<city>
```

| Item | Where |
|---|---|
| Input schemas | `schemas/bylaw_verify_candidates.schema.json`, `schemas/bylaw_verify_evidence.schema.json` |
| Output schema | `schemas/bylaw_verify_result.schema.json` (`<out-dir>/bylaw_verify_result.json`, also printed on stdout) |
| Implementation | `src/burnaby_prototype/cli_verify.py`, a thin adapter over `run_slim_verification` (the same path as `scripts/run_slim_verifier.py --native-extraction`) |
| Contract tests | `tests/test_cli_contract.py`, one golden example per bucket in `tests/fixtures/cli_contract/` taken from the committed Calgary M7 run |

Every envelope carries `"contract_version": "1.0"`, the SHA-256 and count of
each input, one decision per candidate (`verified`, `review_needed`,
`rejected`, `not_used`) with its support gaps, the counts, and the list of
detailed files the pipeline wrote next to it. `review_needed` and `rejected`
are results, not errors.

| Exit code | Meaning |
|---:|---|
| 0 | Ran. Decisions are in the envelope. |
| 1 | Unexpected internal error (JSON error on stderr). |
| 2 | Bad command line. |
| 3 | An input file or the config is missing or is not valid JSON. |
| 4 | An input does not match its schema. Nothing is written. |
| 5 | The output envelope does not match its schema (a contract bug). |

When `data/bylaws/<config stem>/source.pdf` exists and matches provenance, the
pipeline uses it for source repair and table anchoring, and the envelope says
`"source_pdf_used": true`. Without it, results can differ: on the committed
candidates Burnaby gives the same 87 verified and 57 review, while Calgary
gives 28 and 43 (committed 29 and 42) and Vancouver 7 and 34 (committed 10
and 31). See Findings in `upgrade/STATUS.md`.

Container: `docker build -t bylaw-rule-verification .` then
`docker run --rm bylaw-rule-verification bylaw-verify --help`. `make docker-smoke`
builds the image, runs the CLI on the golden `verified` fixture and checks the
demo's health endpoint.

## 2. Onboard a city

### Prerequisites

- Linux or macOS, Python 3.12, `make setup` done.
- The official bylaw PDF URL, and the page span of the zone you want.
- Network access to the city's site. No API key; nothing here is paid.

### Steps

1. Find the zone's pages (optional, prints a suggestion; writes nothing):

   ```bash
   .venv/bin/python scripts/locate_pages.py --url <pdf url> --pattern '<regex for the zone's section headings>'
   ```

2. Run the kit:

   ```bash
   make onboard CITY=<id> URL=<pdf url> PAGES=<a-b> TITLE=<City> ZONE="<zone name>" BYLAW="<bylaw name>"
   ```

   `CITY` is lower_snake_case, for example `toronto_rd`. `NAME=<id>` also works.
   For a city whose `configs/<id>.json` and `data/bylaws/<id>/provenance.json`
   are already committed (for example `surrey_r3`), run `make onboard CITY=<id>`:
   the kit keeps the config and requires the committed SHA-256.

The kit runs and times these steps:

| Step | What it does | Writes |
|---|---|---|
| config | Creates `configs/<id>.json` from `configs/_template.json` (generic settings, placeholders filled) or keeps an existing one | `configs/<id>.json` |
| source | New city: downloads the whole PDF and records provenance with the page scope. Existing city: requires the committed SHA-256 and never rewrites provenance | `data/bylaws/<id>/provenance.json`, `source.pdf` (gitignored) |
| validate_config | `scripts/validate_config.py configs/<id>.json` | nothing |
| locate | With `LOCATE=<regex>`, lists matching pages | nothing |
| page_text | Text of the scoped pages, for drafting gold rules | `outputs/onboarding/<id>/source_pages.txt` (gitignored) |
| dry_run | `scripts/run_m7_bakeoff.py --city <id> --models google/gemini-3.1-flash-lite --dry-run` with no API key in the environment | `outputs/onboarding/<id>/` (gitignored except the report) |
| gold_draft | Creates an empty `benchmark/gold/<id>_gold_rules.DRAFT.json` marked `agent_draft_unreviewed` | the draft (never overwritten) |

It writes `outputs/onboarding/<id>/ONBOARDING_REPORT.md` (source, hash,
pages, per-step timing, what ran, what is NOT RUN, config knobs) and
`onboarding_summary.json`. A step that cannot run is recorded with its reason;
steps that depend on it are NOT RUN. The exit code is 1 if any step failed.

### Verify

- `ONBOARDING_REPORT.md` shows every step PASS, or a stated reason.
- `scripts/validate_config.py configs/<id>.json` exits 0.
- `git status` shows changes only under `configs/`, `data/bylaws/<id>/provenance.json`,
  `outputs/onboarding/<id>/` and `benchmark/gold/<id>_gold_rules.DRAFT.json`.
  `tests/test_onboarding.py` checks this on a synthetic PDF.
- Review every value in `rule_family_direction` against the bylaw. The template's
  generic settings are not legal advice for your city.

### Next (not part of onboarding)

- A person reviews the draft gold rules against the PDF, then renames the file
  without `.DRAFT` to make it a benchmark.
- Real-model extraction: `make extract CITY=<id> CONFIRM_PAID=yes` (paid).

### Roll back

Delete what the run created: `configs/<id>.json` (if it was new),
`data/bylaws/<id>/` (if new), `outputs/onboarding/<id>/` and
`benchmark/gold/<id>_gold_rules.DRAFT.json`. Nothing else is touched.
