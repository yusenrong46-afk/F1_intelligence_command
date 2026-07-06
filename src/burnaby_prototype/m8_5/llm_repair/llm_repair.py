"""LLM-assisted proof patch generation for M8.5 repair.

This module deliberately stops at candidate patch generation. A patch is useful
only if it survives local proof validation and the existing deterministic
verifier rerun.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

from burnaby_prototype.m7_model_extraction import estimate_cost
from burnaby_prototype.m8.extraction.rule_schema import (
    EvidencePointer,
    RepairAttempt,
    RepairCritique,
    RepairPatch,
    SourceSpan,
)
from burnaby_prototype.m8.retrieval.hybrid_index import HybridM8Index
from burnaby_prototype.m8.retrieval.query_planner import plan_query
from burnaby_prototype.native_extraction import OpenRouterChatClient, OpenRouterError


ALLOWED_PATCH_FIELDS = frozenset(
    {
        "rule_object",
        "constraint_scope",
        "applies_to",
        "operator",
        "value",
        "unit",
        "condition",
        "exception",
        "evidence_id",
    }
)
ALLOWED_ACTIONS = frozenset({"patch", "no_patch"})
ALLOWED_TOP_LEVEL_FIELDS = frozenset(
    {"action", "changes", "field_proofs", "confidence", "risk_flags", "no_patch_reason"}
)
ALLOWED_PROOF_FIELDS = frozenset({"field", "evidence_id", "span_id", "quote", "rationale"})
SCOPE_PROOF_FIELDS = frozenset({"rule_object", "constraint_scope", "applies_to", "condition"})


class LLMRepairError(RuntimeError):
    """LLM repair generation failed."""


class LLMRepairParseError(ValueError):
    """LLM repair output violated the strict patch contract."""


class RepairClient(Protocol):
    def propose(self, case: dict[str, Any]) -> dict[str, Any]:
        """Return one raw repair payload for a case."""


@dataclass
class OpenRouterRepairClient:
    api_key: str
    model: str = "google/gemini-3.1-flash-lite"
    max_tokens: int = 1200

    def __post_init__(self) -> None:
        self._client = OpenRouterChatClient(self.api_key, model=self.model, max_tokens=self.max_tokens)

    def propose(self, case: dict[str, Any]) -> dict[str, Any]:
        body = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "stream": False,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": repair_prompt(case)},
            ],
            "response_format": {"type": "json_object"},
        }
        try:
            payload = self._client._post_json("/chat/completions", body)
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMRepairError("OpenRouter repair response did not include message content") from exc
        except OpenRouterError as exc:
            raise LLMRepairError(str(exc)) from exc
        return parse_llm_repair_payload(content)


class FixtureRepairClient:
    """Deterministic test client backed by local JSON payloads."""

    def __init__(self, payloads: dict[str, Any] | list[dict[str, Any]]) -> None:
        if isinstance(payloads, dict):
            self._by_rule = {
                str(rule_id): payload
                for rule_id, payload in payloads.items()
            }
            self._ordered: list[dict[str, Any]] = []
        else:
            self._ordered = list(payloads)
            self._by_rule = {
                str(payload.get("rule_id")): payload.get("payload", payload)
                for payload in self._ordered
                if payload.get("rule_id")
            }
        self._index = 0

    def propose(self, case: dict[str, Any]) -> dict[str, Any]:
        rule_id = str(case.get("rule_id") or "")
        if rule_id in self._by_rule:
            return parse_llm_repair_payload(self._by_rule[rule_id])
        if self._index < len(self._ordered):
            payload = self._ordered[self._index]
            self._index += 1
            return parse_llm_repair_payload(payload.get("payload", payload))
        return {
            "action": "no_patch",
            "changes": {},
            "field_proofs": [],
            "confidence": 0.0,
            "risk_flags": [],
            "no_patch_reason": "fixture did not provide a patch",
        }


_SYSTEM_PROMPT = (
    "You are a zoning-rule repair proposer. A deterministic verifier already "
    "rejected or held the rule for review. Return only JSON. You may propose a "
    "candidate patch, but you must not say the rule is verified, approved, or "
    "legal. Every changed field needs a citation from the provided evidence. "
    "If the evidence is incomplete, return action=no_patch."
)


def disabled_llm_repair_outputs() -> dict[str, Any]:
    return {
        "enabled": False,
        "mode": "disabled",
        "cases": [],
        "raw_outputs": [],
        "patches": [],
        "field_proofs": [],
        "attempts": [],
        "evaluations": [],
        "metrics": {
            "llm_repair_case_count": 0,
            "llm_repair_patch_count": 0,
            "llm_repair_no_patch_count": 0,
            "llm_repair_safe_patch_count": 0,
            "llm_repair_rejected_patch_count": 0,
            "field_proof_completion_rate": 0.0,
            "llm_repair_latency_ms": 0,
            "llm_repair_estimated_cost_usd": 0.0,
            "review_needed_reduction_from_llm_repair": 0,
        },
    }


def build_llm_repair_cases(
    *,
    city: str,
    structured_rules: list[dict[str, Any]],
    verification_decisions: list[dict[str, Any]],
    source_spans: list[SourceSpan],
    repair_rerun_report: dict[str, Any] | None = None,
    max_cases: int = 0,
    max_evidence_snippets: int = 8,
) -> list[dict[str, Any]]:
    decisions_by_rule = {str(row.get("rule_id") or ""): row for row in verification_decisions}
    priority = _failed_repair_priority(repair_rerun_report or {})
    review_rules = [
        rule
        for rule in structured_rules
        if str(decisions_by_rule.get(str(rule.get("rule_id") or ""), rule).get("status") or rule.get("status") or "")
        in {"review_needed", "context_required"}
    ]
    review_rules.sort(key=lambda rule: (priority.get(str(rule.get("rule_id") or ""), 10**9), str(rule.get("rule_id") or "")))
    if max_cases and max_cases > 0:
        review_rules = review_rules[:max_cases]
    index = HybridM8Index(_dedupe_spans(source_spans))
    cases: list[dict[str, Any]] = []
    for ordinal, rule in enumerate(review_rules, start=1):
        rule_id = str(rule.get("rule_id") or "")
        decision = decisions_by_rule.get(rule_id, {})
        support_gaps = _support_gaps(rule, decision, repair_rerun_report or {})
        candidate_fields = candidate_fields_for_rule(rule)
        snippets = retrieve_repair_snippets(
            city=city,
            index=index,
            rule=rule,
            candidate_fields=candidate_fields,
            support_gaps=support_gaps,
            max_snippets=max_evidence_snippets,
        )
        cases.append(
            {
                "case_id": f"llm_repair_case_{ordinal:04d}",
                "rule_id": rule_id,
                "priority": "failed_repair_rerun" if rule_id in priority else "review_worklist",
                "current_status": str(decision.get("status") or rule.get("status") or ""),
                "support_gaps": support_gaps,
                "candidate_fields": candidate_fields,
                "evidence_snippets": snippets,
                "instructions": {
                    "allowed_changed_fields": sorted(ALLOWED_PATCH_FIELDS),
                    "promotion_policy": "LLM proposes only; deterministic verifier decides.",
                },
            }
        )
    return cases


def retrieve_repair_snippets(
    *,
    city: str,
    index: HybridM8Index,
    rule: dict[str, Any],
    candidate_fields: dict[str, Any],
    support_gaps: list[str],
    max_snippets: int,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    snippets: list[dict[str, Any]] = []
    for query in _repair_queries(rule, candidate_fields, support_gaps):
        planned = plan_query(query, city=city)
        for hit in index.search(planned, top_k=max_snippets):
            evidence_id = str(hit.span.metadata.get("evidence_id") or hit.span.metadata.get("chunk_id") or hit.span.span_id)
            key = f"{evidence_id}:{hit.span.span_id}"
            if key in seen:
                continue
            seen.add(key)
            snippets.append(
                {
                    "evidence_id": evidence_id,
                    "span_id": hit.span.span_id,
                    "quote": hit.span.text[:900],
                    "page": hit.span.page,
                    "section_id": hit.span.section_id,
                    "block_type": hit.span.block_type,
                    "score": hit.score,
                    "signals": hit.signals,
                    "metadata": dict(hit.span.metadata or {}),
                }
            )
            if len(snippets) >= max_snippets:
                return snippets
    return snippets


def run_llm_repair(
    *,
    cases: list[dict[str, Any]],
    evidence_by_id: dict[str, SourceSpan],
    client: RepairClient | None,
    dry_run: bool,
) -> dict[str, Any]:
    raw_outputs: list[dict[str, Any]] = []
    patches: list[dict[str, Any]] = []
    field_proofs: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    if dry_run or client is None:
        for case in cases:
            raw_outputs.append(
                {
                    "case_id": case["case_id"],
                    "rule_id": case["rule_id"],
                    "source": "dry_run",
                    "payload": {
                        "action": "no_patch",
                        "changes": {},
                        "field_proofs": [],
                        "confidence": 0.0,
                        "risk_flags": [],
                        "no_patch_reason": "dry run did not call an LLM repair model",
                    },
                    "latency_ms": 0,
                    "estimated_cost_usd": 0.0,
                }
            )
        return _llm_outputs(cases, raw_outputs, patches, field_proofs, attempts)

    for case in cases:
        started = time.perf_counter()
        prompt = repair_prompt(case)
        try:
            payload = client.propose(case)
            error = ""
        except (LLMRepairError, LLMRepairParseError, ValueError) as exc:
            payload = {
                "action": "no_patch",
                "changes": {},
                "field_proofs": [],
                "confidence": 0.0,
                "risk_flags": ["llm_repair_error"],
                "no_patch_reason": str(exc),
            }
            error = f"{type(exc).__name__}: {exc}"
        latency_ms = int((time.perf_counter() - started) * 1000)
        model = str(getattr(client, "model", "") or "")
        estimated_cost = estimate_cost(
            model,
            input_chars=len(prompt),
            output_chars=len(json.dumps(payload, ensure_ascii=False)),
        ) if model else 0.0
        validation = validate_llm_repair_payload(payload, case=case, evidence_by_id=evidence_by_id)
        raw_outputs.append(
            {
                "case_id": case["case_id"],
                "rule_id": case["rule_id"],
                "source": "llm_repair_model",
                "model": model or None,
                "latency_ms": latency_ms,
                "estimated_cost_usd": estimated_cost,
                "payload": payload,
                "validation": validation,
                "error": error,
            }
        )
        patch_row = {
            "case_id": case["case_id"],
            "rule_id": case["rule_id"],
            "accepted": validation["accepted"],
            "findings": validation["findings"],
            "payload": payload,
        }
        patches.append(patch_row)
        for proof in payload.get("field_proofs") or []:
            field_proofs.append({"case_id": case["case_id"], "rule_id": case["rule_id"], **proof})
        if validation["accepted"]:
            attempts.append(_attempt_from_validated_patch(case, validation, evidence_by_id))
    return _llm_outputs(cases, raw_outputs, patches, field_proofs, attempts)


def run_local_table_proof_repair(
    *,
    cases: list[dict[str, Any]],
    evidence_by_id: dict[str, SourceSpan],
    m7_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create deterministic proof patches from exact M7 table-cell candidates.

    This is a local proposer, not a promotion path. It repairs only weak review
    candidates whose core scalar field already matches a table candidate.
    """
    raw_outputs: list[dict[str, Any]] = []
    patches: list[dict[str, Any]] = []
    field_proofs: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for case in cases:
        payload = _local_table_payload(case, evidence_by_id, m7_candidates)
        if payload["action"] != "patch":
            continue
        validation = validate_llm_repair_payload(payload, case=case, evidence_by_id=evidence_by_id)
        raw_outputs.append(
            {
                "case_id": case["case_id"],
                "rule_id": case["rule_id"],
                "source": "local_table_proof_repair",
                "payload": payload,
                "validation": validation,
                "latency_ms": 0,
                "estimated_cost_usd": 0.0,
            }
        )
        patches.append(
            {
                "case_id": case["case_id"],
                "rule_id": case["rule_id"],
                "accepted": validation["accepted"],
                "findings": validation["findings"],
                "payload": payload,
            }
        )
        for proof in payload.get("field_proofs") or []:
            field_proofs.append({"case_id": case["case_id"], "rule_id": case["rule_id"], **proof})
        if validation["accepted"]:
            attempt = _attempt_from_validated_patch(case, validation, evidence_by_id)
            attempt["query"] = "local_table_proof_repair"
            attempt["metadata"] = {
                **dict(attempt.get("metadata") or {}),
                "repair_source": "local_table_proof_repair",
                "clear_extraction_review": True,
            }
            attempts.append(attempt)
    outputs = _llm_outputs(cases, raw_outputs, patches, field_proofs, attempts)
    outputs["mode"] = "local_table_proof_patch"
    outputs["notes"] = [
        "Local table proof repair proposes candidate patches only.",
        "It requires exact rule object, value, and unit agreement with M7 table-cell evidence.",
        "Validated proof patches still require deterministic verifier rerun before promotion.",
    ]
    return outputs


