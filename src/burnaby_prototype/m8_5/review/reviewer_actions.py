"""Reviewer actions for M8.5 workbench artifacts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


ALLOWED_REVIEWER_ACTIONS = frozenset(
    {
        "approve_evidence_link",
        "reject_evidence_link",
        "mark_dependency_resolved",
        "mark_dependency_not_applicable",
        "add_missing_exception",
        "flag_conflict",
        "request_more_retrieval",
        "send_to_verifier",
        "mark_needs_legal_review",
    }
)

DIRECT_VERIFY_ACTIONS = frozenset({"verify", "verified", "mark_verified", "approve_rule", "mark_rule_verified"})

RERUN_ACTIONS = frozenset(
    {
        "approve_evidence_link",
        "mark_dependency_resolved",
        "mark_dependency_not_applicable",
        "add_missing_exception",
        "send_to_verifier",
    }
)


@dataclass(frozen=True)
class ReviewerAction:
    rule_id: str
    action_type: str
    reviewer_note: str = ""
    evidence_ids: tuple[str, ...] = ()
    dependency_ids: tuple[str, ...] = ()
    reviewer_id: str = ""
    created_at: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.action_type in DIRECT_VERIFY_ACTIONS:
            raise ValueError("reviewer action cannot directly verify a rule")
        if self.action_type not in ALLOWED_REVIEWER_ACTIONS:
            raise ValueError(f"unknown reviewer action: {self.action_type}")
        if not self.rule_id:
            raise ValueError("reviewer action requires rule_id")
        if not self.created_at:
            object.__setattr__(self, "created_at", datetime.now(timezone.utc).isoformat())

    @property
    def action_id(self) -> str:
        return "review_action_" + _stable_id(
            self.rule_id,
            self.action_type,
            self.reviewer_note,
            ",".join(self.evidence_ids),
            ",".join(self.dependency_ids),
            self.created_at,
        )

    @property
    def requires_verifier_rerun(self) -> bool:
        return self.action_type in RERUN_ACTIONS

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "rule_id": self.rule_id,
            "action_type": self.action_type,
            "reviewer_note": self.reviewer_note,
            "evidence_ids": list(self.evidence_ids),
            "dependency_ids": list(self.dependency_ids),
            "reviewer_id": self.reviewer_id,
            "created_at": self.created_at,
            "payload": dict(self.payload),
            "requires_verifier_rerun": self.requires_verifier_rerun,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReviewerAction":
        data = dict(payload or {})
        return cls(
            rule_id=str(data.get("rule_id") or ""),
            action_type=str(data.get("action_type") or ""),
            reviewer_note=str(data.get("reviewer_note") or ""),
            evidence_ids=tuple(str(item) for item in data.get("evidence_ids", [])),
            dependency_ids=tuple(str(item) for item in data.get("dependency_ids", [])),
            reviewer_id=str(data.get("reviewer_id") or ""),
            created_at=str(data.get("created_at") or ""),
            payload=dict(data.get("payload") or {}),
        )


def _stable_id(*parts: Any, length: int = 16) -> str:
    text = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]

