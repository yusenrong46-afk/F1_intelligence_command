"""Cross-reference extraction and lookup for M8.5 dependencies."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .dependency_types import normalized_lookup_key, normalize_reference


_SECTION_RE = re.compile(r"\b(?:section|sec\.?|s\.|§)\s*(?P<section>\d+(?:\.\d+)*)\b", re.IGNORECASE)


@dataclass(frozen=True)
class CrossReferenceTarget:
    reference: str
    evidence_ids: tuple[str, ...] = ()
    text: str = ""
    status: str = "available"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference": self.reference,
            "evidence_ids": list(self.evidence_ids),
            "text": self.text,
            "status": self.status,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CrossReferenceTarget":
        data = dict(payload or {})
        return cls(
            reference=str(data.get("reference") or ""),
            evidence_ids=tuple(str(item) for item in data.get("evidence_ids", [])),
            text=str(data.get("text") or ""),
            status=str(data.get("status") or "available"),
            metadata=dict(data.get("metadata") or {}),
        )


class CrossReferenceIndex:
    def __init__(self, targets: list[CrossReferenceTarget] | None = None) -> None:
        self._targets: dict[str, CrossReferenceTarget] = {}
        for target in targets or []:
            self._targets[normalized_lookup_key(target.reference)] = target

    def add(self, reference: str, *, evidence_id: str, text: str, status: str = "available") -> None:
        normalized = normalize_reference(reference)
        self._targets[normalized_lookup_key(normalized)] = CrossReferenceTarget(
            reference=normalized,
            evidence_ids=(evidence_id,),
            text=text,
            status=status,
        )

    def lookup(self, reference: str) -> CrossReferenceTarget | None:
        return self._targets.get(normalized_lookup_key(reference))

    def extract(self, text: str) -> list[str]:
        refs = []
        seen = set()
        for match in _SECTION_RE.finditer(str(text or "")):
            reference = f"Section {match.group('section')}"
            key = normalized_lookup_key(reference)
            if key not in seen:
                seen.add(key)
                refs.append(reference)
        return refs

    def to_dict(self) -> dict[str, Any]:
        return {"targets": [target.to_dict() for target in self._targets.values()]}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CrossReferenceIndex":
        return cls([CrossReferenceTarget.from_dict(row) for row in (payload or {}).get("targets", [])])

