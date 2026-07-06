from __future__ import annotations

from burnaby_prototype.m8_5.tables.table_parser import parse_table_block
from burnaby_prototype.m8_5.tables.table_rule_mapper import map_table_derived_rules


def test_table_mapper_creates_separate_rule_candidates_for_each_rule_column() -> None:
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

    rules = map_table_derived_rules(block)

    assert [(rule.rule_type, rule.subject, rule.comparator, rule.normalized_value, rule.normalized_unit) for rule in rules] == [
        ("setback", "front", ">=", "7.5", "m"),
        ("setback", "rear", ">=", "9.0", "m"),
        ("height", "height", "<=", "10.7", "m"),
    ]
    assert all(rule.row_label == "R1" for rule in rules)
    assert all(rule.status == "candidate_only" for rule in rules)
    assert all(rule.verifier_ready for rule in rules)


def test_wrong_column_does_not_map_to_wrong_rule_type() -> None:
    block = parse_table_block(
        city="burnaby_r1",
        zone="R1",
        document_id="R1.pdf",
        page=2,
        section_id="101.4",
        table_id="table_mixed",
        rows=[
            ["Zone", "Owner note", "Height"],
            ["R1", "7.5 m", "10.7 m"],
        ],
    )

    rules = map_table_derived_rules(block)

    assert len(rules) == 1
    assert rules[0].rule_type == "height"
    assert rules[0].normalized_value == "10.7"
    assert rules[0].column_label == "Height"


def test_table_derived_rules_preserve_source_lineage_and_span() -> None:
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

    rule = map_table_derived_rules(block)[0]

    assert rule.lineage.table_id == "table_101_4"
    assert rule.lineage.row_index == 1
    assert rule.lineage.column_index == 1
    assert rule.lineage.row_label == "R1"
    assert rule.lineage.column_label == "Height"
    assert rule.source_span is not None
    assert rule.source_span.text == "10.7 m"
    assert rule.to_verifier_candidate()["verification_decision"] == "review_needed"
    assert rule.to_verifier_candidate()["table_lineage"]["lineage_id"] == rule.lineage.lineage_id


def test_table_rule_without_row_context_is_not_verifier_ready() -> None:
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

    rule = map_table_derived_rules(block)[0]

    assert rule.verifier_ready is False
    assert "missing_row_label" in rule.parse_warnings
    assert rule.to_verifier_candidate()["verification_decision"] == "review_needed"
