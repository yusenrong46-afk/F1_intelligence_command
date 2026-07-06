"""Map table lineage cells into candidate-only rule claims."""

from __future__ import annotations

from .table_block import TableBlock
from .table_lineage import TableDerivedRule
from .table_parser import build_table_cell_lineage


_MIN_RULE_TYPES = {
    "setback",
    "building_separation",
    "lot_area",
    "fire_access_corridor",
    "automatic_sprinkler",
}
_MAX_RULE_TYPES = {
    "height",
    "storeys",
    "lot_coverage",
    "impervious_surface",
    "dwelling_units",
}


def map_table_derived_rules(block: TableBlock) -> list[TableDerivedRule]:
    rules: list[TableDerivedRule] = []
    for lineage in build_table_cell_lineage(block):
        if not lineage.inferred_rule_type or not lineage.normalized_value:
            continue
        subject = infer_subject(lineage.column_label, lineage.inferred_rule_type)
        rules.append(
            TableDerivedRule(
                city=lineage.city,
                zone=lineage.zone,
                rule_type=lineage.inferred_rule_type,
                subject=subject,
                comparator=comparator_for_rule_type(lineage.inferred_rule_type),
                normalized_value=lineage.normalized_value,
                normalized_unit=lineage.normalized_unit,
                lineage=lineage,
                confidence=lineage.confidence,
                parse_warnings=lineage.parse_warnings,
                metadata={"source": "m8_5_table_rule_mapper"},
            )
        )
    return rules


def comparator_for_rule_type(rule_type: str) -> str:
    if rule_type in _MIN_RULE_TYPES:
        return ">="
    if rule_type in _MAX_RULE_TYPES:
        return "<="
    return ""


def infer_subject(column_label: str, rule_type: str) -> str:
    text = " ".join(str(column_label or "").lower().split())
    if rule_type == "setback":
        if "front" in text:
            return "front"
        if "rear" in text:
            return "rear"
        if "side" in text:
            if "interior" in text:
                return "interior side"
            if "exterior" in text:
                return "exterior side"
            return "side"
        if "yard" in text:
            return text.replace("setback", "").strip() or "setback"
        return "setback"
    if rule_type == "building_separation":
        return "building separation"
    if rule_type == "height":
        return "height"
    if rule_type == "storeys":
        return "storeys"
    if rule_type == "lot_area":
        return "lot area"
    if rule_type == "lot_coverage":
        return "lot coverage"
    if rule_type == "impervious_surface":
        return "impervious surface"
    if rule_type == "dwelling_units":
        return "dwelling units"
    if rule_type == "automatic_sprinkler":
        return "automatic sprinkler"
    if rule_type == "fire_access_corridor":
        return "fire access corridor"
    return rule_type

