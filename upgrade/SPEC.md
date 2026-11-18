# Upgrade spec (verbatim from Thomas's prompt, 2026-11-18)

This file copies sections 2 and 3 and the P1 project spec of the prompt
"Upgrade five portfolio projects to the Portfolio Standard (L1 to L5)" word for
word. It is the contract this branch is built against. Progress and evidence
live in `upgrade/STATUS.md`.

---

## 2. Rules

1. **Branch and PR.** In each repo work on `upgrade/2026-11` and open one draft PR titled `Upgrade to Portfolio Standard L1 to L5`. Commit at least once per level with a conventional commit message.
2. **Repo instructions stay in force.** Read each repo's `CLAUDE.md`, `AGENTS.md` and any protected-files list first. Where they are stricter than this prompt, they win. Where this prompt is stricter, it wins.
3. **Do not ask, decide.** If something is ambiguous, take the most conservative reading, write it under Decisions in `upgrade/STATUS.md`, and continue.
4. **Investigate before you change.** When a check fails, read the whole output, reproduce it in isolation, find the cause, fix the cause. Never edit a test to match the code unless the test contradicts its own spec. After three distinct failed attempts, mark the gate BLOCKED with the evidence and continue with work that does not depend on it.
5. **Never weaken.** Do not remove, relax, skip or bypass an existing test, threshold, lint rule, type setting, coverage gate, mutation gate, frozen evaluation file or protected file to make something pass. You may add.
6. **Report only what you ran.** Every PASS in a status file carries the command and the output line that shows it. A result you did not produce in this session is not a result.
7. **Invent nothing.** No invented metric, user, customer, quote, licence, permission or cost. Unknown stays "unknown" or "not recorded".
8. **Fictional data only.** Demo seeds, fixtures and screenshots use invented content. Never put real personal writing, credentials or keys in a file, log or screenshot. Never print a credential.
9. **Label authorship.** Keep each repo's existing statement about AI assistance. Anything you draft that needs human judgment (gold labels, benchmark questions, case-study facts) is marked `agent_draft_unreviewed` until Thomas reviews it.
10. **Stay in scope.** Build what the spec for that level says. If you find a real bug outside the spec, fix it only if it is small and has a test; otherwise list it under Findings.
11. **Messages.** Send Thomas at most one progress message a day, plus the final report. Message immediately only if you find a leaked secret or discover that a default branch or a production system changed.

## 3. The Portfolio Standard

A project is at level N when `make gate-lN` exits 0 in a fresh clone. Add `make gate-l1` through `make gate-l5` to every repo (create a `Makefile` where none exists; where Makefile targets are protected, add new targets only). Each gate target runs that level's automated checks and every lower level's. Level-specific details are in section 6.

**L1 Reachable. A stranger can open it and run it.**
- `make setup` then `make test` pass from a fresh clone on Linux. Every skipped test states its reason.
- CI runs setup, tests and the gate scripts on every pull request and is green on your branch.
- The README's first screen has: one sentence saying what it does and for whom, one dated result with its number, one image, and how to see it (demo link or one command). `scripts/check_readme.py` asserts these and that every relative link resolves.
- All finished work is on one branch. Fold in finished open branches, or list each with the reason it stays out.
- A secret scan is clean. No new file over 5 MB.

**L2 Demonstrable. Anyone can try it in two minutes with no account, no key and no cost.**
- `make demo` starts the product on localhost with fictional or synthetic data, no credentials and no paid call.
- `make demo-check` drives a browser through the main journey, asserts what a visitor should see, and saves three screenshots and one short video under `docs/demo/`.
- During `demo-check`, no request leaves the machine except to hosts on a short allowlist written in the test (map tiles, fonts). The test asserts this.
- `docs/DEPLOY_DEMO.md` gives Thomas the exact steps and environment variables to host the demo in under ten minutes.

**L3 Measured. Every number in the README regenerates from a command.**
- `make eval` runs offline, makes no paid call, and writes a results file. Two runs give byte-identical files. Timestamps and timings go in a sidecar file that this check excludes.
- The README results block is generated from that file. `make check-docs` fails when they differ.
- CI fails when a guarded number falls below its committed baseline.
- Every real-model evaluation has a documented command, a stated budget, and a status of RUN (with receipts) or NOT RUN.

