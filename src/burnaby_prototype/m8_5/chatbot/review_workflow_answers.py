"""Reviewer workflow answer helpers for M8.5 chatbot."""

from __future__ import annotations

from typing import Any


def sorted_review_packets(context: dict[str, Any]) -> list[dict[str, Any]]:
    packets = list(context.get("review_packets") or [])
    return sorted(packets, key=lambda packet: (-_priority(packet), str(packet.get("rule_id") or "")))


def reviewer_next_step(packet: dict[str, Any]) -> str:
    action = str(packet.get("recommended_reviewer_action") or "mark_needs_legal_review")
    rule_id = str(packet.get("rule_id") or "")
    reason = str(packet.get("failure_reason") or "requires review")
    return f"Inspect `{rule_id}` next. Recommended action: `{action}`. Reason: {reason}."


def _priority(packet: dict[str, Any]) -> int:
    action = str(packet.get("recommended_reviewer_action") or "")
    status = str(packet.get("current_status") or "")
    dependencies = packet.get("dependency_graph_slice") or []
    repair_evaluations = packet.get("repair_evaluations") or []
    score = 0
    if action == "send_to_verifier" or any(item.get("verifier_ready") for item in repair_evaluations):
        score += 50
    if status == "context_required":
        score += 20
    if dependencies:
        score += 10 + min(len(dependencies), 5)
    return score
