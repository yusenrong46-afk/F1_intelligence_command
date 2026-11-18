# Upgrade status: P1 bylaw rule verification

Branch `upgrade/2026-11`, based on `main` at `8ecab50`. Spec: `upgrade/SPEC.md`.
Draft PR: https://github.com/yusenrong46-afk/F1_intelligence_command/pull/1.
Every PASS below carries the command that was run on 2026-11-18 and the output
line that shows it. "Local" means this agent's Linux container; "CI" means
GitHub Actions on this branch.

## Gates

| Gate | Status | Evidence |
|---|---|---|
| Preflight baseline | PASS (matches expected) | see Preflight |
| L1 Reachable | BLOCKED (one item) | Local and CI: `make gate-l1` → `gate-l1 PASS`. CI job `gates` green on every push. BLOCKED item: "CI is green on your branch". The `sources` job fails because 3 of 4 official PDFs changed upstream and Vancouver returns HTTP 403 to CI (Findings 1). Needs Thomas 3. |
| L2 Demonstrable | PASS | Local: `make demo-health` → `PASS http://127.0.0.1:8631/_stcore/health -> ok (no API key in env)`. Local: `scripts/demo_check.py --port 8631 --out docs/demo` → 7 × `PASS page rendered`, `PASS verified rule shown with source text: Source text (page 2, section 101.4): "4 m"`, `PASS only allowlisted hosts contacted: fonts.googleapis.com, fonts.gstatic.com, localhost`. CI run 44385509813 crashed on a path print after the same PASS lines (fixed in `d40fdff`, test added); CI `demo` job 135097501379 on `d40fdff` then passed every step. Media: `docs/demo/` 3 PNG + 1 WebM, 2.1 MB total. |
| L3 Measured | PASS | Local and CI: `make l3-checks` → `PASS eval summary byte-identical across two runs and equal to eval_summary.json`, `check-docs OK: README.md matches eval_summary.json (measured 2026-11-18)`, baseline guard OK. `tests/test_upgrade_l3.py` proves each guard fails on a regression. |
| L4 Connectable | PASS (one exception, below) | Local: `make cli-contract` → 15 passed (14 in the full gate run below, before the quote-check test was added). Local and CI: `make docker-smoke` → `docker smoke PASS`. CI `onboarding` job: `make onboard CITY=toronto_rd ...` → all 6 run steps PASS (`source` 1,218,396 bytes, sha256 `f19ca4ce…`, 328 pages; `dry_run` 41.42 s, 70 evidence packs). 40 Toronto draft gold rules, quotes checked against the page text (see Toronto). Exception: Surrey onboarding FAIL on source drift (by design, provenance not rewritten). |
| L5 Explainable | PASS | Local: `make l5-checks` → `walkthrough OK: 10 questions, ...`, `PASS 01_unit_operator: 8 tests fail on the unsolved stub` (and 9, 13), `L5 docs OK: case study cited from the four sources, demo script, three measured bullets`. |

`make gate-l5` locally: see "Full gate run" at the end.

## Preflight

Python 3.12.3 venv, `pip install -r requirements.txt && pip install -e . --no-build-isolation`, `pytest -q`.

- Expected on 2026-11-18: 669 passed, 20 failed, 23 skipped.
- Measured: `20 failed, 669 passed, 23 skipped in 7.09s`. Matches.
- Note: on a fresh Python 3.12 venv, `pip install -e . --no-build-isolation`
  fails with `ModuleNotFoundError: No module named 'setuptools'` until
  setuptools is installed first. `make setup` installs it.

After this branch, `make test` locally: `742 passed, 11 skipped, 3 subtests passed`.
Every skip prints `source PDF not fetched (run make fetch-sources)`.

## What each level added