def merge_repair_outputs(*outputs: dict[str, Any]) -> dict[str, Any]:
    enabled = any(output.get("enabled") for output in outputs)
    cases: list[dict[str, Any]] = []
    seen_cases: set[str] = set()
    raw_outputs: list[dict[str, Any]] = []
    patches: list[dict[str, Any]] = []
    field_proofs: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    notes: list[str] = []
    for output in outputs:
        for case in output.get("cases") or []:
            case_id = str(case.get("case_id") or "")
            if case_id not in seen_cases:
                cases.append(case)
                seen_cases.add(case_id)
        raw_outputs.extend(dict(row) for row in output.get("raw_outputs") or [])
        patches.extend(dict(row) for row in output.get("patches") or [])
        field_proofs.extend(dict(row) for row in output.get("field_proofs") or [])
        attempts.extend(dict(row) for row in output.get("attempts") or [])
        notes.extend(str(note) for note in output.get("notes") or [])
    merged = _llm_outputs(cases, raw_outputs, patches, field_proofs, attempts)
    merged["enabled"] = enabled
    merged["mode"] = "llm_assisted_and_local_table_proof_patch"
    merged["notes"] = list(dict.fromkeys(notes))
    return merged


def parse_llm_repair_payload(payload: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise LLMRepairParseError(f"repair payload is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise LLMRepairParseError("repair payload must be a JSON object")
    unknown = set(payload) - ALLOWED_TOP_LEVEL_FIELDS
    if unknown:
        raise LLMRepairParseError(f"unknown repair payload fields: {', '.join(sorted(unknown))}")
    action = str(payload.get("action") or "").strip()
    if action not in ALLOWED_ACTIONS:
        raise LLMRepairParseError(f"unknown repair action: {action}")
    if re.search(r"\b(verified|approved|approve|legal)\b", json.dumps(payload, ensure_ascii=False), flags=re.I):
        raise LLMRepairParseError("repair payload attempted to claim verification or approval")
    changes = payload.get("changes") or {}
    if not isinstance(changes, dict):
        raise LLMRepairParseError("changes must be an object")
    unknown_changes = set(changes) - ALLOWED_PATCH_FIELDS
    if unknown_changes:
        raise LLMRepairParseError(f"unknown patch fields: {', '.join(sorted(unknown_changes))}")
    proofs = payload.get("field_proofs") or []
    if not isinstance(proofs, list):
        raise LLMRepairParseError("field_proofs must be a list")
    for proof in proofs:
        if not isinstance(proof, dict):
            raise LLMRepairParseError("each field proof must be an object")
        unknown_proof_fields = set(proof) - ALLOWED_PROOF_FIELDS
        if unknown_proof_fields:
            raise LLMRepairParseError(f"unknown field proof fields: {', '.join(sorted(unknown_proof_fields))}")
        field = str(proof.get("field") or "")
        if field and field not in ALLOWED_PATCH_FIELDS:
            raise LLMRepairParseError(f"field proof references unknown patch field: {field}")
    risk_flags = payload.get("risk_flags") or []
    if not isinstance(risk_flags, list):
        raise LLMRepairParseError("risk_flags must be a list")
    return {
        "action": action,
        "changes": dict(changes),
        "field_proofs": list(proofs),
        "confidence": float(payload.get("confidence") or 0.0),
        "risk_flags": [str(flag) for flag in risk_flags],
        "no_patch_reason": str(payload.get("no_patch_reason") or ""),
    }


def validate_llm_repair_payload(
    payload: dict[str, Any],
    *,
    case: dict[str, Any],
    evidence_by_id: dict[str, SourceSpan],
) -> dict[str, Any]:
    findings: list[str] = []
    if payload.get("action") != "patch":
        return {
            "accepted": False,
            "reason": payload.get("no_patch_reason") or "llm returned no patch",
            "findings": ["no_patch"],
            "changes": {},
            "field_proofs": [],
            "proof_completion_rate": 0.0,
        }
    changes = dict(payload.get("changes") or {})
    if not changes:
        findings.append("patch_has_no_changes")
    if payload.get("risk_flags"):
        findings.append("patch_has_risk_flags")
    field_proofs = [dict(proof) for proof in payload.get("field_proofs") or []]
    proofs_by_field: dict[str, list[dict[str, Any]]] = {}
    for proof in field_proofs:
        proofs_by_field.setdefault(str(proof.get("field") or ""), []).append(proof)
    for field in changes:
        proofs = proofs_by_field.get(field, [])
        if not proofs:
            findings.append(f"{field}_missing_field_proof")
            continue
        if not any(_proof_supports_field(field, changes[field], proof, evidence_by_id) for proof in proofs):
            findings.append(f"{field}_not_supported_by_field_proof")
    if "exception" in changes and not _exception_supported(changes["exception"], proofs_by_field.get("exception", []), evidence_by_id):
        findings.append("exception_not_explicitly_supported")
    accepted = not findings
    return {
        "accepted": accepted,
        "reason": "accepted proof patch" if accepted else "patch failed proof validation",
        "findings": sorted(set(findings)),
        "changes": changes if accepted else {},
        "field_proofs": field_proofs,
        "proof_completion_rate": _proof_completion_rate(changes, proofs_by_field, evidence_by_id),
        "confidence": max(0.0, min(float(payload.get("confidence") or 0.0), 1.0)),
    }


def llm_repair_metrics(outputs: dict[str, Any], *, guarded_repair_promotions: dict[str, Any] | None = None) -> dict[str, Any]:
    metrics = dict(outputs.get("metrics") or {})
    metrics["review_needed_reduction_from_llm_repair"] = int((guarded_repair_promotions or {}).get("review_removed_count") or 0)
    return metrics


def candidate_fields_for_rule(rule: dict[str, Any]) -> dict[str, Any]:
    raw = rule.get("raw") if isinstance(rule.get("raw"), dict) else {}
    candidate = raw.get("candidate") if isinstance(raw.get("candidate"), dict) else {}
    condition = next(iter(rule.get("conditions") or []), "")
    exception = next(iter(rule.get("exceptions") or []), "")
    return {
        "rule_object": candidate.get("rule_object") or raw.get("rule_object") or rule.get("rule_type"),
        "constraint_scope": candidate.get("constraint_scope") or raw.get("constraint_scope") or rule.get("rule_type"),
        "applies_to": candidate.get("applies_to") or raw.get("applies_to") or rule.get("subject"),
        "operator": candidate.get("operator") or raw.get("operator") or rule.get("comparator"),
        "value": candidate.get("value", raw.get("value", rule.get("value"))),
        "unit": candidate.get("unit") or raw.get("unit") or rule.get("unit"),
        "condition": candidate.get("condition") or raw.get("condition") or condition,
        "exception": candidate.get("exception") or raw.get("exception") or exception,
        "evidence_id": candidate.get("evidence_id") or raw.get("evidence_id") or _first_evidence_id(rule),
    }


def repair_prompt(case: dict[str, Any]) -> str:
    return json.dumps(
        {
            "task": "Repair exactly one zoning-rule candidate if evidence proves the missing fields.",
            "rule_id": case.get("rule_id"),
            "current_status": case.get("current_status"),
            "support_gaps": case.get("support_gaps"),
            "candidate_fields": case.get("candidate_fields"),
            "evidence_snippets": case.get("evidence_snippets"),
            "output_schema": {
                "action": "patch | no_patch",
                "changes": {field: "new value" for field in sorted(ALLOWED_PATCH_FIELDS)},
                "field_proofs": [
                    {
                        "field": "one changed field",
                        "evidence_id": "source evidence id",
                        "span_id": "source span id",
                        "quote": "short exact quote from provided evidence",
                        "rationale": "why this quote supports the field",
                    }
                ],
                "confidence": "0.0 to 1.0",
                "risk_flags": [],
                "no_patch_reason": "required when action is no_patch",
            },
            "hard_rules": [
                "Do not decide verification or approval.",
                "Only use provided evidence snippets.",
                "Every changed field must have a field proof.",
                "Return no_patch when proof is incomplete.",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def _llm_outputs(
    cases: list[dict[str, Any]],
    raw_outputs: list[dict[str, Any]],
    patches: list[dict[str, Any]],
    field_proofs: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    patch_count = sum(1 for row in patches if (row.get("payload") or {}).get("action") == "patch")
    safe_count = sum(1 for row in patches if row.get("accepted"))
    changed_field_total = sum(len((row.get("payload") or {}).get("changes") or {}) for row in patches)
    proof_total = sum(
        len(
            {
                str(proof.get("field") or "")
                for proof in (row.get("payload") or {}).get("field_proofs") or []
                if str(proof.get("field") or "") in ((row.get("payload") or {}).get("changes") or {})
            }
        )
        for row in patches
    )
    metrics = {
        "llm_repair_case_count": len(cases),
        "llm_repair_patch_count": patch_count,
        "llm_repair_no_patch_count": len(cases) - patch_count,
        "llm_repair_safe_patch_count": safe_count,
        "llm_repair_rejected_patch_count": max(patch_count - safe_count, 0),
        "field_proof_completion_rate": round(proof_total / changed_field_total, 4) if changed_field_total else 0.0,
        "llm_repair_latency_ms": sum(int(row.get("latency_ms") or 0) for row in raw_outputs),
        "llm_repair_estimated_cost_usd": round(sum(float(row.get("estimated_cost_usd") or 0.0) for row in raw_outputs), 6),
        "review_needed_reduction_from_llm_repair": 0,
    }
    return {
        "enabled": True,
        "mode": "llm_assisted_proof_patch",
        "cases": cases,
        "raw_outputs": raw_outputs,
        "patches": patches,
        "field_proofs": field_proofs,
        "attempts": attempts,
        "evaluations": [],
        "metrics": metrics,
        "notes": [
            "LLM repair proposes candidate patches only.",
            "Validated proof patches still require deterministic verifier rerun before promotion.",
        ],
    }


def _attempt_from_validated_patch(
    case: dict[str, Any],
    validation: dict[str, Any],
    evidence_by_id: dict[str, SourceSpan],
) -> dict[str, Any]:
    rule_id = str(case.get("rule_id") or "")
    changes = dict(validation.get("changes") or {})
    pointers = tuple(_pointer_from_proof(proof, evidence_by_id) for proof in validation.get("field_proofs") or [] if proof.get("field") in changes)
    critique = RepairCritique(
        rule_id=rule_id,
        category=_repair_category(case.get("support_gaps") or []),
        reason="LLM-assisted proof patch prepared for deterministic verifier rerun",
        fields=tuple(sorted(changes)),
        severity="medium",
        support_gaps=tuple(str(gap) for gap in case.get("support_gaps") or []),
    )
    patch = RepairPatch(
        rule_id=rule_id,
        changes=changes,
        evidence_pointers=pointers,
        reason="LLM-assisted proof patch with field-level citations",
        category=critique.category,
    )
    attempt = RepairAttempt(
        attempt_index=1,
        critique=critique,
        query="llm_repair:" + ",".join(str(gap) for gap in case.get("support_gaps") or []),
        patch=patch,
        decision_status="review_needed",
        reason="pending deterministic verifier rerun",
        evidence_bundle_id=str(case.get("case_id") or ""),
    ).to_dict()
    attempt["metadata"] = {
        "repair_source": "llm_repair",
        "field_proof_count": len({str(proof.get("field") or "") for proof in validation.get("field_proofs") or []}),
        "proof_completion_rate": validation.get("proof_completion_rate"),
        "confidence": validation.get("confidence"),
    }
    return attempt


def _local_table_payload(
    case: dict[str, Any],
    evidence_by_id: dict[str, SourceSpan],
    m7_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    fields = dict(case.get("candidate_fields") or {})
    support_gaps = set(str(gap) for gap in case.get("support_gaps") or [])
    if "rule_family_direction_mismatch" in support_gaps:
        return _local_no_patch("rule family direction mismatch is not safe for local table repair")
    candidate = _best_local_table_candidate(fields, m7_candidates, evidence_by_id)
    if candidate is None:
        return _local_no_patch("no exact M7 table-cell candidate matched the review rule")
    evidence_id = str(candidate.get("evidence_id") or "")
    span = evidence_by_id.get(evidence_id)
    if span is None:
        return _local_no_patch("matched M7 table-cell candidate is missing source evidence")
    changes: dict[str, Any] = {"evidence_id": evidence_id}
    applies_to = str(candidate.get("applies_to") or "").strip()
    if applies_to and _norm_text(applies_to) != _norm_text(fields.get("applies_to")):
        changes["applies_to"] = applies_to
    for field in ("value", "unit"):
        value = candidate.get(field)
        if value not in (None, "") and _norm_text(value) != _norm_text(fields.get(field)):
            changes[field] = value
    if str(fields.get("operator") or "").strip() and _norm_text(candidate.get("operator")) != _norm_text(fields.get("operator")):
        changes["operator"] = candidate.get("operator")
    if _should_clear_table_condition(fields, candidate):
        changes["condition"] = ""
    if len(changes) <= 1:
        return _local_no_patch("matched table evidence did not add a stronger field proof")
    quote = _local_table_quote(candidate, span)
    proofs = [
        {
            "field": field,
            "evidence_id": evidence_id,
            "span_id": span.span_id,
            "quote": quote,
            "rationale": "M7 table cell supplies exact row, column, and cell context for this field.",
        }
        for field in changes
    ]
    return {
        "action": "patch",
        "changes": changes,
        "field_proofs": proofs,
        "confidence": 0.95,
        "risk_flags": [],
        "no_patch_reason": "",
    }


def _best_local_table_candidate(
    fields: dict[str, Any],
    candidates: list[dict[str, Any]],
    evidence_by_id: dict[str, SourceSpan],
) -> dict[str, Any] | None:
    matches = [
        candidate
        for candidate in candidates
        if _is_safe_local_table_match(fields, candidate, evidence_by_id)
    ]
    matches.sort(
        key=lambda candidate: (
            _norm_scalar(candidate.get("value")) != _norm_scalar(fields.get("value")),
            -_scope_overlap(fields.get("applies_to"), candidate.get("applies_to")),
            str(candidate.get("candidate_id") or ""),
        )
    )
    return matches[0] if matches else None


def _is_safe_local_table_match(
    fields: dict[str, Any],
    candidate: dict[str, Any],
    evidence_by_id: dict[str, SourceSpan],
) -> bool:
    if str(candidate.get("source_stream") or "") != "native_m7_matrix":
        return False
    if not str(candidate.get("evidence_id") or ""):
        return False
    if _norm_text(candidate.get("rule_object")) != _norm_text(fields.get("rule_object")):
        return False
    if not _safe_local_table_value_match(fields, candidate, evidence_by_id):
        return False
    if _norm_text(candidate.get("unit")) != _norm_text(fields.get("unit")):
        return False
    original_scope = " ".join(str(fields.get(name) or "") for name in ("applies_to", "condition"))
    candidate_scope = str(candidate.get("applies_to") or "")
    if not _scope_can_be_refined(original_scope, candidate_scope):
        return False
    return True


def _safe_local_table_value_match(
    fields: dict[str, Any],
    candidate: dict[str, Any],
    evidence_by_id: dict[str, SourceSpan],
) -> bool:
    if _norm_scalar(candidate.get("value")) == _norm_scalar(fields.get("value")):
        return True
    if _norm_text(fields.get("rule_object")) != "dwelling_units":
        return False
    original_value = _number(fields.get("value"))
    repaired_value = _number(candidate.get("value"))
    if original_value is None or repaired_value is None or repaired_value < original_value:
        return False
    span = evidence_by_id.get(str(candidate.get("evidence_id") or ""))
    if span is None:
        return False
    text = span.text.lower().replace("\n", " ")
    if f"{int(original_value)} to {int(repaired_value)}" in text:
        return True
    if f"{original_value:g} to {repaired_value:g}" in text:
        return True
    return False


def _scope_can_be_refined(original_scope: str, candidate_scope: str) -> bool:
    original = _norm_text(original_scope)
    candidate = _norm_text(candidate_scope)
    original_terms = " ".join(_tokens(original_scope))
    candidate_terms = " ".join(_tokens(candidate_scope))
    if not original or not candidate:
        return False
    if "heritage" in original and "heritage" not in candidate:
        return False
    if "section 219" in original and "section 219" not in candidate:
        return False
    if "small scale multi unit" in original_terms and "small scale multi unit" in candidate_terms:
        return True
    generic_dwelling_scopes = ("residential dwellings", "ground oriented residential dwellings")
    if any(scope in original_terms for scope in generic_dwelling_scopes) and "small scale multi unit" in candidate_terms:
        return True
    return _scope_overlap(original, candidate) >= 0.45


def _should_clear_table_condition(fields: dict[str, Any], candidate: dict[str, Any]) -> bool:
    condition = _norm_text(fields.get("condition"))
    if not condition:
        return False
    if condition in {"r1 district", "on a lot"}:
        return True
    condition_terms = " ".join(_tokens(condition))
    if "total dwelling units on a lot" in condition_terms:
        return True
    return False


def _scope_overlap(left: Any, right: Any) -> float:
    left_tokens = set(_tokens(str(left or "")))
    right_tokens = set(_tokens(str(right or "")))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))


def _local_table_quote(candidate: dict[str, Any], span: SourceSpan) -> str:
    parts = [
        str(candidate.get("rule_object") or ""),
        str(candidate.get("applies_to") or ""),
        span.text,
    ]
    return " | ".join(part for part in parts if part).strip()[:500]


def _number(value: Any) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
    if not match:
        return None
    return float(match.group(0))


def _local_no_patch(reason: str) -> dict[str, Any]:
    return {
        "action": "no_patch",
        "changes": {},
        "field_proofs": [],
        "confidence": 0.0,
        "risk_flags": [],
        "no_patch_reason": reason,
    }


def _pointer_from_proof(proof: dict[str, Any], evidence_by_id: dict[str, SourceSpan]) -> EvidencePointer:
    evidence_id = str(proof.get("evidence_id") or "")
    span = evidence_by_id.get(evidence_id)
    return EvidencePointer(
        evidence_id=evidence_id,
        span_id=str(proof.get("span_id") or (span.span_id if span else "")),
        field_name=str(proof.get("field") or "repair_field"),
        quote=str(proof.get("quote") or "")[:500],
        source_span=span,
        confidence=1.0,
        metadata={"rationale": proof.get("rationale") or "", "repair_source": "llm_repair"},
    )


def _proof_supports_field(
    field: str,
    value: Any,
    proof: dict[str, Any],
    evidence_by_id: dict[str, SourceSpan],
) -> bool:
    evidence_id = str(proof.get("evidence_id") or "")
    quote = str(proof.get("quote") or "")
    span = evidence_by_id.get(evidence_id)
    if not evidence_id or not str(proof.get("span_id") or "") or not quote.strip() or span is None:
        return False
    span_text = _norm_text(span.text)
    quote_text = _norm_text(quote)
    if quote_text not in span_text and not _significant_overlap(quote_text, span_text):
        return False
    if field in {"value", "unit"}:
        return _norm_scalar(value) in _norm_scalar(quote)
    if field == "operator":
        return _operator_supported(str(value or ""), quote)
    if field == "exception":
        return _exception_supported(value, [proof], evidence_by_id)
    if field in SCOPE_PROOF_FIELDS:
        return _scope_like_supported(value, quote)
    if field == "evidence_id":
        return evidence_id == str(value or "")
    return False


def _proof_completion_rate(
    changes: dict[str, Any],
    proofs_by_field: dict[str, list[dict[str, Any]]],
    evidence_by_id: dict[str, SourceSpan],
) -> float:
    if not changes:
        return 0.0
    supported = 0
    for field, value in changes.items():
        if any(_proof_supports_field(field, value, proof, evidence_by_id) for proof in proofs_by_field.get(field, [])):
            supported += 1
    return round(supported / len(changes), 4)


def _exception_supported(value: Any, proofs: list[dict[str, Any]], evidence_by_id: dict[str, SourceSpan]) -> bool:
    if not str(value or "").strip():
        return True
    cues = ("except", "unless", "notwithstanding", "subject to", "provided that")
    for proof in proofs:
        quote = str(proof.get("quote") or "").lower()
        if any(cue in quote for cue in cues) and _scope_like_supported(value, quote):
            evidence_id = str(proof.get("evidence_id") or "")
            if evidence_id in evidence_by_id:
                return True
    return False


def _scope_like_supported(value: Any, quote: str) -> bool:
    value_tokens = set(_tokens(str(value or "")))
    if not value_tokens:
        return True
    quote_tokens = set(_tokens(quote))
    if value_tokens & quote_tokens:
        return True
    structural_cues = {"heading", "table", "row", "column", "section", "district", "zone"}
    return bool(quote_tokens & structural_cues) and bool(len(value_tokens & quote_tokens) >= min(1, len(value_tokens)))


def _operator_supported(operator: str, quote: str) -> bool:
    text = quote.lower()
    op = operator.strip()
    if op in text:
        return True
    aliases = {
        "<=": ("maximum", "max", "up to", "shall not exceed", "not exceed", "no more than"),
        "<": ("less than", "under"),
        ">=": ("minimum", "min", "at least", "not less than", "no less than"),
        ">": ("greater than", "more than"),
        "=": ("must be", "is", "shall be"),
    }
    return any(alias in text for alias in aliases.get(op, ()))


def _support_gaps(rule: dict[str, Any], decision: dict[str, Any], repair_rerun_report: dict[str, Any]) -> list[str]:
    rule_id = str(rule.get("rule_id") or "")
    for attempt in repair_rerun_report.get("attempts", []):
        if str(attempt.get("rule_id") or "") == rule_id:
            gaps = [str(gap) for gap in attempt.get("retry_support_gaps") or []]
            if gaps:
                return gaps
    raw = rule.get("raw") if isinstance(rule.get("raw"), dict) else {}
    return [
        str(gap)
        for gap in (
            decision.get("support_gaps")
            or raw.get("support_gaps")
            or rule.get("support_gaps")
            or []
        )
    ]


def _repair_queries(rule: dict[str, Any], fields: dict[str, Any], gaps: list[str]) -> list[str]:
    base = " ".join(
        str(fields.get(name) or "")
        for name in ("rule_object", "constraint_scope", "applies_to", "operator", "value", "unit", "condition")
    )
    queries = [base]
    gap_set = set(gaps)
    if "value_not_found_in_evidence" in gap_set:
        queries.append(f"{fields.get('value', '')} {fields.get('unit', '')} {fields.get('rule_object', '')}")
    if "unit_not_found_in_evidence" in gap_set:
        queries.append(f"{fields.get('value', '')} {fields.get('unit', '')}")
    if "operator_not_supported" in gap_set:
        queries.extend(
            [
                f"maximum minimum up to at least shall not exceed {fields.get('value', '')} {fields.get('unit', '')}",
                f"{fields.get('rule_object', '')} maximum minimum",
            ]
        )
    if "constraint_scope_not_supported" in gap_set:
        queries.append(f"{fields.get('constraint_scope', '')} heading table row column section")
    if "rule_object_not_supported" in gap_set:
        queries.append(f"{fields.get('rule_object', '')} {fields.get('applies_to', '')} table row")
    if "applies_to_not_supported" in gap_set:
        queries.append(f"{fields.get('applies_to', '')} use subject applies to")
    return [query for query in dict.fromkeys(" ".join(query.split()) for query in queries) if query]


def _failed_repair_priority(report: dict[str, Any]) -> dict[str, int]:
    priority: dict[str, int] = {}
    for index, attempt in enumerate(report.get("attempts", [])):
        if attempt.get("promotion_ready"):
            continue
        rule_id = str(attempt.get("rule_id") or "")
        if rule_id and rule_id not in priority:
            priority[rule_id] = index
    return priority


def _repair_category(gaps: list[str]) -> str:
    gap_set = set(gaps)
    if "constraint_scope_not_supported" in gap_set or "applies_to_not_supported" in gap_set:
        return "missing_scope"
    if "text_condition_not_supported" in gap_set:
        return "missing_condition"
    if "unit_not_found_in_evidence" in gap_set:
        return "unit_mismatch"
    if "value_not_found_in_evidence" in gap_set:
        return "missing_evidence"
    return "general_review"


def _first_evidence_id(rule: dict[str, Any]) -> str:
    pointers = rule.get("evidence_pointers") or []
    for pointer in pointers:
        evidence_id = str(pointer.get("evidence_id") or "")
        if evidence_id:
            return evidence_id
    return ""


def _dedupe_spans(spans: list[SourceSpan]) -> list[SourceSpan]:
    seen: set[str] = set()
    result: list[SourceSpan] = []
    for span in spans:
        evidence_id = str(span.metadata.get("evidence_id") or span.span_id)
        key = f"{evidence_id}:{span.span_id}"
        if key not in seen:
            seen.add(key)
            result.append(span)
    return result


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)*", str(text or "").lower())


def _norm_text(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _norm_scalar(value: Any) -> str:
    text = str(value or "").lower().replace("m²", "m2")
    text = re.sub(r"\s+", "", text)
    return text


def _significant_overlap(quote: str, span_text: str) -> bool:
    quote_tokens = set(_tokens(quote))
    if not quote_tokens:
        return False
    span_tokens = set(_tokens(span_text))
    return len(quote_tokens & span_tokens) / len(quote_tokens) >= 0.8
