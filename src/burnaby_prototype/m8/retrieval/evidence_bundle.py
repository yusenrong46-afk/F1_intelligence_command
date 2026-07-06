"""Build M8 evidence bundles from retrieval hits."""

from __future__ import annotations

from ..extraction.rule_schema import EvidenceBundle, EvidencePointer, stable_id
from .hybrid_index import RetrievalHit


def build_evidence_bundle(query: str, hits: list[RetrievalHit], *, bundle_id: str | None = None) -> EvidenceBundle:
    spans = tuple(hit.span for hit in hits)
    pointers = []
    for hit in hits:
        evidence_id = str(hit.span.metadata.get("evidence_id") or hit.span.metadata.get("chunk_id") or hit.span.span_id)
        pointers.append(
            EvidencePointer(
                evidence_id=evidence_id,
                span_id=hit.span.span_id,
                field_name="retrieved_context",
                quote=hit.span.text[:500],
                source_span=hit.span,
                confidence=max(0.0, min(float(hit.score), 1.0)),
                metadata={"rank": hit.rank, "signals": hit.signals},
            )
        )
    return EvidenceBundle(
        bundle_id=bundle_id or "bundle_" + stable_id(query, *(span.span_id for span in spans)),
        query=query,
        spans=spans,
        pointers=tuple(pointers),
        ranking_signals={
            "hit_count": len(hits),
            "top_score": hits[0].score if hits else 0.0,
        },
    )
