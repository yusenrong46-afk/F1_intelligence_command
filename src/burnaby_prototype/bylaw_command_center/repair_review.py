"""F1 repair and review loop.

Checkpoint 6 turns verifier output into repair/review work items. It does not
generate legal approvals. A repair attempt is either review-only or verifier
rerun-ready; guarded promotions remain zero unless a later proof patch passes
deterministic verification.
"""

from __future__ import annotations

from copy import deepcopy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import ARTIFACT_SCHEMA_VERSION, RepairPatch, ReviewPacket, VerificationDecision
from .verification import build_verification_outputs


def build_repair_review_outputs(
    *,
    review_queue: list[dict[str, Any]],
    retrieval_report: dict[str, Any],
    city_key: str,
    run_id: str,
) -> dict[str, Any]:
    retrieval_queries = [row.get("query") for row in retrieval_report.get("queries") or [] if row.get("query")]
    repair_attempts = []
    review_packets = []
    for index, item in enumerate(review_queue, start=1):
        rule_id = str(item.get("rule_id") or f"review_{index:04d}")
        gaps = list(item.get("support_gaps") or [])
        dependencies = list(item.get("unresolved_dependencies") or [])
        candidate = item.get("candidate") if isinstance(item.get("candidate"), dict) else {}
        family = str(candidate.get("rule_type") or "")
        patch = RepairPatch(
            patch_id=f"f1_repair_{index:04d}",
            rule_id=rule_id,
            changed_fields={},
            field_proofs={},
            action="review_only",
            risk_flags=tuple(["needs_context"] if dependencies else []),
            model="deterministic_gap_router",
        )
        repair_attempt = patch.to_dict()
        repair_attempt.update(
            {
                "city_key": city_key,
                "status": "review_only",
                "gap_types": gaps,
                "unresolved_dependencies": dependencies,
                "suggested_retrieval_queries": _repair_queries(family, gaps, dependencies, retrieval_queries),
                "no_patch_reason": _no_patch_reason(gaps, dependencies),
                "verifier_rerun_ready": False,
            }
        )
        repair_attempts.append(repair_attempt)
        packet = ReviewPacket(
            packet_id=f"f1_review_{index:04d}",
            rule_id=rule_id,
            status=str(item.get("status") or "review_needed"),
            question=_review_question(candidate, gaps, dependencies),
            evidence_ids=tuple(str(eid) for eid in item.get("evidence_ids") or []),
            suggested_actions=("inspect_source_context", "improve_retrieval", "prepare_proof_patch"),
        )
        review_packets.append(packet.to_dict())
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "repair_review_outputs",
        "city_key": city_key,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repair_attempts": repair_attempts,
        "review_packets": review_packets,
        "repair_rerun_report": {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "artifact": "repair_rerun_report.json",
            "eligible_rule_count": 0,
            "attempt_count": 0,
            "promotion_ready_count": 0,
            "guarded_repair_promotion_count": 0,
            "review_only_attempt_count": len(repair_attempts),
            "false_verified_count": 0,
            "note": "Checkpoint 6 prepares repair/review work only; no proof patches were rerun through the verifier.",
        },
    }


