"""F1 proof-aware retrieval.

This checkpoint-level RAG layer ranks source spans and emits evidence records
that later extraction, verification, repair, and chatbot layers can consume. It
does not generate answers and cannot promote rules.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import ARTIFACT_SCHEMA_VERSION, RetrievalEvidence


DEFAULT_RETRIEVAL_QUERIES: tuple[str, ...] = (
    "permitted uses small-scale multi-unit housing",
    "group home permitted",
    "minimum lot area",
    "maximum lot area",
    "maximum height",
    "maximum storeys",
    "minimum setback",
    "lot coverage",
    "impervious surfaces",
    "dwelling units",
    "building separation",
    "fire access corridor",
    "automatic sprinkler",
    "community heritage register lot coverage impervious surface street yard",
    "floor area",
)

RRF_K = 60


def build_retrieval_report(
    *,
    source_spans: list[dict[str, Any]],
    city_key: str,
    run_id: str,
    queries: list[str] | None = None,
    top_k: int = 6,
) -> dict[str, Any]:
    queries = queries or list(DEFAULT_RETRIEVAL_QUERIES)
    index = _SpanIndex(source_spans)
    query_results = []
    all_evidence: list[dict[str, Any]] = []
    for query_index, query in enumerate(queries, start=1):
        hits = index.search(query, top_k=top_k)
        evidence_rows = []
        for rank, hit in enumerate(hits, start=1):
            span = hit["span"]
            quote_limit = 6000 if span.get("block_type") in {"table", "page_text"} else 900
            evidence = RetrievalEvidence(
                evidence_id=f"f1_retrieval_{query_index:03d}_{rank:02d}",
                query=query,
                span_id=str(span.get("span_id") or ""),
                rank=rank,
                score=float(hit["score"]),
                retrieval_method="lexical_bm25_rrf",
                reranker="lexical_overlap",
                quote=_quote(span.get("text"), limit=quote_limit),
                supports_fields=_supports_fields(query, span.get("text")),
            ).to_dict()
            evidence["signals"] = hit["signals"]
            evidence["page"] = span.get("page")
            evidence["section_id"] = span.get("section_id")
            evidence["block_type"] = span.get("block_type")
            evidence_rows.append(evidence)
            all_evidence.append(evidence)
        query_results.append(
            {
                "query": query,
                "top_k": top_k,
                "hit_count": len(evidence_rows),
                "hits": evidence_rows,
            }
        )
    queries_with_hits = sum(1 for row in query_results if row["hit_count"] > 0)
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "retrieval_report.json",
        "city_key": city_key,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "retrieval_method": "lexical_bm25_rrf",
        "reranker": "lexical_overlap",
        "queries": query_results,
        "evidence": all_evidence,
        "summary": {
            "source_span_count": len(source_spans),
            "query_count": len(queries),
            "queries_with_hits": queries_with_hits,
            "total_hit_count": len(all_evidence),
            "retrieval_quality_status": "pass" if queries_with_hits == len(queries) else "needs_attention",
            "note": "Checkpoint 3 retrieval quality is a smoke metric, not legal verification.",
        },
    }


def write_retrieval_report(report: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "retrieval_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


class _SpanIndex:
    def __init__(self, spans: list[dict[str, Any]]) -> None:
        self.spans = [span for span in spans if str(span.get("text") or "").strip()]
        self.tokens = [tokenize(str(span.get("text") or "")) for span in self.spans]
        self.token_sets = [set(tokens) for tokens in self.tokens]
        self.bm25 = None
        if self.spans:
            try:
                from rank_bm25 import BM25Okapi  # noqa: PLC0415

                self.bm25 = BM25Okapi(self.tokens)
            except Exception:
                self.bm25 = None

    def search(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        lexical_ranks = self._lexical_ranks(query_tokens)
        bm25_ranks = self._bm25_ranks(query_tokens)
        hits = []
        for index, span in enumerate(self.spans):
            score = 0.0
            signals: dict[str, Any] = {}
            if index in lexical_ranks:
                score += 1.0 / (RRF_K + lexical_ranks[index])
                signals["lexical_rank"] = lexical_ranks[index]
            if index in bm25_ranks:
                score += 1.0 / (RRF_K + bm25_ranks[index])
                signals["bm25_rank"] = bm25_ranks[index]
            if score > 0:
                signals["overlap_count"] = len(set(query_tokens) & self.token_sets[index])
                hits.append({"span": span, "score": round(score, 6), "signals": signals})
        hits.sort(
            key=lambda hit: (
                -hit["signals"].get("overlap_count", 0),
                -hit["score"],
                hit["span"].get("page") if hit["span"].get("page") is not None else 10**9,
                str(hit["span"].get("span_id") or ""),
            )
        )
        return hits[:top_k]

    def _lexical_ranks(self, query_tokens: list[str]) -> dict[int, int]:
        query_set = set(query_tokens)
        scored = []
        for index, token_set in enumerate(self.token_sets):
            overlap = query_set & token_set
            if overlap:
                scored.append((len(overlap) / math.sqrt(max(len(token_set), 1)), index))
        scored.sort(key=lambda item: (-item[0], str(self.spans[item[1]].get("span_id") or "")))
        return {index: rank for rank, (_, index) in enumerate(scored, start=1)}

    def _bm25_ranks(self, query_tokens: list[str]) -> dict[int, int]:
        if self.bm25 is None:
            return {}
        scores = self.bm25.get_scores(query_tokens)
        query_set = set(query_tokens)
        eligible = [index for index, token_set in enumerate(self.token_sets) if token_set & query_set]
        eligible.sort(key=lambda index: (-float(scores[index]), str(self.spans[index].get("span_id") or "")))
        return {index: rank for rank, index in enumerate(eligible, start=1)}


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)*", str(text or "").lower())


def _quote(text: Any, limit: int = 420) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    return normalized[:limit]


def _supports_fields(query: str, text: Any) -> tuple[str, ...]:
    combined = f"{query} {text}".lower()
    fields: list[str] = []
    if re.search(r"\b\d+(?:\.\d+)?\b", combined):
        fields.extend(["value"])
    if re.search(r"\b(?:m|metre|metres|meter|meters|%|percent|storeys|units|sq|square)\b", combined):
        fields.extend(["unit"])
    if re.search(r"\b(?:maximum|max|not exceed|minimum|min|at least|no more than)\b", combined):
        fields.extend(["operator"])
    if re.search(r"\b(?:height|setback|coverage|floor area|dwelling|separation)\b", combined):
        fields.extend(["rule_object", "constraint_scope"])
    return tuple(dict.fromkeys(fields))
