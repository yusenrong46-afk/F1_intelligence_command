"""Small deterministic table parser for M8.5 lineage contracts."""

from __future__ import annotations

import re
from typing import Sequence

from burnaby_prototype.m8.extraction.rule_schema import SourceSpan

from .table_block import TableBlock, TableCell, TableParseDiagnostic
from .table_confidence import lineage_confidence
from .table_lineage import TableCellLineage


_VALUE_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>m2|m²|m|%|storeys?|units?)?", re.IGNORECASE)


def parse_table_block(
    *,
    city: str,
    zone: str,
    document_id: str,
    page: int | None,
    section_id: str,
    table_id: str,
    rows: Sequence[Sequence[object]],
    title: str = "",
) -> TableBlock:
    if not rows:
        raise ValueError("rows are required")
    headers = tuple(_clean_text(item) for item in rows[0])
    if not headers:
        raise ValueError("header row is required")

    diagnostics: list[TableParseDiagnostic] = []
    cells: list[TableCell] = []
    for column_index, header in enumerate(headers):
        if not header:
            diagnostics.append(
                TableParseDiagnostic(
                    code="blank_header_cell",
                    message="Header cell is blank; column context is ambiguous.",
                    row_index=0,
                    column_index=column_index,
                )
            )
        cells.append(
            TableCell(
                city=city,
                zone=zone,
                document_id=document_id,
                page=page,
                section_id=section_id,
                table_id=table_id,
                row_index=0,
                column_index=column_index,
                text=header,
                row_label="",
                column_label=header,
                is_header=True,
            )
        )

    for row_index, row in enumerate(rows[1:], start=1):
        clean_row = [_clean_text(item) for item in row]
        if len(clean_row) != len(headers):
            diagnostics.append(
                TableParseDiagnostic(
                    code="ragged_or_merged_row",
                    message="Row length does not match header length; this may be a merged-cell or extraction issue.",
                    row_index=row_index,
                    metadata={"expected_columns": len(headers), "actual_columns": len(clean_row)},
                )
            )
        padded = [*clean_row, *([""] * max(0, len(headers) - len(clean_row)))]
        row_label = padded[0] if padded else ""
        if not row_label:
            diagnostics.append(
                TableParseDiagnostic(
                    code="missing_row_label",
                    message="Body row is missing row label; rule scope cannot be trusted.",
                    row_index=row_index,
                    column_index=0,
                )
            )
        for column_index, header in enumerate(headers):
            text = padded[column_index] if column_index < len(padded) else ""
            if column_index > 0 and not text:
                diagnostics.append(
                    TableParseDiagnostic(
                        code="blank_body_cell",
                        message="Body cell is blank; candidate needs review.",
                        row_index=row_index,
                        column_index=column_index,
                    )
                )
            cells.append(
                TableCell(
                    city=city,
                    zone=zone,
                    document_id=document_id,
                    page=page,
                    section_id=section_id,
                    table_id=table_id,
                    row_index=row_index,
                    column_index=column_index,
                    text=text,
                    row_label=row_label,
                    column_label=header,
                    is_header=False,
                )
            )

    return TableBlock(
        city=city,
        zone=zone,
        document_id=document_id,
        page=page,
        section_id=section_id,
        table_id=table_id,
        headers=headers,
        cells=tuple(cells),
        diagnostics=tuple(diagnostics),
        title=title,
    )


def build_table_cell_lineage(block: TableBlock) -> list[TableCellLineage]:
    lineage: list[TableCellLineage] = []
    for cell in block.body_cells():
        if cell.column_index == 0:
            continue
        value, unit = normalize_cell_value(cell.text)
        rule_type = infer_rule_type(cell.column_label)
        warnings = list(_warning_codes_for_cell(block, cell))
        if not cell.row_label:
            warnings.append("missing_row_label")
        if not cell.column_label:
            warnings.append("missing_column_label")
        if not value:
            warnings.append("missing_value")
        if not rule_type:
            warnings.append("unknown_rule_type")
        source_span = _source_span_for_cell(cell)
        lineage.append(
            TableCellLineage(
                city=cell.city,
                zone=cell.zone,
                document_id=cell.document_id,
                page=cell.page,
                section_id=cell.section_id,
                table_id=cell.table_id,
                row_index=cell.row_index,
                column_index=cell.column_index,
                row_label=cell.row_label,
                column_label=cell.column_label,
                cell_text=cell.text,
                normalized_value=value,
                normalized_unit=unit,
                inferred_rule_type=rule_type,
                confidence=lineage_confidence(
                    has_row_label=bool(cell.row_label),
                    has_column_label=bool(cell.column_label),
                    has_value=bool(value),
                    warning_count=len(set(warnings)),
                ),
                parse_warnings=tuple(sorted(set(warnings))),
                source_span=source_span,
                metadata={"cell_id": cell.cell_id},
            )
        )
    return lineage


def normalize_cell_value(text: str) -> tuple[str, str]:
    match = _VALUE_RE.search(str(text or ""))
    if not match:
        return "", ""
    value = match.group("value")
    unit = (match.group("unit") or "").lower().replace("m²", "m2")
    if unit.startswith("storey"):
        unit = "storeys"
    if unit.startswith("unit"):
        unit = "units"
    return value, unit


def infer_rule_type(column_label: str) -> str:
    text = _norm(column_label)
    if "setback" in text or "yard" in text:
        return "setback"
    if "separation" in text:
        return "building_separation"
    if "height" in text:
        return "height"
    if "storey" in text or "storeys" in text or "stories" in text:
        return "storeys"
    if "lot area" in text or "site area" in text or "parcel area" in text:
        return "lot_area"
    if "lot coverage" in text or "coverage" in text:
        return "lot_coverage"
    if "impervious" in text:
        return "impervious_surface"
    if "dwelling" in text or "unit" in text:
        return "dwelling_units"
    if "sprinkler" in text:
        return "automatic_sprinkler"
    if "fire access" in text or "access corridor" in text:
        return "fire_access_corridor"
    return ""


def _warning_codes_for_cell(block: TableBlock, cell: TableCell) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in block.diagnostics_for_cell(cell))


def _source_span_for_cell(cell: TableCell) -> SourceSpan:
    text = cell.text or "[blank table cell]"
    return SourceSpan(
        city=cell.city,
        document_id=cell.document_id,
        page=cell.page,
        section_id=cell.section_id,
        block_type="table_cell",
        char_start=0,
        char_end=len(text),
        text=text,
        metadata={
            "table_id": cell.table_id,
            "row_index": cell.row_index,
            "column_index": cell.column_index,
            "row_label": cell.row_label,
            "column_label": cell.column_label,
            "cell_id": cell.cell_id,
        },
    )


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def _norm(value: str) -> str:
    return _clean_text(value).lower()
