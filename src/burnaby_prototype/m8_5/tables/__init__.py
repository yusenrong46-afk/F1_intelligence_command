"""Table-aware lineage and candidate mapping for M8.5."""

from .table_block import TableBlock, TableCell, TableParseDiagnostic
from .table_lineage import TableCellLineage, TableDerivedRule
from .table_parser import build_table_cell_lineage, parse_table_block
from .table_rule_mapper import map_table_derived_rules

__all__ = [
    "TableBlock",
    "TableCell",
    "TableCellLineage",
    "TableDerivedRule",
    "TableParseDiagnostic",
    "build_table_cell_lineage",
    "map_table_derived_rules",
    "parse_table_block",
]