- **L1** (`1aae90c`, `ac30e04`): `scripts/restore_m7_artifacts.py` restores 93 M7
  artifacts byte-identically (`outputs/m7_runs/MANIFEST.sha256`); `make setup test
  fetch-sources gate-l1`; CI; README first screen with `scripts/check_readme.py`;
  `scripts/secret_scan.py` (also rejects new files over 5 MB);
  `scripts/fetch_bylaw.py --verify-provenance` (SHA-256 checked, never rewrites
  provenance); a cookie-keeping opener for Calgary's redirect.
- **L2** (`28aaac4`, `d40fdff`): `make demo demo-health demo-check`, verified rule
  cards show their quoted source text, `docs/DEPLOY_DEMO.md`, media in `docs/demo/`.
- **L3** (`a6fc0b0`): `make eval` → `outputs/eval_summary.json` (+ `.meta.json`
  sidecar), generated README results, `benchmark/eval_baseline.json` guard,
  `docs/EVALUATION.md` (every real-model eval NOT RUN, with command and budget).
- **L4** (`cd062fc`): `bylaw-verify` (contract 1.0, 3 JSON schemas, 6 exit codes,
  golden fixture per bucket), `make onboard`, `scripts/locate_pages.py`,
  `configs/_template.json`, Dockerfile + `make docker-smoke`, `docs/ONBOARDING.md`;
  (`923e294`, `c30f50b`) draft-gold quote check, Surrey and Toronto onboarding outputs, 40 Toronto draft rules.
- **L5** (`08e3c08`): `docs/WALKTHROUGH.md` + checker, `exercises/` (3) + checker,
  `docs/CASE_STUDY.md`, `docs/DEMO_SCRIPT.md`, `upgrade/RESUME_BULLETS.md` (generated).

## Toronto

Both cities are **exploratory**: no reviewed gold, so no accuracy number.

`make onboard` ran in CI (run 44389640405, job 135103466447), because
toronto.ca is not reachable from this environment. The outputs were copied from
the job log, each checked against the SHA-256 the job printed, and committed in
`c30f50b`.

Locate: `scripts/locate_pages.py --pattern '^\s*10\.20\.\d+'` → pages
`[4, 61, 62, 63, 64, 65, 66]`, suggested `61-66` (page 4 is the table of contents).

| Step | Toronto RD | Seconds | Surrey R3 | Seconds |
|---|---|---:|---|---:|
| config | PASS (created from template) | 0.0 | PASS (kept reviewed config) | 0.0 |
| source | PASS, 1,218,396 bytes, sha256 `f19ca4ce…`, 328 pages | 0.27 | FAIL, upstream PDF changed (Findings 1), provenance not rewritten | 0.17 |
| validate_config | PASS | 0.03 | PASS | 0.03 |
| page_text | PASS, pages 61 to 66 | 2.95 | NOT RUN (needs matching source) | |
| dry_run | PASS, 70 evidence packs, 0 model calls, US$0 | 41.42 | NOT RUN | |
| gold_draft | PASS | 0.0 | PASS (empty draft) | 0.0 |

Reports: `outputs/onboarding/<id>/ONBOARDING_REPORT.md` and `onboarding_summary.json`.

Draft gold: `benchmark/gold/toronto_rd_gold_rules.DRAFT.json`, **40 rules**
(setbacks 14, heights, storeys and wall rules 10, building length and depth 4, lot and
use conditions 8, platforms, dormers and attic 4), each with `source_page`, an
exact `quote` and `"label_source": "agent_draft_unreviewed"`.
`scripts/check_draft_gold_quotes.py --min-rules 30` → `draft gold OK: 40 rules,
every quote found on its cited page`, locally on the page text from the CI log;
CI runs the same check after each onboarding. Rules whose value is only on an
overlay map (HT, ST, "a", "f", "d", lot coverage) are left out because the value
is not in the text. Surrey's draft is empty: its page text could not be produced.

## Decisions

Conservative readings taken without asking, per section 2 of the spec.

1. `make fetch-sources` checks each PDF against the committed SHA-256 and fails
   on a mismatch; it never rewrites provenance. Re-baselining would silently
   change what the M7 numbers were measured on.