def build_guarded_repair_rerun_outputs(
    *,
    review_queue: list[dict[str, Any]],
    retrieval_report: dict[str, Any],
    city_key: str,
    run_id: str,
    rule_contract_families: set[str] | None = None,
    preverified_rules: list[dict[str, Any]] | None = None,
    preverified_decisions: list[dict[str, Any]] | None = None,
    initial_candidate_count: int | None = None,
) -> dict[str, Any]:
    """Build verifier-rerun outputs from deterministic proof patches.

    This checkpoint only patches missing applicability when the existing cited
    quote plainly names the subject. All patched candidates are sent back
    through deterministic verification; the repair layer never promotes by
    itself.
    """
    base_payload = build_repair_review_outputs(
        review_queue=review_queue,
        retrieval_report=retrieval_report,
        city_key=city_key,
        run_id=run_id,
    )
    repair_attempts: list[dict[str, Any]] = []
    verifier_rerun_requests: list[dict[str, Any]] = []
    guarded_promotions: list[dict[str, Any]] = []
    verification_decisions: list[dict[str, Any]] = list(preverified_decisions or [])
    verified_rules: list[dict[str, Any]] = deepcopy(preverified_rules or [])
    remaining_review_queue: list[dict[str, Any]] = []
    eligible_rule_count = 0
    rerun_rejected_count = 0
    rerun_review_needed_count = 0
    rerun_not_used_count = 0

    for index, item in enumerate(review_queue, start=1):
        patch = _context_patch(index, item)
        if patch is None:
            repair_attempts.append(base_payload["repair_attempts"][index - 1])
            decision = _decision_from_review_item(item)
            verification_decisions.append(decision.to_dict())
            remaining_review_queue.append(item)
            continue

        eligible_rule_count += 1
        patched_candidate = _patched_candidate(item["candidate"], patch)
        attempt = patch.to_dict()
        attempt.update(
            {
                "city_key": city_key,
                "status": "proof_patch_ready",
                "gap_types": list(item.get("support_gaps") or []),
                "unresolved_dependencies": list(item.get("unresolved_dependencies") or []),
                "suggested_retrieval_queries": [],
                "no_patch_reason": "",
                "verifier_rerun_ready": True,
            }
        )
        repair_attempts.append(attempt)
        rerun = build_verification_outputs(
            candidate_rules=[patched_candidate],
            city_key=city_key,
            run_id=run_id,
        )
        rerun_decision = rerun["verification_decisions"][0]
        rerun_request = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "request_id": f"f1_rerun_{index:04d}",
            "rule_id": patched_candidate["rule_id"],
            "patch_id": patch.patch_id,
            "status": "completed",
            "verifier_status": rerun_decision["status"],
            "evidence_ids": rerun_decision["evidence_ids"],
            "support_gaps": rerun_decision["support_gaps"],
            "unresolved_dependencies": rerun_decision["unresolved_dependencies"],
            "risk_flags": rerun_decision["risk_flags"],
        }
        verifier_rerun_requests.append(rerun_request)
        if _guarded_promotable(rerun_decision) and _release_contract_promotable(
            patched_candidate,
            rule_contract_families=rule_contract_families,
        ):
            repaired_decision = VerificationDecision(
                rule_id=patched_candidate["rule_id"],
                status="repaired_successfully",
                reason="guarded repair patch passed deterministic verification",
                evidence_ids=tuple(str(eid) for eid in rerun_decision["evidence_ids"]),
                repair_history=(patch.patch_id,),
            )
            patched_candidate["status"] = "verified"
            verified_rules.append(patched_candidate)
            verification_decisions.append(repaired_decision.to_dict())
            guarded_promotions.append(
                {
                    "schema_version": ARTIFACT_SCHEMA_VERSION,
                    "rule_id": patched_candidate["rule_id"],
                    "patch_id": patch.patch_id,
                    "changed_fields": dict(patch.changed_fields),
                    "field_proofs": dict(patch.field_proofs),
                    "evidence_ids": list(repaired_decision.evidence_ids),
                    "decision_status": repaired_decision.status,
                }
            )
        else:
            decision_status = str(rerun_decision["status"])
            decision_reason = str(rerun_decision["reason"])
            decision_risk_flags = tuple(str(flag) for flag in rerun_decision["risk_flags"])
            if _guarded_promotable(rerun_decision):
                decision_status = "not_used"
                decision_reason = "verifier proof passed, but candidate is outside the configured F1 release contract"
                decision_risk_flags = ("outside_f1_release_contract",)
                patched_candidate["status"] = "not_used"
            decision = VerificationDecision(
                rule_id=str(rerun_decision["rule_id"]),
                status=decision_status,
                reason=decision_reason,
                evidence_ids=tuple(str(eid) for eid in rerun_decision["evidence_ids"]),
                support_gaps=tuple(str(gap) for gap in rerun_decision["support_gaps"]),
                unresolved_dependencies=tuple(str(dep) for dep in rerun_decision["unresolved_dependencies"]),
                risk_flags=decision_risk_flags,
                repair_history=(patch.patch_id,),
            )
            verification_decisions.append(decision.to_dict())
            remaining_review_queue.append(_review_item_from_decision(patched_candidate, decision))
            if decision.status == "rejected":
                rerun_rejected_count += 1
            elif decision.status == "not_used":
                rerun_not_used_count += 1
            else:
                rerun_review_needed_count += 1

    status_counts: dict[str, int] = {}
    for decision in verification_decisions:
        status = str(decision["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    payload = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "guarded_repair_rerun_outputs",
        "city_key": city_key,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repair_attempts": repair_attempts,
        "review_packets": base_payload["review_packets"],
        "verifier_rerun_requests": verifier_rerun_requests,
        "guarded_repair_promotions": guarded_promotions,
        "verification_decisions": verification_decisions,
        "verified_rules": verified_rules,
        "review_queue": remaining_review_queue,
        "verification_report": {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "artifact": "verification_report.json",
            "candidate_count": initial_candidate_count if initial_candidate_count is not None else len(verified_rules) + len(review_queue),
            "status_counts": status_counts,
            "verified_count": len(verified_rules),
            "review_queue_count": len(remaining_review_queue),
            "false_verified_count": 0,
            "promoter": "deterministic_f1_verifier_after_guarded_repair",
            "note": "Checkpoint 7 applies only verifier-passed proof patches.",
        },
        "repair_rerun_report": {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "artifact": "repair_rerun_report.json",
            "eligible_rule_count": eligible_rule_count,
            "attempt_count": len(verifier_rerun_requests),
            "promotion_ready_count": len(guarded_promotions),
            "guarded_repair_promotion_count": len(guarded_promotions),
            "review_only_attempt_count": len(repair_attempts) - len(verifier_rerun_requests),
            "repair_rerun_review_needed_count": rerun_review_needed_count,
            "repair_rerun_rejected_count": rerun_rejected_count,
            "repair_rerun_not_used_count": rerun_not_used_count,
            "remaining_review_queue_count": len(remaining_review_queue),
            "review_needed_reduction_from_repair_rerun": len(guarded_promotions),
            "false_verified_count": 0,
            "note": "Repair proposes proof patches; deterministic verification remains the promotion authority.",
        },
    }
    return payload


def write_repair_review_outputs(payload: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "repair_attempts": output_dir / "repair_attempts.json",
        "review_packets": output_dir / "review_packets.json",
        "repair_rerun_report": output_dir / "repair_rerun_report.json",
    }
    if "verifier_rerun_requests" in payload:
        paths["verifier_rerun_requests"] = output_dir / "verifier_rerun_requests.json"
    if "guarded_repair_promotions" in payload:
        paths["guarded_repair_promotions"] = output_dir / "guarded_repair_promotions.json"
    if "verification_decisions" in payload:
        paths["verification_decisions"] = output_dir / "verification_decisions.json"
        paths["verified_rules"] = output_dir / "verified_rules.json"
        paths["review_queue"] = output_dir / "review_queue.json"
        paths["verification_report"] = output_dir / "verification_report.json"
    paths["repair_attempts"].write_text(
        json.dumps(payload["repair_attempts"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["review_packets"].write_text(
        json.dumps(payload["review_packets"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["repair_rerun_report"].write_text(
        json.dumps(payload["repair_rerun_report"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if "verifier_rerun_requests" in payload:
        paths["verifier_rerun_requests"].write_text(
            json.dumps(payload["verifier_rerun_requests"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if "guarded_repair_promotions" in payload:
        paths["guarded_repair_promotions"].write_text(
            json.dumps(payload["guarded_repair_promotions"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    for key in ("verification_decisions", "verified_rules", "review_queue", "verification_report"):
        if key in payload:
            paths[key].write_text(json.dumps(payload[key], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return paths


def _context_patch(index: int, item: dict[str, Any]) -> RepairPatch | None:
    if item.get("support_gaps"):
        return None
    dependencies = set(str(dep) for dep in item.get("unresolved_dependencies") or [])
    if dependencies != {"applies_to_missing"}:
        return None
    candidate = item.get("candidate") if isinstance(item.get("candidate"), dict) else {}
    raw = candidate.get("raw") if isinstance(candidate.get("raw"), dict) else {}
    citations = raw.get("field_citations") if isinstance(raw.get("field_citations"), dict) else {}
    citation = citations.get("constraint_scope") if isinstance(citations.get("constraint_scope"), dict) else {}
    quote = str(citation.get("quote") or "")
    applies_to = _extract_applies_to(quote)
    if not applies_to:
        return None
    proof = {
        "evidence_id": citation.get("evidence_id"),
        "span_id": citation.get("span_id"),
        "page": citation.get("page"),
        "section_id": citation.get("section_id"),
        "quote": quote,
    }
    return RepairPatch(
        patch_id=f"f1_guarded_repair_{index:04d}",
        rule_id=str(item.get("rule_id") or candidate.get("rule_id") or f"review_{index:04d}"),
        changed_fields={"applies_to": applies_to},
        field_proofs={"applies_to": proof},
        action="proof_patch",
        risk_flags=(),
        model="deterministic_context_patch",
    )


def _patched_candidate(candidate: dict[str, Any], patch: RepairPatch) -> dict[str, Any]:
    patched = deepcopy(candidate)
    patched["applies_to"] = str(patch.changed_fields["applies_to"])
    raw = patched.setdefault("raw", {})
    citations = raw.setdefault("field_citations", {})
    citations["applies_to"] = dict(patch.field_proofs["applies_to"])
    history = list(raw.get("repair_history") or [])
    history.append(
        {
            "patch_id": patch.patch_id,
            "changed_fields": dict(patch.changed_fields),
            "model": patch.model,
            "action": patch.action,
        }
    )
    raw["repair_history"] = history
    raw["extraction_note"] = "Candidate copy repaired by proof patch; deterministic verification decides promotion."
    return patched


def _extract_applies_to(quote: str) -> str:
    text = re.sub(r"\s+", " ", quote).strip()
    text = re.sub(r"^\(?[a-z0-9]+\)?\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\.\d+\s+", "", text)
    patterns = (
        r"^(?P<subject>.+?)\s+shall not exceed\b",
        r"^(?P<subject>.+?)\s+must have\b",
        r"^(?P<subject>.+?)\s+may meet\b",
        r"^(?P<subject>.+?)\s+may be increased\b",
        r"^(?P<subject>.+?)\s+shall have\b",
        r"^(?P<subject>.+?)\s+shall contain\b",
        r"^(?P<subject>.+?)\s+must contain\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_subject(match.group("subject"))
    return ""


def _clean_subject(subject: str) -> str:
    cleaned = subject.strip(" ;:,.")
    cleaned = re.sub(r"^(any|each|all|a|an|the)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" ;:,.")
    if len(cleaned.split()) > 24:
        cleaned = " ".join(cleaned.split()[:24])
    return cleaned


def _guarded_promotable(decision: dict[str, Any]) -> bool:
    return (
        decision.get("status") == "verified"
        and bool(decision.get("evidence_ids"))
        and not decision.get("support_gaps")
        and not decision.get("unresolved_dependencies")
        and not decision.get("risk_flags")
    )


def _release_contract_promotable(candidate: dict[str, Any], *, rule_contract_families: set[str] | None) -> bool:
    family = str(candidate.get("rule_object") or candidate.get("rule_type") or "")
    if rule_contract_families is not None and family not in rule_contract_families:
        return False
    applies_to = str(candidate.get("applies_to") or "").lower()
    if "not being a building" in applies_to:
        return False
    return True


def _decision_from_review_item(item: dict[str, Any]) -> VerificationDecision:
    return VerificationDecision(
        rule_id=str(item.get("rule_id") or ""),
        status=str(item.get("status") or "review_needed"),
        reason=str(item.get("reason") or "remains under review"),
        evidence_ids=tuple(str(eid) for eid in item.get("evidence_ids") or []),
        support_gaps=tuple(str(gap) for gap in item.get("support_gaps") or []),
        unresolved_dependencies=tuple(str(dep) for dep in item.get("unresolved_dependencies") or []),
    )


def _review_item_from_decision(candidate: dict[str, Any], decision: VerificationDecision) -> dict[str, Any]:
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "rule_id": candidate.get("rule_id"),
        "status": decision.status,
        "reason": decision.reason,
        "support_gaps": list(decision.support_gaps),
        "unresolved_dependencies": list(decision.unresolved_dependencies),
        "evidence_ids": list(decision.evidence_ids),
        "candidate": candidate,
    }


def _repair_queries(
    family: str,
    gaps: list[str],
    dependencies: list[str],
    existing_queries: list[str],
) -> list[str]:
    queries = []
    family_text = family.replace("_", " ")
    for gap in gaps:
        if "operator" in gap:
            queries.append(f"{family_text} maximum minimum shall not exceed at least")
        elif "value" in gap or "unit" in gap:
            queries.append(f"{family_text} value unit table row")
        elif "rule_object" in gap:
            queries.append(f"{family_text} definition table heading")
    for dependency in dependencies:
        if "applies_to" in dependency:
            queries.append(f"{family_text} applies to dwelling building unit")
        elif "scope" in dependency:
            queries.append(f"{family_text} scope heading condition exception")
    queries.extend(query for query in existing_queries if family_text and family_text.split()[0] in query)
    return list(dict.fromkeys(query for query in queries if query.strip()))


def _no_patch_reason(gaps: list[str], dependencies: list[str]) -> str:
    if dependencies:
        return "candidate needs applicability or scope context before verifier rerun"
    if gaps:
        return "candidate has unsupported field evidence; retrieve stronger proof before patching"
    return "no safe changed fields proposed at checkpoint 6"


def _review_question(candidate: dict[str, Any], gaps: list[str], dependencies: list[str]) -> str:
    family = str(candidate.get("rule_type") or "rule").replace("_", " ")
    if dependencies:
        return f"What applicability or scope context is required before verifying this {family} candidate?"
    if gaps:
        return f"Which source span exactly supports the missing fields for this {family} candidate?"
    return f"Should this {family} candidate receive a proof patch or remain under review?"
