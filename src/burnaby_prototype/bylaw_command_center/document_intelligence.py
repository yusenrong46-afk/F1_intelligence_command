"""F1 document intelligence.

This layer converts a registered official source PDF into product-level
document blocks and source spans. It prefers the existing Docling-aware ingest
helper when available, then falls back to pypdf so checkpoint execution does not
depend on optional layout tooling.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import ARTIFACT_SCHEMA_VERSION, DocumentBlock, SourceDocument, SourceSpan


def build_document_intelligence(
    *,
    source_registry: dict[str, Any],
    run_id: str,
    root: Path,
    prefer_docling: bool = True,
) -> dict[str, Any]:
    documents = source_registry.get("documents") or []
    if not documents:
        raise ValueError("source_registry contains no documents")
    source_document = SourceDocument(**documents[0])
    pdf_path = root / source_document.local_path
    if not pdf_path.exists():
        raise FileNotFoundError(f"registered source PDF not found: {pdf_path}")

    page_ranges = _page_ranges(source_document.scoped_pages)
    intermediate = _ingest_pdf(pdf_path, prefer_docling=prefer_docling, page_ranges=page_ranges)
    intermediate = _restrict_intermediate_to_pages(intermediate, page_ranges)
    return build_document_intelligence_from_intermediate(
        intermediate=intermediate,
        source_document=source_document,
        city_key=str(source_registry.get("city_key") or source_document.city),
        run_id=run_id,
    )


def build_document_intelligence_from_intermediate(
    *,
    intermediate: dict[str, Any],
    source_document: SourceDocument,
    city_key: str,
    run_id: str,
) -> dict[str, Any]:
    blocks: list[DocumentBlock] = []
    spans: list[SourceSpan] = []
    ingest_backend = str(intermediate.get("ingest_backend") or "unknown")
    for page in intermediate.get("pages") or []:
        page_number = int(page.get("page_number") or 0)
        page_text = str(page.get("text") or "")
        page_block_id = _stable_id("block", source_document.source_id, page_number, "page")
        if page_text:
            block = DocumentBlock(
                block_id=page_block_id,
                source_id=source_document.source_id,
                city=source_document.city,
                page=page_number,
                block_type="page_text",
                section_id=_section_guess(page_text),
                heading="",
                text=page_text,
                metadata={"ingest_backend": ingest_backend, "city_key": city_key},
            )
            blocks.append(block)
            spans.append(_span_for_block(block, source_document=source_document, kind="page_text"))

        for block_index, raw_block in enumerate(page.get("blocks") or [], start=1):
            text = str(raw_block.get("text") or "").strip()
            if not text:
                continue
            kind = str(raw_block.get("kind") or "paragraph")
            block = DocumentBlock(
                block_id=_stable_id("block", source_document.source_id, page_number, kind, block_index, text[:80]),
                source_id=source_document.source_id,
                city=source_document.city,
                page=page_number,
                block_type=kind,
                section_id=_section_guess(text),
                heading=text if kind == "heading" else "",
                text=text,
                parent_block_id=page_block_id,
                metadata={"ingest_backend": ingest_backend, "city_key": city_key},
            )
            blocks.append(block)
            spans.append(_span_for_block(block, source_document=source_document, kind=kind))

        for table_index, table in enumerate(page.get("tables") or [], start=1):
            rows = table.get("rows") or []
            text = _table_text(rows)
            if not text:
                continue
            title = str(table.get("title_guess") or "")
            block = DocumentBlock(
                block_id=_stable_id("block", source_document.source_id, page_number, "table", table_index, text[:80]),
                source_id=source_document.source_id,
                city=source_document.city,
                page=page_number,
                block_type="table",
                section_id=_section_guess(title or text),
                heading=title,
                text=text,
                parent_block_id=page_block_id,
                metadata={
                    "ingest_backend": ingest_backend,
                    "city_key": city_key,
                    "table_index": table_index,
                    "row_count": len(rows),
                    "column_count": max((len(row) for row in rows), default=0),
                },
            )
            blocks.append(block)
            spans.append(_span_for_block(block, source_document=source_document, kind="table"))

    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "document_intelligence",
        "city_key": city_key,
        "city": source_document.city,
        "run_id": run_id,
        "source_id": source_document.source_id,
        "source_sha256": source_document.sha256,
        "ingest_backend": ingest_backend,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "document_blocks": [block.to_dict() for block in blocks],
        "source_spans": [span.to_dict() for span in spans],
        "summary": {
            "page_count": len(intermediate.get("pages") or []),
            "document_block_count": len(blocks),
            "source_span_count": len(spans),
            "table_block_count": sum(1 for block in blocks if block.block_type == "table"),
            "heading_block_count": sum(1 for block in blocks if block.block_type == "heading"),
        },
    }


def write_document_intelligence(payload: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    blocks_path = output_dir / "document_blocks.json"
    spans_path = output_dir / "source_spans.json"
    report_path = output_dir / "document_intelligence_report.json"
    blocks_path.write_text(
        json.dumps(payload["document_blocks"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    spans_path.write_text(
        json.dumps(payload["source_spans"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = {key: value for key, value in payload.items() if key not in {"document_blocks", "source_spans"}}
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "document_blocks": blocks_path,
        "source_spans": spans_path,
        "document_intelligence_report": report_path,
    }


def _ingest_pdf(pdf_path: Path, *, prefer_docling: bool, page_ranges: list[tuple[int, int]] | None = None) -> dict[str, Any]:
    try:
        from burnaby_prototype.extraction.pdf_ingest import ingest_pdf  # noqa: PLC0415

        return ingest_pdf(pdf_path, prefer_docling=prefer_docling, log=lambda _message: None)
    except Exception:
        return _ingest_with_pypdf(pdf_path, page_ranges=page_ranges)


def _ingest_with_pypdf(pdf_path: Path, *, page_ranges: list[tuple[int, int]] | None = None) -> dict[str, Any]:
    from pypdf import PdfReader  # noqa: PLC0415

    reader = PdfReader(str(pdf_path))
    pages: list[dict[str, Any]] = []
    selected_pages = set(_page_numbers(page_ranges)) if page_ranges else None
    for index, page in enumerate(reader.pages, start=1):
        if selected_pages is not None and index not in selected_pages:
            continue
        text = page.extract_text() or ""
        blocks = [{"text": line.strip(), "kind": "paragraph"} for line in text.splitlines() if line.strip()]
        pages.append({"page_number": index, "text": text, "blocks": blocks, "tables": []})
    return {"source_pdf": str(pdf_path), "ingest_backend": "pypdf", "pages": pages}


def _page_numbers(page_ranges: list[tuple[int, int]]) -> list[int]:
    numbers: list[int] = []
    for start, end in page_ranges:
        numbers.extend(range(start, end + 1))
    return numbers


def _restrict_intermediate_to_pages(intermediate: dict[str, Any], page_ranges: list[tuple[int, int]] | None) -> dict[str, Any]:
    if not page_ranges:
        return intermediate
    return {
        **intermediate,
        "pages": [
            page
            for page in intermediate.get("pages") or []
            if any(start <= int(page.get("page_number") or 0) <= end for start, end in page_ranges)
        ],
    }


def _page_ranges(scoped_pages: list[Any]) -> list[tuple[int, int]] | None:
    if not scoped_pages:
        return None
    if len(scoped_pages) == 2 and all(isinstance(item, int) for item in scoped_pages):
        return [(int(scoped_pages[0]), int(scoped_pages[1]))]
    ranges: list[tuple[int, int]] = []
    for item in scoped_pages:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            ranges.append((int(item[0]), int(item[1])))
    return ranges or None


def _span_for_block(block: DocumentBlock, *, source_document: SourceDocument, kind: str) -> SourceSpan:
    return SourceSpan(
        span_id=_stable_id("span", block.block_id, kind),
        source_id=source_document.source_id,
        block_id=block.block_id,
        city=block.city,
        page=block.page,
        section_id=block.section_id,
        block_type=block.block_type,
        char_start=0,
        char_end=len(block.text),
        text=block.text,
        metadata={**block.metadata, "source_sha256": source_document.sha256},
    )


def _table_text(rows: list[list[Any]]) -> str:
    return "\n".join(" | ".join(str(cell or "").strip() for cell in row) for row in rows if any(row))


def _section_guess(text: str) -> str:
    import re

    match = re.search(r"\b\d{1,4}(?:\.\d{1,4})+\b", text or "")
    return match.group(0) if match else ""


def _stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha1("||".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"