2. CI runs the strict source check as its own `sources` job, and the `gates` job
   fetches what still matches and runs the gates anyway, so drift is visible
   without hiding everything else.
3. Tests that need a source PDF skip with one stated reason instead of failing.
4. `buildable_envelope.json` is committed (it was missing and the dashboard reads it).
5. The demo uses the committed checkpoint_16 demo manifest (Burnaby R1, 38 verified
   of 51). The README benchmark numbers come from the M7 runs. `docs/DEMO_SCRIPT.md`
   tells the presenter which is which.
6. Demo media was captured locally with the same script as CI (Chromium 130 from
   the Playwright 1.48 container image), because GitHub's artifact storage is not
   reachable from this environment. Google Fonts is also blocked here, so icon
   names (for example "keyboard_double_") render as text in the screenshots. A
   CI-captured set is uploaded as the `demo-media` artifact on every push.
7. The eval sidecar holds the date and timings; the README date is read from it.
8. `contract_version` lives in the CLI envelope and its error JSON. The pipeline's
   own detail files are unchanged and listed under `artifacts`.
9. The CLI uses the city's cached source PDF when present, as the pipeline always
   has, and records `source_pdf_used` (Findings 2).
10. The onboarding dry run writes to `outputs/onboarding/<id>/` with
    `--no-source-corpus` and its own SQLite cache, so it never touches committed
    corpora or caches.
11. `configs/_template.json` copies Surrey R3's generic settings, the one config
    with no city-specific tuning.
12. Toronto source: the enacted By-law 569-2013 Schedule A, volume 1, chapters
    1 to 800, from toronto.ca. Chapter 10.20 (RD zone) is found by heading pattern
    (pages 61 to 66). The whole PDF is stored so page numbers stay official.
13. `make extract` refuses to run without `CONFIRM_PAID=yes` and writes to
    `outputs/extract_runs/`, never over the committed M7 runs. NOT RUN (US$0 budget).
14. The Docker build takes an optional CA bundle as a BuildKit secret for proxied
    networks. TLS verification is never disabled.
15. `pytest` `testpaths` is pinned to `tests/`, which is where every test already
    lived, so the deliberately failing exercises stay out of `make test`.
16. Case study, demo script, résumé bullets and Toronto draft gold are labelled
    `agent_draft_unreviewed`.

## Findings

Not fixed here (out of scope or needs a decision), except where marked.

1. **Official PDFs drifted.** CI run 44385509813, `sources` job:
   Burnaby now 531,729 bytes, sha256 `0f9683…` (provenance 443,033, `4eb9ad…`);
   Calgary 23,164,530 bytes `af9088…` (provenance 22,469,286, `25d15e…`);
   Surrey 3,299,125 bytes `9b6966…` (provenance 3,281,006, `b18d03…`);
   Vancouver `HTTP 403`. The committed M7 results were measured on the old files.
2. **Results depend on the cached PDF.** Re-verifying the committed candidates
   without the source PDFs gives Calgary 28 verified / 43 review and Vancouver
   7 / 34, against committed 29 / 42 and 10 / 31. Burnaby matches (87 / 57).
   `bylaw-verify` gives the same. So a fresh clone cannot reproduce Calgary and
   Vancouver exactly until Finding 1 is resolved.
3. **Revised F1 proposal gold fails its own gate.** With the committed gold,
   Burnaby `proposal_case_accuracy` is 0.9 and `quality_gates_passed` is false.
   Gold is protected, so it was not edited; it is reported in `eval_summary.json`
   but not guarded.
4. **A checkpoint script rewrites history.** `scripts/run_f1_checkpoint.py
   --run-id checkpoint_0` writes into protected `outputs/f1_runs/`. Not run.
5. **pdfplumber is missing from `requirements.txt`**; the dry run needs it.
   `make onboard-deps` installs it. Fixed for onboarding only.

