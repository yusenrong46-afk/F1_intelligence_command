"""Typed M8 contracts.

The defaults are deliberately fail-closed: a rule with no evidence starts in
``review_needed`` and attempting to mark an unsupported rule as verified raises
``ValueError``. These classes are pure data contracts; they do not verify law.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any


M8_STATUSES = frozenset({
    "verified",
    "repaired_successfully",
    "context_required",
    "review_needed",
    "rejected",
    "not_used",
})
PROMOTED_STATUSES = frozenset({"verified", "repaired_successfully"})
REPAIR_CATEGORIES = frozenset({
    "missing_evidence",
    "weak_evidence",
    "unit_mismatch",
    "missing_scope",
    "missing_condition",
    "missing_exception",
    "conflicting_evidence",
    "unresolved_cross_reference",
    "unsupported_rule_type",
    "general_review",
})


def stable_id(*parts: Any, length: int = 16) -> str:
    text = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _clean_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {str(k): v for k, v in dict(value or {}).items() if v is not None}


def _dataclass_dict(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return {
            item.name: _serialize(getattr(value, item.name))
            for item in fields(value)
        }
    return asdict(value)


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return _dataclass_dict(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class SourceSpan:
    city: str
    document_id: str
    page: int | None
    section_id: str = ""
    block_type: str = "text"
    char_start: int = 0
    char_end: int = 0
    text: str = ""
    source_url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.char_start < 0 or self.char_end < 0:
            raise ValueError("source span offsets must be non-negative")
        if self.char_end and self.char_end < self.char_start:
            raise ValueError("source span char_end must be >= char_start")
        if self.page is not None and int(self.page) < 0:
            raise ValueError("source span page must be non-negative")
        if not str(self.text or "").strip():
            raise ValueError("source span text is required")

    @property
    def span_id(self) -> str:
        return "span_" + stable_id(
            self.city,
            self.document_id,
            self.page,
            self.section_id,
            self.block_type,
            self.char_start,
            self.char_end,
            self.text,
        )

    def to_dict(self) -> dict[str, Any]:
        data = _dataclass_dict(self)
        data["span_id"] = self.span_id
        return data

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SourceSpan":
        data = dict(payload or {})
        data.pop("span_id", None)
        return cls(
            city=str(data.get("city") or ""),
            document_id=str(data.get("document_id") or ""),
            page=data.get("page"),
            section_id=str(data.get("section_id") or ""),
            block_type=str(data.get("block_type") or "text"),
            char_start=int(data.get("char_start") or 0),
            char_end=int(data.get("char_end") or 0),
            text=str(data.get("text") or ""),
            source_url=str(data.get("source_url") or ""),
            metadata=_clean_dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class EvidencePointer:
    evidence_id: str
    span_id: str
    field_name: str
    quote: str = ""
    source_span: SourceSpan | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise ValueError("evidence pointer needs evidence_id")
        if not self.span_id:
            raise ValueError("evidence pointer needs span_id")
        if not self.field_name:
            raise ValueError("evidence pointer needs field_name")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("evidence pointer confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvidencePointer":
        data = dict(payload or {})
        span = data.get("source_span")
        return cls(
            evidence_id=str(data.get("evidence_id") or ""),
            span_id=str(data.get("span_id") or ""),
            field_name=str(data.get("field_name") or ""),
            quote=str(data.get("quote") or ""),
            source_span=SourceSpan.from_dict(span) if isinstance(span, dict) else None,
            confidence=float(data.get("confidence", 1.0)),
            metadata=_clean_dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class EvidenceBundle:
    bundle_id: str
    query: str
    spans: tuple[SourceSpan, ...] = ()
    pointers: tuple[EvidencePointer, ...] = ()
    ranking_signals: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.bundle_id:
            raise ValueError("bundle_id is required")
        if not self.query:
            raise ValueError("query is required")

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvidenceBundle":
        data = dict(payload or {})
        return cls(
            bundle_id=str(data.get("bundle_id") or ""),
            query=str(data.get("query") or ""),
            spans=tuple(SourceSpan.from_dict(row) for row in data.get("spans", [])),
            pointers=tuple(EvidencePointer.from_dict(row) for row in data.get("pointers", [])),
            ranking_signals=_clean_dict(data.get("ranking_signals") or {}),
            metadata=_clean_dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class RepairCritique:
    rule_id: str
    category: str
    reason: str
    fields: tuple[str, ...] = ()
    severity: str = "medium"
    support_gaps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.category not in REPAIR_CATEGORIES:
            raise ValueError(f"unknown repair category: {self.category}")

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RepairCritique":
        data = dict(payload or {})
        return cls(
            rule_id=str(data.get("rule_id") or ""),
            category=str(data.get("category") or "general_review"),
            reason=str(data.get("reason") or ""),
            fields=tuple(str(item) for item in data.get("fields", [])),
            severity=str(data.get("severity") or "medium"),
            support_gaps=tuple(str(item) for item in data.get("support_gaps", [])),
        )


@dataclass(frozen=True)
class RepairPatch:
    rule_id: str
    changes: dict[str, Any] = field(default_factory=dict)
    evidence_pointers: tuple[EvidencePointer, ...] = ()
    reason: str = ""
    category: str = "general_review"

    def __post_init__(self) -> None:
        if self.category not in REPAIR_CATEGORIES:
            raise ValueError(f"unknown repair category: {self.category}")

    @property
    def is_empty(self) -> bool:
        return not self.changes and not self.evidence_pointers

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RepairPatch":
        data = dict(payload or {})
        return cls(
            rule_id=str(data.get("rule_id") or ""),
            changes=_clean_dict(data.get("changes") or {}),
            evidence_pointers=tuple(EvidencePointer.from_dict(row) for row in data.get("evidence_pointers", [])),
            reason=str(data.get("reason") or ""),
            category=str(data.get("category") or "general_review"),
        )


@dataclass(frozen=True)
class RepairAttempt:
    attempt_index: int
    critique: RepairCritique
    query: str
    patch: RepairPatch | None = None
    decision_status: str = "review_needed"
    reason: str = ""
    evidence_bundle_id: str = ""

    def __post_init__(self) -> None:
        if self.attempt_index < 1:
            raise ValueError("attempt_index is 1-based")
        if self.decision_status not in M8_STATUSES:
            raise ValueError(f"unknown M8 status: {self.decision_status}")

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RepairAttempt":
        data = dict(payload or {})
        patch = data.get("patch")
        return cls(
            attempt_index=int(data.get("attempt_index") or 1),
            critique=RepairCritique.from_dict(data.get("critique") or {}),
            query=str(data.get("query") or ""),
            patch=RepairPatch.from_dict(patch) if isinstance(patch, dict) else None,
            decision_status=str(data.get("decision_status") or "review_needed"),
            reason=str(data.get("reason") or ""),
            evidence_bundle_id=str(data.get("evidence_bundle_id") or ""),
        )


@dataclass(frozen=True)
class VerificationDecision:
    rule_id: str
    status: str = "review_needed"
    reason: str = "not verified by M8"
    evidence_ids: tuple[str, ...] = ()
    unresolved_dependencies: tuple[str, ...] = ()
    support_gaps: tuple[str, ...] = ()
    repair_history: tuple[RepairAttempt, ...] = ()
    verifier: str = "m8_dependency_wrapper"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in M8_STATUSES:
            raise ValueError(f"unknown M8 status: {self.status}")
        if self.status in PROMOTED_STATUSES and not self.evidence_ids:
            raise ValueError("promoted M8 decisions require evidence_ids")
        if self.status == "verified" and self.unresolved_dependencies:
            raise ValueError("verified M8 decisions cannot have unresolved dependencies")

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "VerificationDecision":
        data = dict(payload or {})
        return cls(
            rule_id=str(data.get("rule_id") or ""),
            status=str(data.get("status") or "review_needed"),
            reason=str(data.get("reason") or ""),
            evidence_ids=tuple(str(item) for item in data.get("evidence_ids", [])),
            unresolved_dependencies=tuple(str(item) for item in data.get("unresolved_dependencies", [])),
            support_gaps=tuple(str(item) for item in data.get("support_gaps", [])),
            repair_history=tuple(RepairAttempt.from_dict(row) for row in data.get("repair_history", [])),
            verifier=str(data.get("verifier") or "m8_dependency_wrapper"),
            metadata=_clean_dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class StructuredRule:
    rule_id: str
    city: str
    zone: str
    rule_type: str
    subject: str
    comparator: str = ""
    value: Any = None
    unit: str = ""
    conditions: tuple[str, ...] = ()
    exceptions: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    evidence_pointers: tuple[EvidencePointer, ...] = ()
    status: str = "review_needed"
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in M8_STATUSES:
            raise ValueError(f"unknown M8 status: {self.status}")
        if self.status in PROMOTED_STATUSES and not self.evidence_pointers:
            raise ValueError("promoted M8 rules require evidence pointers")
        if self.status in PROMOTED_STATUSES and self.dependencies:
            raise ValueError("promoted M8 rules cannot carry unresolved dependencies")

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        seen: list[str] = []
        for pointer in self.evidence_pointers:
            if pointer.evidence_id not in seen:
                seen.append(pointer.evidence_id)
        return tuple(seen)

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StructuredRule":
        data = dict(payload or {})
        return cls(
            rule_id=str(data.get("rule_id") or data.get("candidate_id") or ""),
            city=str(data.get("city") or ""),
            zone=str(data.get("zone") or ""),
            rule_type=str(data.get("rule_type") or data.get("rule_object") or ""),
            subject=str(data.get("subject") or data.get("applies_to") or ""),
            comparator=str(data.get("comparator") or data.get("operator") or ""),
            value=data.get("value"),
            unit=str(data.get("unit") or ""),
            conditions=tuple(str(item) for item in data.get("conditions", [])),
            exceptions=tuple(str(item) for item in data.get("exceptions", [])),
            dependencies=tuple(str(item) for item in data.get("dependencies", [])),
            evidence_pointers=tuple(EvidencePointer.from_dict(row) for row in data.get("evidence_pointers", [])),
            status=str(data.get("status") or "review_needed"),
            raw=_clean_dict(data.get("raw") or {}),
        )


@dataclass(frozen=True)
class M8RunSummary:
    city: str
    input_dir: str
    output_dir: str
    status_counts: dict[str, int] = field(default_factory=dict)
    m7_metrics: dict[str, Any] = field(default_factory=dict)
    m8_metrics: dict[str, Any] = field(default_factory=dict)
    safety: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "M8RunSummary":
        data = dict(payload or {})
        return cls(
            city=str(data.get("city") or ""),
            input_dir=str(data.get("input_dir") or ""),
            output_dir=str(data.get("output_dir") or ""),
            status_counts={str(k): int(v) for k, v in (data.get("status_counts") or {}).items()},
            m7_metrics=_clean_dict(data.get("m7_metrics") or {}),
            m8_metrics=_clean_dict(data.get("m8_metrics") or {}),
            safety=_clean_dict(data.get("safety") or {}),
            artifacts={str(k): str(v) for k, v in (data.get("artifacts") or {}).items()},
        )


def structured_rule_from_m7(
    rule: dict[str, Any],
    *,
    city: str,
    zone: str,
    evidence_pointer: EvidencePointer | None = None,
    status: str | None = None,
) -> StructuredRule:
    """Build a structured M8 rule from a current M7 row."""
    condition = str(rule.get("condition") or "").strip()
    exception = str(rule.get("exception") or "").strip()
    dependencies = tuple(str(item) for item in rule.get("m8_unresolved_dependencies", []) or [])
    pointers = (evidence_pointer,) if evidence_pointer else ()
    return StructuredRule(
        rule_id=str(rule.get("rule_id") or rule.get("candidate_id") or ""),
        city=city,
        zone=zone,
        rule_type=str(rule.get("rule_object") or ""),
        subject=str(rule.get("applies_to") or rule.get("constraint_scope") or ""),
        comparator=str(rule.get("operator") or ""),
        value=rule.get("value"),
        unit=str(rule.get("unit") or ""),
        conditions=(condition,) if condition else (),
        exceptions=(exception,) if exception else (),
        dependencies=dependencies,
        evidence_pointers=pointers,
        status=status or str(rule.get("verification_decision") or "review_needed"),
        raw=dict(rule),
    )
