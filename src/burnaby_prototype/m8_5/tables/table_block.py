"""M8.5 table block contracts.

These contracts preserve raw table geometry and diagnostics. They are not a
verification path; table-derived claims must still go through the verifier.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any


def stable_id(*parts: Any, length: int = 16) -> str:
    text = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return {item.name: _serialize(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class TableParseDiagnostic:
    code: str
    message: str
    severity: str = "review"
    row_index: int | None = None
    column_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("diagnostic code is required")
        if self.severity not in {"info", "review", "error"}:
            raise ValueError(f"unknown diagnostic severity: {self.severity}")

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TableParseDiagnostic":
        data = dict(payload or {})
        return cls(
            code=str(data.get("code") or ""),
            message=str(data.get("message") or ""),
            severity=str(data.get("severity") or "review"),
            row_index=data.get("row_index"),
            column_index=data.get("column_index"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class TableCell:
    city: str
    zone: str
    document_id: str
    page: int | None
    section_id: str
    table_id: str
    row_index: int
    column_index: int
    text: str
    row_label: str = ""
    column_label: str = ""
    is_header: bool = False
    row_span: int = 1
    column_span: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.row_index < 0 or self.column_index < 0:
            raise ValueError("table cell indices must be non-negative")
        if self.row_span < 1 or self.column_span < 1:
            raise ValueError("table cell spans must be positive")

    @property
    def cell_id(self) -> str:
        return "cell_" + stable_id(
            self.city,
            self.document_id,
            self.page,
            self.section_id,
            self.table_id,
            self.row_index,
            self.column_index,
            self.text,
        )

    def to_dict(self) -> dict[str, Any]:
        data = _serialize(self)
        data["cell_id"] = self.cell_id
        return data

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TableCell":
        data = dict(payload or {})
        data.pop("cell_id", None)
        return cls(
            city=str(data.get("city") or ""),
            zone=str(data.get("zone") or ""),
            document_id=str(data.get("document_id") or ""),
            page=data.get("page"),
            section_id=str(data.get("section_id") or ""),
            table_id=str(data.get("table_id") or ""),
            row_index=int(data.get("row_index") or 0),
            column_index=int(data.get("column_index") or 0),
            text=str(data.get("text") or ""),
            row_label=str(data.get("row_label") or ""),
            column_label=str(data.get("column_label") or ""),
            is_header=bool(data.get("is_header")),
            row_span=int(data.get("row_span") or 1),
            column_span=int(data.get("column_span") or 1),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class TableBlock:
    city: str
    zone: str
    document_id: str
    page: int | None
    section_id: str
    table_id: str
    headers: tuple[str, ...]
    cells: tuple[TableCell, ...] = ()
    diagnostics: tuple[TableParseDiagnostic, ...] = ()
    title: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.table_id:
            raise ValueError("table_id is required")
        if not self.headers:
            raise ValueError("table headers are required")

    def body_cells(self) -> tuple[TableCell, ...]:
        return tuple(cell for cell in self.cells if not cell.is_header)

    def diagnostics_for_cell(self, cell: TableCell) -> tuple[TableParseDiagnostic, ...]:
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.row_index in {None, cell.row_index}
            and diagnostic.column_index in {None, cell.column_index}
        )

    def to_dict(self) -> dict[str, Any]:
        data = _serialize(self)
        data["block_id"] = self.block_id
        return data

    @property
    def block_id(self) -> str:
        return "table_" + stable_id(self.city, self.document_id, self.page, self.section_id, self.table_id)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TableBlock":
        data = dict(payload or {})
        data.pop("block_id", None)
        return cls(
            city=str(data.get("city") or ""),
            zone=str(data.get("zone") or ""),
            document_id=str(data.get("document_id") or ""),
            page=data.get("page"),
            section_id=str(data.get("section_id") or ""),
            table_id=str(data.get("table_id") or ""),
            headers=tuple(str(item) for item in data.get("headers", [])),
            cells=tuple(TableCell.from_dict(row) for row in data.get("cells", [])),
            diagnostics=tuple(TableParseDiagnostic.from_dict(row) for row in data.get("diagnostics", [])),
            title=str(data.get("title") or ""),
            metadata=dict(data.get("metadata") or {}),
        )

