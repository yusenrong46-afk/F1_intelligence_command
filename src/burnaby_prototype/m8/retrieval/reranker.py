"""M8 reranker interfaces and deterministic fallback."""

from __future__ import annotations

from typing import Protocol

from .hybrid_index import RetrievalHit, tokenize


class Reranker(Protocol):
    def rerank(self, query: str, hits: list[RetrievalHit], *, top_k: int) -> list[RetrievalHit]:
        ...


class LexicalOverlapReranker:
    """Deterministic local fallback used when no model reranker is configured."""

    def rerank(self, query: str, hits: list[RetrievalHit], *, top_k: int) -> list[RetrievalHit]:
        query_tokens = set(tokenize(query))
        ranked = sorted(
            hits,
            key=lambda hit: (-(len(query_tokens & set(tokenize(hit.span.text))), hit.score), hit.span.span_id),
        )
        return ranked[:top_k]
