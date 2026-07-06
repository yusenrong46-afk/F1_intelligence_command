"""M8.5 table lineage contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from burnaby_prototype.m8.extraction.rule_schema import SourceSpan

from .table_block import stable_id


def _source_span_from_dict(payload: dict[str, Any] | None) -> SourceSpan | None:
    if not isinstance(payload, dict):
        return None
    return SourceSpan.from_dict(payload)


@dataclass(frozen=True)
class TableCellLineage:
    city: str
    zone: str
    document_id: str
    page: int | None
    section_id: str
    table_id: str
    row_index: int
    column_index: int
    row_label: str
    column_label: str
    cell_text: str
    normalized_value: str = ""
    normalized_unit: str = ""
    inferred_rule_type: str = ""
    confidence: float = 0.0
    parse_warnings: tuple[str, ...] = ()
    source_span: SourceSpan | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def lineage_id(self) -> str:
        return "lineage_" + stable_id(
            self.city,
            self.document_id,
            self.page,
            self.section_id,
            self.table_id,
            self.row_index,
            self.column_index,
            self.row_label,
            self.column_label,
            self.cell_text,
        )

    @property
    def verifier_ready(self) -> bool:
        return bool(
            self.row_label.strip()
            and self.column_label.strip()
            and self.normalized_value
            and self.inferred_rule_type
            and self.source_span is not None
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "lineage_id": self.lineage_id,
            "city": self.city,
            "zone": self.zone,
            "document_id": self.document_id,
            "page": self.page,
            "section_id": self.section_id,
            "table_id": self.table_id,
            "row_index": self.row_index,
            "column_index": self.column_index,
            "row_label": self.row_label,
            "column_label": self.column_label,
            "cell_text": self.cell_text,
            "normalized_value": self.normalized_value,
            "normalized_unit": self.normalized_unit,
            "inferred_rule_type": self.inferred_rule_type,
            "confidence": self.confidence,
            "parse_warnings": list(self.parse_warnings),
            "source_span": self.source_span.to_dict() if self.source_span else None,
            "metadata": dict(self.metadata),
            "verifier_ready": self.verifier_ready,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TableCellLineage":
        data = dict(payload or {})
        data.pop("lineage_id", None)
        data.pop("verifier_ready", None)
        return cls(
            city=str(data.get("city") or ""),
            zone=str(data.get("zone") or ""),
            document_id=str(data.get("document_id") or ""),
            page=data.get("page"),
            section_id=str(data.get("section_id") or ""),
            table_id=str(data.get("table_id") or ""),
            row_index=int(data.get("row_index") or 0),
            column_index=int(data.get("column_index") or 0),
            row_label=str(data.get("row_label") or ""),
            column_label=str(data.get("column_label") or ""),
            cell_text=str(data.get("cell_text") or ""),
            normalized_value=str(data.get("normalized_value") or ""),
            normalized_unit=str(data.get("normalized_unit") or ""),
            inferred_rule_type=str(data.get("inferred_rule_type") or ""),
            confidence=float(data.get("confidence") or 0.0),
            parse_warnings=tuple(str(item) for item in data.get("parse_warnings", [])),
            source_span=_source_span_from_dict(data.get("source_span")),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class TableDerivedRule:
    city: str
    zone: str
    rule_type: str
    subject: str
    comparator: str
    normalized_value: str
    normalized_unit: str
    lineage: TableCellLineage
    status: str = "candidate_only"
    confidence: float = 0.0
    parse_warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status != "candidate_only":
            raise ValueError("table-derived rules are candidate-only until the verifier runs")

    @property
    def rule_id(self) -> str:
        return "table_rule_" + stable_id(self.city, self.zone, self.rule_type, self.subject, self.lineage.lineage_id)

    @property
    def source_span(self) -> SourceSpan | None:
        return self.lineage.source_span

    @property
    def row_label(self) -> str:
        return self.lineage.row_label

    @property
    def column_label(self) -> str:
        return self.lineage.column_label

    @property
    def verifier_ready(self) -> bool:
        return self.lineage.verifier_ready and not self._has_context_blocker()

    def _has_context_blocker(self) -> bool:
        blockers = {"missing_row_label", "missing_column_label", "missing_value", "unknown_rule_type"}
        return any(warning in blockers for warning in self.parse_warnings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "city": self.city,
            "zone": self.zone,
            "rule_type": self.rule_type,
            "subject": self.subject,
            "comparator": self.comparator,
            "normalized_value": self.normalized_value,
            "normalized_unit": self.normalized_unit,
            "status": self.status,
            "confidence": self.confidence,
            "parse_warnings": list(self.parse_warnings),
            "lineage": self.lineage.to_dict(),
            "source_span": self.source_span.to_dict() if self.source_span else None,
            "metadata": dict(self.metadata),
            "verifier_ready": self.verifier_ready,
        }

    def to_verifier_candidate(self) -> dict[str, Any]:
        return {
            "candidate_id": self.rule_id,
            "rule_object": self.rule_type,
            "constraint_type": "development_regulation",
            "constraint_scope": self.subject,
            "applies_to": self.row_label,
            "operator": self.comparator,
            "value": self.normalized_value,
            "unit": self.normalized_unit,
            "evidence_id": (self.source_span.metadata.get("evidence_id") if self.source_span else "") or self.lineage.lineage_id,
            "verification_decision": "review_needed",
            "review_reason": "M8.5 table-derived candidate requires deterministic verifier review",
            "table_lineage": self.lineage.to_dict(),
            "support_gaps": [] if self.verifier_ready else list(self.parse_warnings),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TableDerivedRule":
        data = dict(payload or {})
        return cls(
            city=str(data.get("city") or ""),
            zone=str(data.get("zone") or ""),
            rule_type=str(data.get("rule_type") or ""),
            subject=str(data.get("subject") or ""),
            comparator=str(data.get("comparator") or ""),
            normalized_value=str(data.get("normalized_value") or ""),
            normalized_unit=str(data.get("normalized_unit") or ""),
            lineage=TableCellLineage.from_dict(data.get("lineage") or {}),
            status=str(data.get("status") or "candidate_only"),
            confidence=float(data.get("confidence") or 0.0),
            parse_warnings=tuple(str(item) for item in data.get("parse_warnings", [])),
            metadata=dict(data.get("metadata") or {}),
        )

