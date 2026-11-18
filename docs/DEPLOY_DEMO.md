# Deploy the demo (about ten minutes)

Based on `../DEPLOYMENT.md`. The demo is the F1 command center
(`streamlit_app.py`). It reads only committed artifacts under
`outputs/f1_runs/burnaby_r1/checkpoint_16_product_operations/`, so it needs no
database, no bylaw PDF and no API key.

## 1. Check it locally (2 minutes)

```bash
make setup
make demo-health   # starts the app, expects /_stcore/health -> ok, stops it
make demo          # http://localhost:8631
```

`make demo-check` drives Chromium through every page and refreshes the
screenshots and video in `docs/demo/` (needs `make demo-deps` once).

## 2. Streamlit Community Cloud (5 to 8 minutes)

1. Sign in at share.streamlit.io with the GitHub account that owns this repo.
2. Click **Create app**, then **Deploy a public app from GitHub**.
3. Fill in:

   | Field | Value |
   |---|---|
   | Repository | `yusenrong46-afk/F1_intelligence_command` (or the renamed repo) |
   | Branch | `main` once the upgrade PR is merged (or `upgrade/2026-11` to preview) |
   | Main file path | `streamlit_app.py` |
   | App URL | your choice, for example `bylaw-rule-verification` |

4. Open **Advanced settings** and set **Python version** to `3.12`.
5. Leave **Secrets** empty. With no key the "Ask the Bylaw" chat answers from
   the committed artifacts only, which costs nothing.
6. Click **Deploy**. The first build installs `requirements.txt` (a few minutes).
7. Check `https://<your-app>.streamlit.app/_stcore/health` returns `ok`, then put
   the URL in the README's first screen.

## Environment variables

| Variable | Needed for the demo | Effect |
|---|---|---|
| none | yes | The demo runs from committed artifacts. |
| `OPENROUTER_API_KEY` | no | Turns on model-written chat answers. Each question is a paid call. Leave unset for a free public demo. |
| `BYLAW_RAG_PROVIDER` | no | `openrouter` when a key is set. |
| `BYLAW_RAG_MODEL` | no | For example `openai/gpt-oss-120b` when a key is set. |

Never commit `.env`, keys, `.venv`, caches or raw model output.

## Roll back

Delete the app in the Streamlit Cloud dashboard, or point it back at the
previous branch. Nothing else is deployed.
