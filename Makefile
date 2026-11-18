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
        benchmark-check gate-l1 demo demo-deps demo-check demo-health gate-l2 help

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
