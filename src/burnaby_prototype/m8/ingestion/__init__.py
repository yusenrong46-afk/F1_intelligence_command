"""M8 source-span ingestion helpers."""

from .source_blocks import spans_from_evidence_units, spans_from_source_chunks
from .source_span_store import SourceSpanStore

__all__ = ["SourceSpanStore", "spans_from_evidence_units", "spans_from_source_chunks"]
