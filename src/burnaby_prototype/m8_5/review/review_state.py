"""State transitions for M8.5 reviewer workbench artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from .review_packet import ReviewPacket
from .reviewer_actions import ReviewerAction
from .verifier_rerun_request import VerifierRerunRequest


@dataclass(frozen=True)
class ReviewState:
    packet: ReviewPacket
    actions: tuple[ReviewerAction, ...] = ()
    verifier_rerun_requests: tuple[VerifierRerunRequest, ...] = ()

    @property
    def current_status(self) -> str:
        return self.packet.current_status

    def apply_action(self, action: ReviewerAction) -> "ReviewState":
        if action.rule_id != self.packet.rule_id:
            raise ValueError("review action rule_id does not match review packet")
        packet = self.packet.with_reviewer_note(action.reviewer_note)
        requests = list(self.verifier_rerun_requests)
        if action.requires_verifier_rerun:
            requests.append(_rerun_request_for_action(packet, action))
        return ReviewState(
            packet=packet,
            actions=(*self.actions, action),
            verifier_rerun_requests=tuple(requests),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "packet": self.packet.to_dict(),
            "actions": [action.to_dict() for action in self.actions],
            "verifier_rerun_requests": [request.to_dict() for request in self.verifier_rerun_requests],
            "current_status": self.current_status,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ReviewState":
        data = dict(payload or {})
        return cls(
            packet=ReviewPacket.from_dict(data.get("packet") or {}),
            actions=tuple(ReviewerAction.from_dict(row) for row in data.get("actions", []) or []),
            verifier_rerun_requests=tuple(
                VerifierRerunRequest.from_dict(row) for row in data.get("verifier_rerun_requests", []) or []
            ),
        )


def _rerun_request_for_action(packet: ReviewPacket, action: ReviewerAction) -> VerifierRerunRequest:
    return VerifierRerunRequest(
        rule_id=packet.rule_id,
        source_action_id=action.action_id,
        candidate_rule_fields=packet.candidate_rule_fields,
        approved_evidence_ids=action.evidence_ids if action.action_type == "approve_evidence_link" else (),
        resolved_dependency_ids=action.dependency_ids
        if action.action_type in {"mark_dependency_resolved", "mark_dependency_not_applicable"}
        else (),
        table_lineage=packet.table_lineage,
        reviewer_note=action.reviewer_note,
        metadata={"reviewer_action_type": action.action_type},
    )