**L4 Connectable. It plugs into another system and can be set up for a new customer from config.**
- One documented, versioned interface (HTTP with OpenAPI, MCP, or CLI with JSON Schema) with contract tests. It calls the existing code; it is never a second implementation.
- `make onboard NAME=<new>` sets up a new city, database, region or environment with no source edits and writes a report with per-step timings.
- A container image builds and passes a smoke test, or the status file records that Docker was unavailable.
- `docs/ONBOARDING.md`: prerequisites, steps, how to verify, how to roll back.

**L5 Explainable. Thomas can defend it live.**
- `docs/WALKTHROUGH.md`: ten questions an interviewer would ask, each answered in under 120 words with a pointer to file and symbol. `scripts/check_walkthrough.py` asserts every pointer exists.
- `docs/CASE_STUDY.md` in customer-loop form: problem, discovery, scope, build, demo-back, result, what I would change. Every factual claim cites a file or artifact in the repo.
- `exercises/`: three stand-alone hand-coding exercises, each a stub, failing tests and hints. No solution anywhere in the repo. The gate asserts the tests fail on the stubs.
- `docs/DEMO_SCRIPT.md`: a 90-second spoken demo and a five-minute deep-dive outline.
- `upgrade/RESUME_BULLETS.md`: three bullets backed only by numbers the repo now generates.

---

### P1. Bylaw rule verification (Green Metrics Technology capstone)

**Repo:** `yusenrong46-afk/F1_intelligence_command` (public). **Related:** `yusenrong46-afk/burnaby-verification-dashboard` (public; hosted Streamlit dashboard; holds the committed M7 run artifacts).

**Context.** A client-sponsored UBC Master of Data Science capstone, four-person team. An LLM extracts zoning rules from municipal bylaw PDFs; a deterministic verifier decides which rules the source supports. Thomas led verification. "F1" is his own continuation after the capstone. Keep verification at the centre of everything you write.

**Protected.** `benchmark/gold/**`. `archive/**` and `outputs/f1_runs/**` (history). The verifier's behaviour: any change to `src/burnaby_prototype/verification.py`, `support_checks.py`, `table_natural_logic.py`, `normalization_rules.py`, `decision_policy.py` or `conflict_guard.py` must leave every committed city's bucket counts unchanged and false-verified at 0. Restored run artifacts stay byte-identical to their source.

**Known state.** The curated M7 run artifacts are whitelisted in `.gitignore` but were never committed here; they exist in the dashboard repo. Bylaw PDFs are gitignored, with URL and SHA-256 committed in `data/bylaws/<city>/provenance.json`. Two README commands mislead on a clean clone: `scripts/run_slim_verifier.py --city burnaby_r1` raises FileNotFoundError, and `benchmark/evaluate_benchmark.py --city burnaby_r1` prints "Benchmark complete" with precision 0.00. With the artifacts copied in, the suite gives 691 passed, 9 failed, 9 skipped, and the benchmark prints precision 1.00 and 0 false verified for all three cities. Committed counts: Burnaby 87 verified, 57 review, of 144 candidates; Calgary 29 and 42 of 150; Vancouver 10 and 31 of 56. The README table says Calgary 30 and 41, which is stale. There is no CI.

**L1**
1. Restore `outputs/m7_runs/{burnaby_r1,calgary_rcg,vancouver_rs}/` from the dashboard repo at `e1a150f`, limited to files `.gitignore` already whitelists plus any file a test needs. Write `outputs/m7_runs/MANIFEST.sha256` naming the source commit.
2. Add `make setup`, `make test` and `make fetch-sources`. The last runs `scripts/fetch_bylaw.py` for each city in `configs/` and verifies SHA-256 against `provenance.json`. A mismatch fails. Never overwrite provenance.
3. Tests that need a source PDF skip with the reason `source PDF not fetched (run make fetch-sources)` when it is absent. Add no other skip.
4. `benchmark/evaluate_benchmark.py` exits non-zero with a clear message when the output directory has no `verified_rules.json`. Add a regression test. Fix or remove every README command that fails on a clean clone.
5. Add `.github/workflows/ci.yml`: setup, fetch-sources, test, gate scripts.
6. Rewrite the README's first screen to the standard. Say plainly: client-sponsored capstone, four-person team, Thomas led verification, F1 is his continuation. Move the long history into `docs/` and link it. Delete nothing from `docs/`.
7. Add to Needs Thomas: rename the repo to `bylaw-rule-verification`.

*Done when:* `pytest -q` reports 0 failed. For each of the three cities, `python benchmark/evaluate_benchmark.py --city <city> --output-dir outputs/m7_runs/<city>/google_gemini_3_1_flash_lite` prints `Verified precision: 1.00` and `False verified: 0`. The same command on a missing directory exits non-zero. CI is green.

