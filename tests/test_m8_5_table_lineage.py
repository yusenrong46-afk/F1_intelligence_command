from __future__ import annotations

from burnaby_prototype.m8_5.tables.table_lineage import TableCellLineage
from burnaby_prototype.m8_5.tables.table_parser import (
    build_table_cell_lineage,
    parse_table_block,
)


def test_table_lineage_preserves_row_and_column_labels() -> None:
    block = parse_table_block(
        city="burnaby_r1",
        zone="R1",
        document_id="R1.pdf",
        page=2,
        section_id="101.4",
        table_id="table_101_4",
        rows=[
            ["Zone", "Front setback", "Rear setback", "Height"],
            ["R1", "7.5 m", "9.0 m", "10.7 m"],
        ],
    )

    lineage = build_table_cell_lineage(block)
    front = next(item for item in lineage if item.column_label == "Front setback")
    rear = next(item for item in lineage if item.column_label == "Rear setback")

    assert front.row_label == "R1"
    assert front.column_label == "Front setback"
    assert front.cell_text == "7.5 m"
    assert rear.row_label == "R1"
    assert rear.column_label == "Rear setback"
    assert rear.cell_text == "9.0 m"


def test_blank_and_ragged_rows_produce_review_diagnostics() -> None:
    block = parse_table_block(
        city="burnaby_r1",
        zone="R1",
        document_id="R1.pdf",
        page=2,
        section_id="101.4",
        table_id="table_bad",
        rows=[
            ["Zone", "Front setback", "Rear setback"],
            ["", "7.5 m", "9.0 m"],
            ["R1", "7.5 m"],
            ["R2", "", "8.0 m"],
        ],
    )

    codes = {diagnostic.code for diagnostic in block.diagnostics}

    assert "missing_row_label" in codes
    assert "ragged_or_merged_row" in codes
    assert "blank_body_cell" in codes
    assert all(diagnostic.severity == "review" for diagnostic in block.diagnostics)


def test_table_lineage_serializes_to_json() -> None:
    block = parse_table_block(
        city="burnaby_r1",
        zone="R1",
        document_id="R1.pdf",
        page=2,
        section_id="101.4",
        table_id="table_101_4",
        rows=[
            ["Zone", "Height"],
            ["R1", "10.7 m"],
        ],
    )
    lineage = build_table_cell_lineage(block)[0]

    round_tripped = TableCellLineage.from_dict(lineage.to_dict())

    assert round_tripped == lineage
    assert round_tripped.source_span is not None
    assert round_tripped.source_span.text == "10.7 m"
    assert round_tripped.lineage_id == lineage.lineage_id


def test_value_without_row_context_is_not_verifier_ready() -> None:
    block = parse_table_block(
        city="burnaby_r1",
        zone="R1",
        document_id="R1.pdf",
        page=2,
        section_id="101.4",
        table_id="table_missing_context",
        rows=[
            ["Zone", "Height"],
            ["", "10.7 m"],
        ],
    )

    lineage = build_table_cell_lineage(block)[0]

    assert lineage.row_label == ""
    assert lineage.normalized_value == "10.7"
    assert lineage.verifier_ready is False
    assert "missing_row_label" in lineage.parse_warnings


def test_table_lineage_preserves_source_span_identity() -> None:
    block = parse_table_block(
        city="burnaby_r1",
        zone="R1",
        document_id="R1.pdf",
        page=2,
        section_id="101.4",
        table_id="table_101_4",
        rows=[
            ["Zone", "Height"],
            ["R1", "10.7 m"],
        ],
    )

    lineage = build_table_cell_lineage(block)[0]

    assert lineage.source_span is not None
    assert lineage.source_span.document_id == "R1.pdf"
    assert lineage.source_span.page == 2
    assert lineage.source_span.section_id == "101.4"
    assert lineage.source_span.metadata["table_id"] == "table_101_4"
    assert lineage.source_span.metadata["row_label"] == "R1"
    assert lineage.source_span.metadata["column_label"] == "Height"
