# Refactor Plan

Date: 2026-06-29

## Current Architecture Summary

This is a Python zoning-rule verification system with a Streamlit dashboard.
The architecture is verification-first:

```text
PDF/source corpus -> discovery/RAG evidence packs -> extraction candidates
-> source repair/context normalization -> deterministic verification
-> review/reject/not-used buckets -> verified-only GIS/dashboard exports
```

Key boundaries:

- `src/burnaby_prototype/verification.py`, `decision_policy.py`, `support_checks.py`, and related proof modules decide whether a candidate can be verified.
- `src/burnaby_prototype/m7_*` modules own M7 source discovery, model extraction, matrix candidates, evidence discovery, gap reporting, run storage, and measurement.
- `src/burnaby_prototype/slim_pipeline.py` is the orchestration layer that turns candidates/evidence into verifier outputs.
- `scripts/` contains CLI entrypoints. The stable handoff front door is `scripts/run_consolidated_prototype.py`.
- `benchmark/` contains gold rules, proposal/adversarial cases, and evaluators. Benchmarks are read-only scoring, not verifier inputs.
- `dashboard/streamlit_app.py` reads existing artifacts and presents review/GIS/chatbot surfaces. It must not mutate verifier decisions.
- `dashboard/bylaw_retrieval.py` is a package-light chatbot retrieval adapter for Streamlit deployment; it is advisory only.
- `configs/` stores city/zone vocabulary and source metadata. It is not an answer-key layer.
- `outputs/m7_runs/` stores current product artifacts; `archive/pre_m7_records/` stores historical records.

Tech stack:

- Python package with `setuptools` / `pyproject.toml`.
- Streamlit dashboard with optional Plotly/pydeck visuals.
- JSON artifacts and JSON Schema validation.
- Local PDFs under `data/bylaws/<city>/source.pdf`.
- SQLite run cache through `m7_run_store`.
- No application database, auth layer, or web API server beyond Streamlit.
- External LLM/OpenRouter calls are optional extraction/chat support paths and are not required for deterministic verification.

## Major Risks

- `dashboard/streamlit_app.py` is still very large and mixes UI composition, artifact loading, data shaping, and chatbot orchestration.
- `slim_pipeline.py`, `m7_measure.py`, and `verification.py` remain high-complexity modules; future changes should be benchmark-gated.
- Historical names remain in some internal compatibility concepts, especially Pipeline 5/Pipeline 9 adapter terminology. These are valid provenance terms but need careful wording so they do not look like current product lanes.
- The repo has no configured lint or static typecheck tool. `compileall` and tests catch syntax/runtime regressions, but not style or typing drift.
- Streamlit startup needs local socket permissions; sandboxed startup can fail even when the app is healthy.
- `.env` contains `OPENROUTER_API_KEY`; it is ignored and untracked, but local secret hygiene remains important.

## Duplicate Or Messy Areas

- Dashboard data-prep helpers are partly extracted and tested, but the main Streamlit file is still the largest coupling point.
- Chatbot logic exists in both dashboard-adjacent code and package code; tests protect import boundaries, but future extraction should continue moving pure logic out of Streamlit.
- Several scripts are intentionally CLI-oriented and share path/config patterns. They should stay simple, but common validation/path helpers should live in package modules when duplication becomes risky.
- Generated outputs are large; `.gitignore` now keeps curated M7 outputs visible and archives historical records.

## Missing Tests / Test Gaps

- No automated browser-level dashboard flow test; current smoke is Streamlit health plus pure-data dashboard tests.
- No configured lint/typecheck gate.
- Limited characterization tests for full Streamlit rendering because the dashboard is mostly UI and artifact-driven.
- External LLM extraction is intentionally not part of default tests; safety is validated after artifacts enter the deterministic verifier.

## Proposed Refactor Checkpoints

1. Preserve current behavior and clean naming/documentation surfaces around M7.
2. Make install/build/test commands reproducible and document missing lint/type gates.
3. Keep extracting pure dashboard data logic from `streamlit_app.py` behind tests.
4. Split `m7_measure.py` into smaller measurement, diagnosis, and report-rendering modules only after benchmark behavior is pinned.
5. Add a lightweight lint/static typing gate if the dependency policy allows it.
6. Add a dashboard startup/render smoke script that checks health and expected artifact availability.
7. Continue M7.5 work behind benchmark gates: extraction proposes, verification decides, dashboard/chatbot consume verified/review artifacts.

## Validation Commands

Core validation:

```bash
.venv/bin/python -m pip install -r requirements.txt --no-index
.venv/bin/python -m pip install -e . --no-build-isolation
.venv/bin/python -m pip check
.venv/bin/python -m pip wheel --no-deps --no-build-isolation . -w /private/tmp/burnaby_m7_wheel
.venv/bin/python -m compileall -q src scripts dashboard benchmark tests
.venv/bin/python -m pytest -q
```

M7 safety validation:

```bash
.venv/bin/python scripts/run_consolidated_prototype.py status
.venv/bin/python benchmark/evaluate_benchmark.py --city burnaby_r1 --output-dir outputs/m7_runs/burnaby_r1/google_gemini_3_1_flash_lite
.venv/bin/python benchmark/evaluate_adversarial.py --config configs/burnaby_r1.json --cases benchmark/gold/burnaby_r1_adversarial_cases.json --bundle-cases benchmark/gold/burnaby_r1_adversarial_bundles.json
.venv/bin/python benchmark/evaluate_m7_chatbot.py --cases benchmark/gold/m7_chatbot_gold_cases.json
```

Dashboard smoke:

```bash
.venv/bin/python -m streamlit run dashboard/streamlit_app.py --server.port 8620 --server.headless true
curl -s http://127.0.0.1:8620/_stcore/health
```

Current lint/typecheck status:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy src scripts dashboard benchmark tests
```

These are documented as not configured yet: the modules are not installed and no lint/type configuration exists in `pyproject.toml`.
