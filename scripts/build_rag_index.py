#!/usr/bin/env python3
"""Build the advisory bylaw-RAG index for a city.

Corpus preference order:
1. ``data/bylaws/<city>/sections.json`` — section-anchored text from the
   internal extraction helper (best: whole-section context);
2. the city's run ``evidence_units.json`` — works for every city today.

Writes ``outputs/m7_runs/<city>/google_gemini_3_1_flash_lite/bylaw_rag_index.json``.
Advisory only: nothing in the verify path reads this artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from burnaby_prototype.bylaw_rag import (
    BylawIndex,
    build_index_payload,
    load_corpus_from_evidence_units,
    load_corpus_from_sections,
)


def embed_index_to_sidecar(index_path: Path, api_key: str | None = None, *, decimals: int = 4) -> Path | None:
    """Precompute dense embeddings for an existing index's chunks and write them
    to a ``bylaw_rag_vectors.json`` sidecar next to the index, so the cloud chat
    does only ONE query-embedding call per question (no corpus embedding).

    Rounds to ``decimals`` places (bge-m3 cosine is robust after normalization) to
    cap the shipped size. Reuses the package's OpenRouter embedding client.
    """
    from burnaby_prototype.native_extraction import (
        DEFAULT_EMBEDDING_MODEL,
        OpenRouterEmbeddingBackend,
        load_openrouter_api_key,
    )

    index_path = Path(index_path)
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    chunks = payload.get("chunks", [])
    if not chunks:
        print(f"[vectors] no chunks in {index_path}; skipping")
        return None
    api_key = api_key or load_openrouter_api_key()
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY required to precompute embeddings (set env or .env)")
    backend = OpenRouterEmbeddingBackend(api_key, model=DEFAULT_EMBEDDING_MODEL)
    vectors = backend.encode([str(c.get("text") or "") for c in chunks])
    rounded = [[round(float(x), decimals) for x in v] for v in vectors]
    sidecar = index_path.with_name("bylaw_rag_vectors.json")
    sidecar.write_text(
        json.dumps(
            {
                "embedding_model": DEFAULT_EMBEDDING_MODEL,
                "embedding_dim": len(rounded[0]) if rounded else 0,
                "chunk_count": len(rounded),
                "vectors": rounded,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    size_kb = sidecar.stat().st_size / 1024
    print(f"[vectors] {len(rounded)} x {len(rounded[0]) if rounded else 0}-dim -> {sidecar} ({size_kb:.0f} KB)")
    return sidecar


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", default="burnaby_r1")
    parser.add_argument("--ask", default=None, help="Optional smoke question to run against the fresh index.")
    parser.add_argument("--with-vectors", action="store_true", help="Also precompute dense embeddings into a sidecar.")
    parser.add_argument("--embed-existing", default=None, help="Skip rebuild; just write the vectors sidecar for this index path.")
    args = parser.parse_args()

    if args.embed_existing:
        embed_index_to_sidecar(Path(args.embed_existing))
        return

    sections_path = ROOT / "data" / "bylaws" / args.city / "sections.json"
    out_dir = ROOT / "outputs" / "m7_runs" / args.city / "google_gemini_3_1_flash_lite"
    if sections_path.exists():
        chunks = load_corpus_from_sections(json.loads(sections_path.read_text(encoding="utf-8")))
        source = str(sections_path)
    else:
        evidence_path = out_dir / "evidence_units.json"
        chunks = load_corpus_from_evidence_units(json.loads(evidence_path.read_text(encoding="utf-8")))
        source = str(evidence_path)

    payload = build_index_payload(chunks)
    payload["corpus_source"] = source
    out_path = out_dir / "bylaw_rag_index.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[rag] {len(chunks)} chunks from {source}")
    print(f"[rag] index written to {out_path}")

    if args.with_vectors:
        embed_index_to_sidecar(out_path)

    if args.ask:
        index = BylawIndex(chunks)
        for hit in index.ask(args.ask, top_k=3):
            print(f"  [{hit.get('section') or hit['chunk_id']}] score={hit['score']}: {hit['text'][:110]}")


if __name__ == "__main__":
    main()
