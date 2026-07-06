"""Local M8 hybrid retrieval.

This module supports exact lexical search, BM25 when ``rank_bm25`` is present,
metadata filters, and an optional vector adapter. The deterministic lexical path
is always available and never writes verifier outputs.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Callable

from ..extraction.rule_schema import SourceSpan
from .query_planner import PlannedQuery, plan_query


QueryVector = Callable[[str], list[float]]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)*", str(text or "").lower())


@dataclass(frozen=True)
class RetrievalHit:
    span: SourceSpan
    score: float
    rank: int
    signals: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "span": self.span.to_dict(),
            "score": self.score,
            "rank": self.rank,
            "signals": dict(self.signals),
        }


class HybridM8Index:
    def __init__(
        self,
        spans: list[SourceSpan],
        *,
        vectors: list[list[float]] | None = None,
    ) -> None:
        self.spans = list(spans)
        self._tokens = [tokenize(span.text) for span in self.spans]
        self._token_sets = [set(tokens) for tokens in self._tokens]
        self._bm25 = None
        if self.spans:
            try:
                from rank_bm25 import BM25Okapi

                self._bm25 = BM25Okapi(self._tokens)
            except Exception:
                self._bm25 = None
        self._vectors = _normalize_vectors(vectors) if vectors and len(vectors) == len(self.spans) else None

    @property
    def has_bm25(self) -> bool:
        return self._bm25 is not None

    @property
    def has_vectors(self) -> bool:
        return self._vectors is not None

    def search(
        self,
        query: str | PlannedQuery,
        *,
        top_k: int = 6,
        filters: dict[str, Any] | None = None,
        query_vector: QueryVector | None = None,
    ) -> list[RetrievalHit]:
        planned = query if isinstance(query, PlannedQuery) else plan_query(str(query or ""))
        merged_filters = {**planned.filters, **(filters or {})}
        candidates = self._eligible_indexes(merged_filters)
        if not candidates:
            return []
        query_text = " ".join(planned.all_queries())
        lexical = self._lexical_scores(query_text, candidates)
        bm25 = self._bm25_scores(query_text, candidates)
        dense = self._dense_scores(query_text, candidates, query_vector)
        hits: list[RetrievalHit] = []
        for index in candidates:
            score = lexical.get(index, 0.0) + bm25.get(index, 0.0) + dense.get(index, 0.0)
            if score <= 0:
                continue
            hits.append(
                RetrievalHit(
                    span=self.spans[index],
                    score=round(score, 6),
                    rank=0,
                    signals={
                        "lexical": round(lexical.get(index, 0.0), 6),
                        "bm25": round(bm25.get(index, 0.0), 6),
                        "dense": round(dense.get(index, 0.0), 6),
                    },
                )
            )
        hits.sort(key=lambda hit: (-hit.score, hit.span.page if hit.span.page is not None else 10**9, hit.span.span_id))
        return [
            RetrievalHit(span=hit.span, score=hit.score, rank=rank, signals=hit.signals)
            for rank, hit in enumerate(hits[:top_k], start=1)
        ]

    def _eligible_indexes(self, filters: dict[str, Any]) -> list[int]:
        rows: list[int] = []
        for index, span in enumerate(self.spans):
            if filters.get("city") and span.city != filters["city"]:
                continue
            if filters.get("page") is not None and span.page != filters["page"]:
                continue
            if filters.get("section_id") and span.section_id != filters["section_id"]:
                continue
            if filters.get("block_type") and span.block_type != filters["block_type"]:
                continue
            family = str(filters.get("rule_family") or "").replace("_", " ")
            if family and family not in span.text.lower().replace("_", " "):
                # Metadata filters should narrow but not erase table rows whose
                # metadata carries the family.
                meta_family = str(span.metadata.get("rule_family") or "").replace("_", " ")
                if family != meta_family:
                    continue
            rows.append(index)
        return rows

    def _lexical_scores(self, query: str, indexes: list[int]) -> dict[int, float]:
        query_tokens = set(tokenize(query))
        if not query_tokens:
            return {}
        scores: dict[int, float] = {}
        for index in indexes:
            overlap = query_tokens & self._token_sets[index]
            if overlap:
                scores[index] = len(overlap) / max(len(query_tokens), 1)
        return scores

    def _bm25_scores(self, query: str, indexes: list[int]) -> dict[int, float]:
        if self._bm25 is None:
            return {}
        scores = self._bm25.get_scores(tokenize(query))
        positives = [max(float(scores[index]), 0.0) for index in indexes]
        max_score = max(positives) if positives else 0.0
        if max_score <= 0.0:
            return {}
        return {index: max(float(scores[index]), 0.0) / max_score for index in indexes}

    def _dense_scores(self, query: str, indexes: list[int], query_vector: QueryVector | None) -> dict[int, float]:
        if self._vectors is None or query_vector is None:
            return {}
        try:
            vector = _normalize(query_vector(query))
        except Exception:
            return {}
        return {index: max(_dot(vector, self._vectors[index]), 0.0) for index in indexes}


def _normalize(vector: list[float]) -> list[float]:
    values = [float(item) for item in vector]
    norm = math.sqrt(sum(item * item for item in values)) or 1.0
    return [item / norm for item in values]


def _normalize_vectors(vectors: list[list[float]] | None) -> list[list[float]] | None:
    if vectors is None:
        return None
    try:
        return [_normalize(vector) for vector in vectors]
    except Exception:
        return None


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))
