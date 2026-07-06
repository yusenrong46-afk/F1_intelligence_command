"""Convert M7 artifacts into M8 source spans."""

from __future__ import annotations

from typing import Any

from ..extraction.rule_schema import SourceSpan


def span_from_evidence_unit(unit: dict[str, Any], *, city: str, document_id: str = "source.pdf") -> SourceSpan:
    text = str(unit.get("evidence_text") or unit.get("source_text") or "")
    context = str(unit.get("source_context") or "")
    combined = text if not context or context == text else f"{text}\n{context}"
    evidence_id = str(unit.get("evidence_id") or "")
    return SourceSpan(
        city=city,
        document_id=str(unit.get("document") or document_id),
        page=_to_int(unit.get("page")),
        section_id=str(unit.get("section") or unit.get("section_id") or ""),
        block_type=str(unit.get("evidence_type") or unit.get("block_type") or "evidence"),
        char_start=0,
        char_end=len(combined),
        text=combined,
        source_url=str(unit.get("source_url") or ""),
        metadata={
            "evidence_id": evidence_id,
            "chunk_id": (unit.get("native_provenance") or {}).get("chunk_id"),
            "source_stream": unit.get("source_stream"),
        },
    )


def spans_from_evidence_units(
    evidence_units: list[dict[str, Any]],
    *,
    city: str,
    document_id: str = "source.pdf",
) -> list[SourceSpan]:
    spans: list[SourceSpan] = []
    for unit in evidence_units:
        try:
            spans.append(span_from_evidence_unit(unit, city=city, document_id=document_id))
        except ValueError:
            continue
    return spans


def spans_by_evidence_id(spans: list[SourceSpan]) -> dict[str, SourceSpan]:
    lookup: dict[str, SourceSpan] = {}
    for span in spans:
        evidence_id = str(span.metadata.get("evidence_id") or "")
        if evidence_id and evidence_id not in lookup:
            lookup[evidence_id] = span
    return lookup


def span_from_source_chunk(chunk: dict[str, Any], *, city: str, document_id: str = "source.pdf") -> SourceSpan:
    text = str(chunk.get("text") or chunk.get("source_text") or "")
    return SourceSpan(
        city=city,
        document_id=document_id,
        page=_to_int(chunk.get("page")),
        section_id=str(chunk.get("section") or chunk.get("section_id") or ""),
        block_type=str(chunk.get("block_type") or "source_chunk"),
        char_start=int(chunk.get("char_start") or 0),
        char_end=int(chunk.get("char_end") or len(text)),
        text=text,
        source_url=str(chunk.get("source_url") or ""),
        metadata={
            "chunk_id": chunk.get("chunk_id"),
            "evidence_id": chunk.get("evidence_id"),
        },
    )


def spans_from_source_chunks(chunks: list[dict[str, Any]], *, city: str, document_id: str = "source.pdf") -> list[SourceSpan]:
    spans: list[SourceSpan] = []
    for chunk in chunks:
        try:
            spans.append(span_from_source_chunk(chunk, city=city, document_id=document_id))
        except ValueError:
            continue
    return spans


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
