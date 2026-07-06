# F1 Deployment Guide

## Local Smoke Run

```bash
python -m streamlit run streamlit_app.py --server.port 8631
```

Health endpoint:

```text
http://localhost:8631/_stcore/health
```

Expected response:

```text
ok
```

## Streamlit Cloud

Use these settings:

```text
Repository: <your GitHub repo>
Branch: main
Main file path: streamlit_app.py
```

Optional secrets:

```toml
OPENROUTER_API_KEY = "..."
BYLAW_RAG_PROVIDER = "openrouter"
BYLAW_RAG_MODEL = "openai/gpt-oss-120b"
```

The app can run without `OPENROUTER_API_KEY`, but model-backed chat answers
will degrade to artifact-grounded fallback behavior.

## Product Data

The deployed app reads F1 artifacts from:

```text
outputs/f1_runs/burnaby_r1/checkpoint_16_product_operations/
```

Required file:

```text
command_center_app_manifest.json
```

The default repository includes the curated checkpoint artifacts needed for the
first deployed demo. Do not commit `.env`, local API keys, `.venv`, caches, or
raw model output dumps.
