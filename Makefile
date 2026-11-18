# Portfolio-standard entrypoints for the bylaw rule verification project.
# `make gate-lN` runs level N's checks and every lower level's (upgrade/SPEC.md).

PYTHON ?= $(shell command -v python3.12 || command -v python3)
VENV ?= .venv
PY := $(VENV)/bin/python
STAMP := $(VENV)/.setup-stamp
CITIES := burnaby_r1 calgary_rcg vancouver_rs
M7 := outputs/m7_runs
MODEL_DIR := google_gemini_3_1_flash_lite
# Every committed city config except the onboarding template.
CONFIG_CITIES := $(filter-out _%,$(basename $(notdir $(wildcard configs/*.json))))

.PHONY: setup derived test fetch-sources verify-artifacts check-readme secret-scan \
        benchmark-check gate-l1 demo demo-deps demo-check demo-health gate-l2 \
        eval eval-repro eval-guard docs check-docs extract l3-checks gate-l3 \
        onboard-deps onboard cli-contract docker-smoke l4-checks gate-l4 \
        walkthrough-check exercises-check l5-checks gate-l5 help

help:
	@echo "make setup | test | fetch-sources | demo | demo-check | gate-l1 .. gate-l5"

$(STAMP): requirements.txt pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --quiet --upgrade pip "setuptools>=68" wheel
	$(PY) -m pip install --quiet -r requirements.txt
	$(PY) -m pip install --quiet -e . --no-build-isolation
	touch $(STAMP)

setup: $(STAMP) derived

# Deterministic, no-model artifacts derived from the committed M7 runs.
# buildable_envelope.json is committed (whitelisted in .gitignore) and rebuilds
# byte-identically; chat_context.sqlite is gitignored and rebuilt here.
derived: $(STAMP)
	@for c in $(CITIES); do $(PY) scripts/build_buildable_envelope.py --output-dir $(M7)/$$c/$(MODEL_DIR) >/dev/null; done
	@$(PY) scripts/build_chat_context_db.py --outputs-root $(M7) >/dev/null
	@echo "derived artifacts built for: $(CITIES)"

test: $(STAMP)
	$(PY) -m pytest -q -p no:cacheprovider -rs

# Download each city's official bylaw PDF and require the SHA-256 committed in
# data/bylaws/<city>/provenance.json. Never rewrites provenance.
fetch-sources: $(STAMP)
	@fail=0; for c in $(CONFIG_CITIES); do \
	  $(PY) scripts/fetch_bylaw.py --city $$c --verify-provenance || fail=1; \
	done; exit $$fail

verify-artifacts: $(STAMP)
	$(PY) scripts/restore_m7_artifacts.py --verify
	@git diff --quiet -- $(M7) || { echo "FAIL committed M7 artifacts changed:"; git diff --stat -- $(M7); exit 1; }

check-readme: $(STAMP)
	$(PY) scripts/check_readme.py

secret-scan: $(STAMP)
	$(PY) scripts/secret_scan.py

benchmark-check: $(STAMP)
	$(PY) scripts/check_benchmark.py

gate-l1: setup verify-artifacts test check-readme secret-scan benchmark-check
	@echo "gate-l1 PASS"

# ---- L2 Demonstrable -------------------------------------------------------
DEMO_PORT ?= 8631

# The command center on localhost with committed artifacts only: no API key
# (chat uses its artifact-grounded fallback), no paid call.
demo: setup
	env -u OPENROUTER_API_KEY -u ANTHROPIC_API_KEY -u GEMINI_API_KEY -u GOOGLE_API_KEY \
	  $(PY) -m streamlit run streamlit_app.py --server.port $(DEMO_PORT) --server.headless true \
	  --browser.gatherUsageStats false

# Starts the demo in the background, requires /_stcore/health == ok, stops it.
demo-health: setup
	$(PY) scripts/demo_health.py --port $(DEMO_PORT)

demo-deps: $(STAMP)
	$(PY) -m pip install --quiet -r requirements-demo.txt
	$(PY) -m playwright install chromium

demo-check: setup demo-deps
	$(PY) scripts/demo_check.py --port $(DEMO_PORT) --out docs/demo

# gate-l2 runs the browser journey; demo-check needs Chromium (see docs/DEPLOY_DEMO.md).
gate-l2: gate-l1 demo-health demo-check
	@test -f docs/DEPLOY_DEMO.md
	@echo "gate-l2 PASS"

# ---- L3 Measured -----------------------------------------------------------
EVAL := outputs/eval_summary.json

# Offline, no model call: benchmark + adversarial cases for the three cities.
eval: setup
	$(PY) scripts/run_eval.py --out $(EVAL)

# Two fresh runs must give byte-identical summaries, equal to the committed one.
# Timings and the run date live in the .meta.json sidecar and are excluded.
eval-repro: setup
	$(PY) scripts/run_eval.py --repro --out $(EVAL)

# Guarded numbers against benchmark/eval_baseline.json.
eval-guard: setup
	$(PY) scripts/check_eval_baseline.py --summary $(EVAL)

# Regenerate the README result line and table from the committed summary.
docs: setup
	$(PY) scripts/render_results.py

check-docs: setup
	$(PY) scripts/render_results.py --check

# Real-model extraction for one city. PAID (OpenRouter; recorded M7 cost
# US$0.015 to US$0.045 per city, see model_cost_report.json). Needs
# OPENROUTER_API_KEY, the source PDF (make fetch-sources) and CONFIRM_PAID=yes.
# Writes to outputs/extract_runs/, never to the committed outputs/m7_runs/.
# Status on upgrade/2026-11: NOT RUN.
extract: setup
	@test -n "$(CITY)" || { echo "usage: make extract CITY=<city> CONFIRM_PAID=yes"; exit 2; }
	@test "$(CONFIRM_PAID)" = yes || { echo "make extract makes paid model calls; rerun with CONFIRM_PAID=yes"; exit 2; }
	$(PY) scripts/run_m7_bakeoff_engine.py --discovery-mode exhaustive --out-root outputs/extract_runs \
	  --city $(CITY) --models google/gemini-3.1-flash-lite

# The L3 checks alone (CI runs these in the gates job; gate-l3 adds L2's browser check).
l3-checks: eval-repro eval-guard check-docs
	@echo "L3 checks PASS"

gate-l3: gate-l2 l3-checks
	@echo "gate-l3 PASS"

# ---- L4 Connectable ----------------------------------------------------------
# make onboard CITY=<id> URL=<official PDF URL> [PAGES=a-b] [LOCATE=<regex>]
#   [TITLE=<display name>] [ZONE=<zone>] [BYLAW=<bylaw name>]
# NAME=<id> is accepted as a synonym for CITY. No model call.
ONBOARD_ID := $(or $(CITY),$(NAME))

onboard-deps: $(STAMP)
	$(PY) -m pip install --quiet "pdfplumber>=0.11"

onboard: setup onboard-deps
	@test -n "$(ONBOARD_ID)" || { echo "usage: make onboard CITY=<id> URL=<official PDF URL> [PAGES=a-b]"; exit 2; }
	$(PY) scripts/onboard_city.py --city $(ONBOARD_ID) $(if $(URL),--url "$(URL)") \
	  $(if $(PAGES),--pages "$(PAGES)") $(if $(LOCATE),--locate "$(LOCATE)") \
	  $(if $(TITLE),--name "$(TITLE)") $(if $(ZONE),--zone "$(ZONE)") $(if $(BYLAW),--bylaw "$(BYLAW)")

# CLI contract tests (golden example per decision bucket, exit codes).
cli-contract: setup
	$(PY) -m pytest -q -p no:cacheprovider tests/test_cli_contract.py tests/test_onboarding.py

# Container image: build, bylaw-verify --help, a golden fixture, demo health.
# Needs a Docker daemon. EXTRA_CA_BUNDLE=<file> for a TLS-intercepting proxy.
docker-smoke:
	scripts/docker_smoke.sh

l4-checks: cli-contract docker-smoke
	@test -f docs/ONBOARDING.md
	@echo "L4 checks PASS"

gate-l4: gate-l3 l4-checks
	@echo "gate-l4 PASS"

# --- L5: teach and present -------------------------------------------------
walkthrough-check: setup
	$(PY) scripts/check_walkthrough.py

# Every exercise test must FAIL on the committed stub (no solution in the repo).
exercises-check: setup
	$(PY) scripts/check_exercises.py

l5-checks: walkthrough-check exercises-check
	$(PY) scripts/check_l5_docs.py
	@echo "L5 checks PASS"

gate-l5: gate-l4 l5-checks
	@echo "gate-l5 PASS"
