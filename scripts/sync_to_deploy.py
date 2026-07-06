#!/usr/bin/env python3
"""Sync the chatbot brain + retrieval module + precomputed vectors to the
Streamlit Cloud deploy repo (dashboard + JSON only; no burnaby_prototype package).

What it does (idempotent, NO git push):
1. Mirror the brain  src/burnaby_prototype/bylaw_chat.py -> dashboard/chat_brain.py
   (local) and -> <deploy>/dashboard/chat_brain.py, asserting byte-identity.
2. Ship the package-free retrieval module dashboard/bylaw_retrieval.py -> deploy.
3. Regenerate each city's precomputed-embedding sidecar (bylaw_rag_vectors.json)
   next to the index the deploy actually loads.
4. Ensure rank-bm25 is in the deploy requirements.txt.
5. Divergence check: the chat-helper function bodies that must stay identical
   across the two app files. The deploy streamlit_app.py is a FORK, so this
   script never copies it wholesale — it only flags drift to hand-port.

It does NOT commit or push. Review the deploy git diff, then push `main` to
trigger the Streamlit Cloud rebuild.

Usage:
    python scripts/sync_to_deploy.py [--deploy-dir ../burnaby-verification-dashboard-deploy]
                                     [--cities burnaby_r1,vancouver_rs,calgary_rcg]
                                     [--no-vectors]
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Chat-helper functions that MUST stay byte-identical across both app files.
SHARED_CHAT_FUNCS = [
    "_retrieval_module", "_dashboard_reranker", "_dashboard_embedding_backend",
    "_query_encoder", "_cached_bylaw_index", "_rerank_rag_hits", "_standalone_rag_hits",
    "_dashboard_rag_hits", "_cached_rule_index", "_read_json", "_read_json_cached",
    "_followup_chips", "_bylaw_chat_respond", "_build_brain_answer",
    "_answer_definition", "_answer_why_verification", "_answer_list_table",
    "_answer_grounded", "_render_verification_card", "_render_chat_table",
]


def _func_body(text: str, name: str) -> str | None:
    """Extract a top-level `def name(...)` body (until the next top-level def)."""
    lines = text.splitlines()
    out: list[str] = []
    inside = False
    for line in lines:
        if line.startswith(f"def {name}("):
            inside = True
            out.append(line)
            continue
        if inside:
            if line.startswith("def ") and not line.startswith(f"def {name}("):
                break
            out.append(line)
    return "\n".join(out) if out else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deploy-dir", default=str(ROOT.parent / "burnaby-verification-dashboard-deploy"))
    ap.add_argument("--cities", default="burnaby_r1,vancouver_rs,calgary_rcg")
    ap.add_argument("--no-vectors", action="store_true", help="Skip regenerating embedding sidecars.")
    args = ap.parse_args()

    deploy = Path(args.deploy_dir).expanduser().resolve()
    if not (deploy / "dashboard").is_dir():
        raise SystemExit(f"deploy dashboard not found at {deploy}/dashboard")
    cities = [c.strip() for c in args.cities.split(",") if c.strip()]

    # 1. Mirror the brain (package -> local mirror -> deploy), assert identity.
    brain_src = ROOT / "src" / "burnaby_prototype" / "bylaw_chat.py"
    local_mirror = ROOT / "dashboard" / "chat_brain.py"
    shutil.copyfile(brain_src, local_mirror)
    shutil.copyfile(brain_src, deploy / "dashboard" / "chat_brain.py")
    assert brain_src.read_bytes() == (deploy / "dashboard" / "chat_brain.py").read_bytes(), "brain mirror mismatch"
    print(f"[sync] brain mirrored -> {local_mirror.name} + deploy (byte-identical)")

    # 2. Ship the package-free retrieval module.
    retr = ROOT / "dashboard" / "bylaw_retrieval.py"
    shutil.copyfile(retr, deploy / "dashboard" / "bylaw_retrieval.py")
    print(f"[sync] shipped {retr.name} -> deploy")

    # 3. Regenerate precomputed-embedding sidecars next to the deploy's indexes.
    if not args.no_vectors:
        from build_rag_index import embed_index_to_sidecar  # type: ignore

        sys.path.insert(0, str(ROOT / "scripts"))
        for city in cities:
            ip = deploy / "outputs" / "m7_runs" / city / "google_gemini_3_1_flash_lite" / "bylaw_rag_index.json"
            if ip.exists():
                embed_index_to_sidecar(ip)
            else:
                print(f"[sync] WARN no index for {city}: {ip}")

    # 4. Ensure rank-bm25 in deploy requirements.
    reqs = deploy / "requirements.txt"
    text = reqs.read_text(encoding="utf-8")
    if "rank-bm25" not in text:
        text = text.replace(
            "plotly>=5.24",
            "plotly>=5.24\nrank-bm25>=0.2.2  # BM25 leg of the chatbot hybrid retrieval",
            1,
        )
        reqs.write_text(text, encoding="utf-8")
        print("[sync] added rank-bm25 to deploy requirements.txt")
    else:
        print("[sync] rank-bm25 already in deploy requirements.txt")

    # 5. Divergence check on shared chat-helper bodies (fork-safe: never copy the app file).
    src_app = (ROOT / "dashboard" / "streamlit_app.py").read_text(encoding="utf-8")
    dep_app = (deploy / "dashboard" / "streamlit_app.py").read_text(encoding="utf-8")
    drift = [fn for fn in SHARED_CHAT_FUNCS if _func_body(src_app, fn) != _func_body(dep_app, fn)]
    if drift:
        print("[sync] ⚠ shared chat helpers DIVERGED — hand-port these to the deploy app:")
        for fn in drift:
            print(f"         - {fn}")
    else:
        print("[sync] ✓ shared chat-helper bodies match across both apps")

    print("\n[sync] done. Review the deploy diff, then:  cd", deploy, "&& git add -A && git commit && git push origin main")


if __name__ == "__main__":
    main()
