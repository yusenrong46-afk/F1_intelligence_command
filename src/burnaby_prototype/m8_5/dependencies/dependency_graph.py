"""M8.5 legal dependency graph contracts."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from .dependency_types import DEPENDENCY_STATUSES, DEPENDENCY_TYPES


def stable_id(*parts: Any, length: int = 16) -> str:
    text = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


@dataclass(frozen=True)
class RuleDependency:
    source_rule_id: str
    dependency_type: str
    target_reference: str
    status: str
    evidence_ids: tuple[str, ...] = ()
    reason: str = ""
    resolver_confidence: float = 0.0
    reviewer_note: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_rule_id:
            raise ValueError("source_rule_id is required")
        if self.dependency_type not in DEPENDENCY_TYPES:
            raise ValueError(f"unknown dependency type: {self.dependency_type}")
        if self.status not in DEPENDENCY_STATUSES:
            raise ValueError(f"unknown dependency status: {self.status}")
        if not 0.0 <= float(self.resolver_confidence) <= 1.0:
            raise ValueError("resolver_confidence must be between 0 and 1")

    @property
    def dependency_id(self) -> str:
        return "dep_" + stable_id(self.source_rule_id, self.dependency_type, self.target_reference)

    @property
    def is_blocking(self) -> bool:
        return self.status in {"unresolved", "conflicting"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "dependency_id": self.dependency_id,
            "source_rule_id": self.source_rule_id,
            "dependency_type": self.dependency_type,
            "target_reference": self.target_reference,
            "status": self.status,
            "evidence_ids": list(self.evidence_ids),
            "reason": self.reason,
            "resolver_confidence": self.resolver_confidence,
            "reviewer_note": self.reviewer_note,
            "metadata": dict(self.metadata),
            "is_blocking": self.is_blocking,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuleDependency":
        data = dict(payload or {})
        return cls(
            source_rule_id=str(data.get("source_rule_id") or ""),
            dependency_type=str(data.get("dependency_type") or ""),
            target_reference=str(data.get("target_reference") or ""),
            status=str(data.get("status") or "unresolved"),
            evidence_ids=tuple(str(item) for item in data.get("evidence_ids", [])),
            reason=str(data.get("reason") or ""),
            resolver_confidence=float(data.get("resolver_confidence") or 0.0),
            reviewer_note=str(data.get("reviewer_note") or ""),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class DependencyGraph:
    dependencies: tuple[RuleDependency, ...] = ()

    def __init__(self, dependencies: Iterable[RuleDependency] = ()) -> None:
        object.__setattr__(self, "dependencies", tuple(dependencies))

    def for_rule(self, rule_id: str) -> list[RuleDependency]:
        return [dependency for dependency in self.dependencies if dependency.source_rule_id == rule_id]

    def rule_has_blockers(self, rule_id: str) -> bool:
        return any(dependency.is_blocking for dependency in self.for_rule(rule_id))

    def status_for_rule(self, rule_id: str, *, base_status: str = "review_needed") -> str:
        dependencies = self.for_rule(rule_id)
        if any(dependency.status == "conflicting" for dependency in dependencies):
            return "review_needed" if base_status in {"verified", "repaired_successfully"} else base_status
        if any(dependency.status == "unresolved" for dependency in dependencies):
            return "context_required"
        return base_status

    def status_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(dependency.status for dependency in self.dependencies).items()))

    def type_metrics(self) -> dict[str, dict[str, int]]:
        metrics: dict[str, Counter[str]] = defaultdict(Counter)
        for dependency in self.dependencies:
            metrics[dependency.dependency_type]["total"] += 1
            metrics[dependency.dependency_type][dependency.status] += 1
        return {
            dependency_type: dict(sorted(counter.items()))
            for dependency_type, counter in sorted(metrics.items())
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "dependency_count": len(self.dependencies),
            "dependencies": [dependency.to_dict() for dependency in self.dependencies],
            "status_counts": self.status_counts(),
            "type_metrics": self.type_metrics(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DependencyGraph":
        return cls(RuleDependency.from_dict(row) for row in (payload or {}).get("dependencies", []))

