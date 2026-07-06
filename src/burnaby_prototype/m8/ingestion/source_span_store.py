"""Small in-memory source-span store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..extraction.rule_schema import SourceSpan


@dataclass
class SourceSpanStore:
    spans: list[SourceSpan]

    @classmethod
    def from_spans(cls, spans: Iterable[SourceSpan]) -> "SourceSpanStore":
        return cls(list(spans))

    def by_span_id(self) -> dict[str, SourceSpan]:
        return {span.span_id: span for span in self.spans}

    def by_evidence_id(self) -> dict[str, SourceSpan]:
        rows: dict[str, SourceSpan] = {}
        for span in self.spans:
            evidence_id = str(span.metadata.get("evidence_id") or "")
            if evidence_id and evidence_id not in rows:
                rows[evidence_id] = span
        return rows

    def filter(self, *, city: str | None = None, page: int | None = None, section_id: str | None = None) -> list[SourceSpan]:
        results = self.spans
        if city:
            results = [span for span in results if span.city == city]
        if page is not None:
            results = [span for span in results if span.page == page]
        if section_id:
            results = [span for span in results if span.section_id == section_id]
        return results
