"""Definition dependency linker for M8.5."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .dependency_types import normalized_lookup_key


@dataclass(frozen=True)
class DefinitionRecord:
    term: str
    evidence_ids: tuple[str, ...] = ()
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"term": self.term, "evidence_ids": list(self.evidence_ids), "text": self.text}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DefinitionRecord":
        data = dict(payload or {})
        return cls(
            term=str(data.get("term") or ""),
            evidence_ids=tuple(str(item) for item in data.get("evidence_ids", [])),
            text=str(data.get("text") or ""),
        )


class DefinitionLinker:
    def __init__(self, definitions: dict[str, tuple[str, str] | DefinitionRecord] | None = None) -> None:
        self._definitions: dict[str, DefinitionRecord] = {}
        for term, value in (definitions or {}).items():
            if isinstance(value, DefinitionRecord):
                record = value
            else:
                evidence_id, text = value
                record = DefinitionRecord(term=term, evidence_ids=(evidence_id,), text=text)
            self._definitions[normalized_lookup_key(term)] = record

    def find_terms(self, text: str) -> list[str]:
        lower = str(text or "").lower()
        return [record.term for key, record in sorted(self._definitions.items()) if key in lower]

    def lookup(self, term: str) -> DefinitionRecord | None:
        return self._definitions.get(normalized_lookup_key(term))

    def to_dict(self) -> dict[str, Any]:
        return {"definitions": [record.to_dict() for record in self._definitions.values()]}

