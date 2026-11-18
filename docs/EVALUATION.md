# Evaluation

Every number in the README's results block comes from `make eval`. This page
lists every evaluation in the repo, what it costs and whether it ran on the
`upgrade/2026-11` branch.

## Offline (no model call, US$0)

| Command | What it measures | Status |
|---|---|---|
| `make eval` | `benchmark/evaluate_benchmark.py` on the committed M7 runs for Burnaby R1, Calgary R-CG and Vancouver RS, plus `benchmark/evaluate_adversarial.py` on 34 poisoned candidates (Burnaby 24, Calgary 6, Vancouver 4) and Burnaby's 3 poisoned evidence bundles. Writes `outputs/eval_summary.json`; timings and the run date go to `outputs/eval_summary.meta.json`. | RUN 2026-11-18 (receipt: `outputs/eval_summary.json`) |
| `make eval-repro` | Two fresh runs are byte-identical and equal the committed summary. | RUN 2026-11-18, PASS |
| `make eval-guard` | Per city: false verified = 0, verified precision = 1.00, poisoned inputs leaked = 0, extraction coverage recall at or above 0.975 (Burnaby) and 1.00 (Calgary, Vancouver), verified and review counts equal the committed counts. Baseline: `benchmark/eval_baseline.json`. | RUN 2026-11-18, PASS |
| `make check-docs` | The README result line and table equal what `scripts/render_results.py` generates from the summary. | RUN 2026-11-18, PASS |

CI runs `make eval-repro eval-guard check-docs` (as `make l3-checks`) on every
pull request.

## Real model (paid; none ran on this branch)

| Command | What it does | Budget | Status |
|---|---|---|---|
| `make extract CITY=<city> CONFIRM_PAID=yes` | Full-bylaw discovery and extraction with `google/gemini-3.1-flash-lite` via OpenRouter, then the deterministic verifier. Writes `outputs/extract_runs/`. Needs `OPENROUTER_API_KEY` and the source PDF. | Recorded M7 estimates in `outputs/m7_runs/<city>/google_gemini_3_1_flash_lite/model_cost_report.json`: US$0.014857 Burnaby, US$0.044801 Calgary, US$0.032056 Vancouver. OpenRouter billing is authoritative. | NOT RUN |
| `scripts/run_native_extraction.py` | Older native RAG + LLM extraction path. | Not recorded in the repo. Set one before running. | NOT RUN |
| `scripts/run_m7_chatbot_redteam.py` | Red-team questions through the "Ask the Bylaw" chat, optionally with LLM-generated questions. | Not recorded in the repo. Set one before running. | NOT RUN |

An unrecorded cost is unknown, not zero.
