"""Review packet artifact for M8.5 reviewer workbench."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from burnaby_prototype.m8.extraction.rule_schema import SourceSpan

from ..dependencies.dependency_graph import RuleDependency
from ..repair_evaluation.repair_evaluation import RepairEvaluation


@dataclass(frozen=True)
class ReviewPacket:
    rule_id: str
    current_status: str
    failure_reason: str
    candidate_rule_fields: dict[str, Any]
    evidence_spans: tuple[SourceSpan, ...] = ()
    table_lineage: dict[str, Any] | None = None
    dependency_graph_slice: tuple[RuleDependency, ...] = ()
    repair_attempts: tuple[Any, ...] = ()
    repair_evaluations: tuple[RepairEvaluation, ...] = ()
    recommended_reviewer_action: str = "mark_needs_legal_review"
    reviewer_notes: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.rule_id:
            raise ValueError("review packet requires rule_id")
        if self.current_status == "verified":
            raise ValueError("review packets are for unresolved work, not verified rules")
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            object.__setattr__(self, "created_at", now)
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at or now)

    def with_reviewer_note(self, note: str) -> "ReviewPacket":
        if not note:
            return self
        return replace(
            self,
            reviewer_notes=(*self.reviewer_notes, note),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    def dashboard_context(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "current_status": self.current_status,
            "failure_reason": self.failure_reason,
            "candidate_rule_fields": dict(self.candidate_rule_fields),
            "evidence_count": len(self.evidence_spans),
            "dependency_count": len(self.dependency_graph_slice),
            "repair_attempt_count": len(self.repair_attempts),
            "repair_evaluation_count": len(self.repair_evaluations),
            "recommended_reviewer_action": self.recommended_reviewer_action,
            "has_table_lineage": self.table_lineage is not None,
            "reviewer_notes": list(self.reviewer_notes),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "current_status": self.current_status,
            "failure_reason": self.failure_reason,
            "candidate_rule_fields": dict(self.candidate_rule_fields),
            "evidence_spans": [span.to_dict() for span in self.evidence_spans],
            "table_lineage": self.table_lineage,
            "dependency_graph_slice": [dependency.to_dict() for dependency in self.dependency_graph_slice],
            "repair_attempts": list(self.repair_attempts),
            "repair_evaluations": [evaluation.to_dict() for evaluation in self.repair_evaluations],
            "recommended_reviewer_action": self.recommended_reviewer_action,
            "reviewer_notes": list(self.reviewer_notes),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
            "dashboard_context": self.dashboard_context(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReviewPacket":
        data = dict(payload or {})
        return cls(
            rule_id=str(data.get("rule_id") or ""),
            current_status=str(data.get("current_status") or "review_needed"),
            failure_reason=str(data.get("failure_reason") or ""),
            candidate_rule_fields=dict(data.get("candidate_rule_fields") or {}),
            evidence_spans=tuple(SourceSpan.from_dict(row) for row in data.get("evidence_spans", [])),
            table_lineage=data.get("table_lineage"),
            dependency_graph_slice=tuple(
                RuleDependency.from_dict(row) for row in data.get("dependency_graph_slice", [])
            ),
            repair_attempts=tuple(data.get("repair_attempts", [])),
            repair_evaluations=tuple(
                RepairEvaluation.from_dict(row) for row in data.get("repair_evaluations", [])
            ),
            recommended_reviewer_action=str(data.get("recommended_reviewer_action") or "mark_needs_legal_review"),
            reviewer_notes=tuple(str(item) for item in data.get("reviewer_notes", [])),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            metadata=dict(data.get("metadata") or {}),
        )

