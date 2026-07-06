"""M8.5 repair evaluation contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from burnaby_prototype.m8.extraction.rule_schema import SourceSpan

from .patch_safety_checker import PATCH_SAFETY_CATEGORIES, PatchSafetyChecker
from .verifier_ready_gate import VerifierReadyGate, recommended_status_for_category


@dataclass(frozen=True)
class RepairEvaluation:
    rule_id: str
    original_failure: str
    changed_fields: tuple[str, ...]
    safety_category: str
    safety_findings: tuple[str, ...]
    verifier_ready: bool
    recommended_status: str
    evidence_ids: tuple[str, ...] = ()
    introduced_dependencies: tuple[str, ...] = ()
    repair_history: tuple[Any, ...] = ()
    verifier_result: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.safety_category not in PATCH_SAFETY_CATEGORIES:
            raise ValueError(f"unknown patch safety category: {self.safety_category}")
        if self.recommended_status == "verified":
            raise ValueError("repair evaluator cannot recommend direct verified status")

    @property
    def promotes_directly(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "original_failure": self.original_failure,
            "changed_fields": list(self.changed_fields),
            "safety_category": self.safety_category,
            "safety_findings": list(self.safety_findings),
            "verifier_ready": self.verifier_ready,
            "recommended_status": self.recommended_status,
            "evidence_ids": list(self.evidence_ids),
            "introduced_dependencies": list(self.introduced_dependencies),
            "repair_history": list(self.repair_history),
            "verifier_result": self.verifier_result,
            "metadata": dict(self.metadata),
            "promotes_directly": self.promotes_directly,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RepairEvaluation":
        data = dict(payload or {})
        return cls(
            rule_id=str(data.get("rule_id") or ""),
            original_failure=str(data.get("original_failure") or ""),
            changed_fields=tuple(str(item) for item in data.get("changed_fields", [])),
            safety_category=str(data.get("safety_category") or "needs_human_review"),
            safety_findings=tuple(str(item) for item in data.get("safety_findings", [])),
            verifier_ready=bool(data.get("verifier_ready")),
            recommended_status=str(data.get("recommended_status") or "review_needed"),
            evidence_ids=tuple(str(item) for item in data.get("evidence_ids", [])),
            introduced_dependencies=tuple(str(item) for item in data.get("introduced_dependencies", [])),
            repair_history=tuple(data.get("repair_history", [])),
            verifier_result=data.get("verifier_result"),
            metadata=dict(data.get("metadata") or {}),
        )


def evaluate_repair(
    *,
    original_rule: dict[str, Any],
    patched_rule: dict[str, Any],
    evidence_by_id: dict[str, SourceSpan] | None = None,
    repair_history: tuple[Any, ...] = (),
    verifier_result: dict[str, Any] | None = None,
) -> RepairEvaluation:
    evidence_by_id = evidence_by_id or {}
    checker = PatchSafetyChecker()
    check = checker.check(
        original_rule=original_rule,
        patched_rule=patched_rule,
        evidence_by_id=evidence_by_id,
    )
    gate = VerifierReadyGate()
    verifier_ready = gate.is_ready(
        safety_category=check["safety_category"],
        findings=check["safety_findings"],
    )
    evidence_id = str(patched_rule.get("evidence_id") or "")
    introduced_dependencies = []
    if "exception_dependency_introduced" in check["safety_findings"]:
        introduced_dependencies.append("exception")
    return RepairEvaluation(
        rule_id=str(patched_rule.get("rule_id") or original_rule.get("rule_id") or patched_rule.get("candidate_id") or ""),
        original_failure=_original_failure(original_rule),
        changed_fields=check["changed_fields"],
        safety_category=check["safety_category"],
        safety_findings=check["safety_findings"],
        verifier_ready=verifier_ready,
        recommended_status=recommended_status_for_category(check["safety_category"], verifier_ready=verifier_ready),
        evidence_ids=(evidence_id,) if evidence_id else (),
        introduced_dependencies=tuple(introduced_dependencies),
        repair_history=repair_history,
        verifier_result=verifier_result,
        metadata={
            "original_rule_status": original_rule.get("verification_decision") or original_rule.get("status"),
            "patched_rule_status": patched_rule.get("verification_decision") or patched_rule.get("status"),
        },
    )


def _original_failure(rule: dict[str, Any]) -> str:
    if rule.get("review_reason"):
        return str(rule.get("review_reason"))
    gaps = [str(gap) for gap in rule.get("support_gaps", []) or []]
    if gaps:
        return "; ".join(gaps)
    return "not specified"