Fixed on this branch, with tests: Calgary's cookie-gated 302 loop in
`fetch_bylaw.py`; a stale README Calgary count (30 / 41); `demo_check.py`
crashing on a relative output path.

## Not verified

- The hosted Streamlit demo URL (blocked from this environment).
- Any real-model extraction (`make extract`): NOT RUN, budget US$0.
- Byte-identical M7 reproduction from a fresh clone (Findings 1 and 2).
- The Toronto config's `rule_family_direction` against the by-law (template values).

## Needs Thomas

In order. Times are estimates.

1. **Confirm the code may be public** (15 min). Ask Green Metrics Technology and
   UBC; the repository is already public.
2. **Review and merge PR #1** (45 min).
   https://github.com/yusenrong46-afk/F1_intelligence_command/pull/1 → Ready for
   review → Squash and merge (or merge commit, to keep the level commits).
3. **Decide on the drifted source PDFs** (20 min to decide). Either supply the
   original PDFs (put them at `data/bylaws/<city>/source.pdf`; `make fetch-sources`
   then reports MATCH), or accept re-baselining, which changes what the M7
   numbers mean and is a separate, deliberate change:
   ```bash
   .venv/bin/python scripts/fetch_bylaw.py --city burnaby_r1   # rewrites provenance; do NOT run without deciding
   ```
   Until then CI's `sources` and `onboarding` (Surrey) jobs stay red.
4. **Review the 40 Toronto draft gold rules** (about 2 hours).
   `benchmark/gold/toronto_rd_gold_rules.DRAFT.json`: check each `quote` against
   the cited page of the PDF, fix or delete, then rename without `.DRAFT`:
   ```bash
   git mv benchmark/gold/toronto_rd_gold_rules.DRAFT.json benchmark/gold/toronto_rd_gold_rules.json
   ```
   Also check `rule_family_direction` in `configs/toronto_rd.json`.
5. **Rename the repository** (5 min). GitHub → Settings → General → Repository
   name → `bylaw-rule-verification` → Rename. Then
   `git remote set-url origin https://github.com/yusenrong46-afk/bylaw-rule-verification.git`.
6. **Host the demo** (10 min). Follow `docs/DEPLOY_DEMO.md`, then confirm the URL
   returns 200 and update the README link.
7. **Optional: paid Toronto extraction** (about 5 min, roughly US$0.02 to US$0.05
   judging by the recorded M7 runs; not a quote).
   ```bash
   export OPENROUTER_API_KEY=...   # your key; never commit it
   make extract CITY=toronto_rd CONFIRM_PAID=yes
   ```

## Full gate run

Local, 2026-11-18, `make gate-l5` (runs gate-l1 through gate-l5 in order), exit 0.
Key lines from the log:

```
742 passed, 11 skipped, 3 subtests passed in 14.12s
README first screen OK (README.md)
gate-l1 PASS
PASS verified rule shown with source text: Source text (page 2, section 101.4): "4 m"
gate-l2 PASS
PASS eval summary byte-identical across two runs and equal to eval_summary.json
check-docs OK: README.md matches eval_summary.json (measured 2026-11-18)
gate-l3 PASS
14 passed in 4.68s
PASS image built: bylaw-rule-verification:smoke
PASS bylaw-verify --help (contract 1.0)
PASS bylaw-verify golden fixture -> verified
PASS demo container /_stcore/health -> ok
docker smoke PASS
gate-l4 PASS
walkthrough OK: 10 questions, 29 pointers, every answer under 120 words
PASS 01_unit_operator: 8 tests fail on the unsolved stub
PASS 02_range_guard: 9 tests fail on the unsolved stub
PASS 03_mini_verifier: 13 tests fail on the unsolved stub
L5 docs OK: case study cited from the four sources, demo script, three measured bullets
gate-l5 PASS
```

The demo step rewrites `docs/demo/` media (video and screenshots are not
byte-reproducible); the committed set was restored after the run.