**L2**
1. `make demo`: `python -m streamlit run streamlit_app.py --server.port 8631 --server.headless true`. `/_stcore/health` returns `ok`. No API key; chat uses its artifact-grounded fallback.
2. `make demo-check`: visit each top-level page of the command center, assert that at least one verified rule is shown with its quoted source text, save screenshots and video.
3. Confirm the hosted dashboard URL in the dashboard repo's README returns HTTP 200 and link it. If it does not respond, add "wake or redeploy the Streamlit app" to Needs Thomas.
4. `docs/DEPLOY_DEMO.md` from the existing `DEPLOYMENT.md`.

**L3**
1. `make eval` runs the benchmark for the three cities and `benchmark/evaluate_adversarial.py` for each city's cases (Burnaby 24 plus 3 bundles, Calgary 6, Vancouver 4: 34 single cases and 3 bundles) and writes `outputs/eval_summary.json`.
2. Generate the README results table from that file.
3. CI guards, per city: false verified = 0; verified precision = 1.00; adversarial leaked = 0; extraction coverage recall at or above 0.975 (Burnaby), 1.00 (Calgary), 1.00 (Vancouver); verified and review counts equal the committed counts.
4. Document `make extract CITY=<city>` as the real-model recipe. The recorded extraction cost in `model_cost_report.json` was US$0.015 to US$0.045 per city. Status NOT RUN.

**L4**
1. **CLI contract.** Console script `bylaw-verify --candidates <rule_candidates.json> --evidence <evidence_units.json> --config configs/<city>.json --out-dir <dir>`. Validate inputs and outputs against `schemas/`. Put a `contract_version` in every output. `tests/test_cli_contract.py` holds one golden example per decision bucket (verified, review needed, rejected, not used), taken from committed artifacts. Document exit codes.
2. **Onboarding kit.** `make onboard CITY=<id> URL=<official PDF URL> [PAGES=a-b]`: create `configs/<id>.json` from a new `configs/_template.json`; fetch and record provenance; run `scripts/validate_config.py`; run the no-LLM dry run `scripts/run_m7_bakeoff.py --city <id> --models google/gemini-3.1-flash-lite --dry-run`; write `outputs/onboarding/<id>/ONBOARDING_REPORT.md` (source, hash, pages, per-step timing, what ran, what is NOT RUN, which config knobs were set) and `benchmark/gold/<id>_gold_rules.DRAFT.json`.
3. Run the kit for `surrey_r3` (config and provenance already exist) and for `toronto_rd`: City of Toronto Zoning By-law 569-2013, Residential Detached zone. Find the official PDF on toronto.ca and scope pages to that zone. For Toronto, read the bylaw text yourself and draft at least 30 gold rules, each with page number and exact quoted span, each marked `"label_source": "agent_draft_unreviewed"`. Both cities stay labelled exploratory everywhere: the repo's own constitution says a city without a gold benchmark is exploratory only.
4. The diff for the two onboardings may touch only `configs/`, `data/bylaws/<id>/provenance.json`, `outputs/onboarding/` and `benchmark/gold/*.DRAFT.json`. If a source edit turns out to be unavoidable, stop that city and record exactly why. That is a finding, not a failure to hide.
5. `Dockerfile` whose image runs `bylaw-verify --help` and the demo. Smoke test.
6. `docs/ONBOARDING.md`.

**L5.** Walkthrough questions centre on verification: how a rule becomes verified; why a table cell with the right number is not auto-verified; what the "1 to 3 units" range bug was and how the guard stops it; what the 34 poisoned cases contain; what "review needed" means for the client; how a new city is onboarded; where a false verification could still come from. Case study facts come only from `docs/M7_SYSTEM_HANDOFF.md`, `docs/M7_FINAL_RELEASE.md`, `docs/M7_PRESENTATION_NOTE.md` and `docs/M8_CANVA_STAKEHOLDER_REPORT.md`; where the client's words or reactions are not recorded, write "not recorded". Exercises (stand-alone, no imports from `src/`): a unit and operator compatibility check; a guard that reads "1 to 3 units" as a range and never as a maximum of 3; a mini-verifier that must reject a poisoned candidate.

**Needs Thomas.** Confirm with Green Metrics Technology and UBC that this code may be public (it already is). Rename the repo. Review and merge the PR. Review the 30 Toronto draft gold rules (about two hours). Optionally run `make extract CITY=toronto_rd`.
