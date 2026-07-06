"""Tests for the package-free hybrid retrieval module (dashboard/bylaw_retrieval.py).

Pins parity with burnaby_prototype.bylaw_rag.BylawIndex (so the cloud copy behaves
identically to the package), and exercises the vendored OpenRouter clients with a
stubbed urllib (no network).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT / "dashboard"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import bylaw_retrieval as br  # the cloud module under test
from burnaby_prototype.bylaw_rag import BylawIndex, load_corpus_from_sections

# Same fixture as tests/test_rag_advisory.py
SECTIONS = [
    {"section": "11.3.8.2", "page": 9, "text": "11.3.8.2 The floor area for a laneway house must not exceed the lesser of 0.25 multiplied by the site area and 186 sq. m."},
    {"section": "11.3.8.4", "page": 9, "text": "11.3.8.4 The building height for a laneway house must not exceed 8.5 m and 2 storeys."},
    {"section": "11.3.8.6", "page": 10, "text": "11.3.8.6 A laneway house must be at least 0.9 m from the ultimate rear property line."},
    {"section": "11.3.8.6", "page": 10, "text": "11.3.8.6 (c) 1.2 m from each side property line."},
    {"section": "11.3.8.5", "page": 10, "text": "11.3.8.5 The maximum site coverage is 50% of the site area for a site with a laneway house."},
]
CHUNKS = load_corpus_from_sections(SECTIONS)
QUERIES = [
    "building height limit for a laneway house",
    "floor area limits",
    "setback from the property line",
    "side property line distance",
    "maximum site coverage",
    "how tall can a laneway house be",
]


class FakeBackend:
    VOCAB = ("height", "floor", "coverage", "property", "laneway")

    def encode(self, texts):
        return [[float(word in text.lower()) for word in self.VOCAB] for text in texts]


def _keys(hits):
    return [(h["chunk_id"], h.get("signals")) for h in hits]


# --------------------------------------------------------------------------- #
# Parity with BylawIndex
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("q", QUERIES)
def test_bm25_only_parity(q):
    a = BylawIndex(CHUNKS).search(q, top_k=5)
    b = br.HybridBylawIndex(CHUNKS).search(q, top_k=5)
    assert _keys(a) == _keys(b), q


@pytest.mark.parametrize("q", QUERIES)
def test_hybrid_parity(q):
    fb = FakeBackend()
    vecs = fb.encode([c["text"] for c in CHUNKS])
    qenc = lambda s: fb.encode([s])[0]
    a = BylawIndex(CHUNKS, embedding_backend=fb).search(q, top_k=5)
    b = br.HybridBylawIndex(CHUNKS, corpus_vectors=vecs).search(q, top_k=5, query_encoder=qenc)
    assert [h["chunk_id"] for h in a] == [h["chunk_id"] for h in b], q
    assert _keys(a) == _keys(b), q


def test_dense_requires_vectors_and_encoder():
    fb = FakeBackend()
    vecs = fb.encode([c["text"] for c in CHUNKS])
    idx = br.HybridBylawIndex(CHUNKS, corpus_vectors=vecs)
    assert idx.has_dense
    bm25_only = idx.search("floor area limits", top_k=3)  # no encoder
    assert all("dense_rank" not in h["signals"] for h in bm25_only)
    hybrid = idx.search("floor area limits", top_k=3, query_encoder=lambda s: fb.encode([s])[0])
    assert any("dense_rank" in h["signals"] for h in hybrid)


def test_ask_parent_section_expansion_matches():
    a = BylawIndex(CHUNKS).ask("side property line distance", top_k=2)
    b = br.HybridBylawIndex(CHUNKS).ask("side property line distance", top_k=2)
    assert [h["chunk_id"] for h in a] == [h["chunk_id"] for h in b]
    side = next(h for h in b if "1.2 m" in h["text"])
    assert "0.9 m" in side["section_text"] and "1.2 m" in side["section_text"]


def test_determinism():
    a = br.HybridBylawIndex(CHUNKS).ask("setback from the property line", top_k=5)
    b = br.HybridBylawIndex(load_corpus_from_sections(SECTIONS)).ask("setback from the property line", top_k=5)
    assert [h["chunk_id"] for h in a] == [h["chunk_id"] for h in b]


def test_mismatched_vectors_ignored():
    idx = br.HybridBylawIndex(CHUNKS, corpus_vectors=[[1.0, 0.0]])  # wrong count
    assert not idx.has_dense
    assert idx.search("height", top_k=3)  # still works (BM25)


# --------------------------------------------------------------------------- #
# Vendored OpenRouter clients (stubbed urllib)
# --------------------------------------------------------------------------- #

class _FakeResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._b


def test_embeddings_reorder_and_count(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        # return rows out of order to prove index-sorting
        return _FakeResp({"data": [{"index": 1, "embedding": [0.0, 1.0]}, {"index": 0, "embedding": [1.0, 0.0]}]})

    monkeypatch.setattr(br.urllib.request, "urlopen", fake_urlopen)
    out = br.OpenRouterEmbeddings("key").encode(["a", "b"])
    assert out == [[1.0, 0.0], [0.0, 1.0]]
    assert captured["url"].endswith("/embeddings")
    assert captured["body"]["model"] == br.DEFAULT_EMBEDDING_MODEL
    assert captured["body"]["input"] == ["a", "b"]


def test_embeddings_count_mismatch_raises(monkeypatch):
    monkeypatch.setattr(br.urllib.request, "urlopen", lambda req, timeout=None: _FakeResp({"data": [{"index": 0, "embedding": [1.0]}]}))
    with pytest.raises(br.RetrievalError):
        br.OpenRouterEmbeddings("key").encode(["a", "b"])


def test_rerank_maps_indexes(monkeypatch):
    monkeypatch.setattr(
        br.urllib.request, "urlopen",
        lambda req, timeout=None: _FakeResp({"results": [{"index": 2, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.4}]}),
    )
    packs = [
        {"section": "a", "page": 1, "source_text": "x"},
        {"section": "b", "page": 2, "source_text": "y"},
        {"section": "c", "page": 3, "source_text": "z"},
    ]
    out = br.OpenRouterRerank("key").rerank("q", packs, top_n=2)
    assert [p["section"] for p in out] == ["c", "a"]
    assert out[0]["rerank_score"] == 0.9


def test_clients_require_key():
    with pytest.raises(br.RetrievalError):
        br.OpenRouterEmbeddings("")
    with pytest.raises(br.RetrievalError):
        br.OpenRouterRerank("")
