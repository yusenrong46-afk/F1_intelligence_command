"""LLM-assisted M8.5 repair proposals.

The LLM repair layer is proposer-only. It can build proof patches for verifier
reruns, but it cannot promote a rule.
"""

from .llm_repair import (
    FixtureRepairClient,
    LLMRepairError,
    LLMRepairParseError,
    OpenRouterRepairClient,
    build_llm_repair_cases,
    disabled_llm_repair_outputs,
    llm_repair_metrics,
    merge_repair_outputs,
    parse_llm_repair_payload,
    run_local_table_proof_repair,
    run_llm_repair,
    validate_llm_repair_payload,
)

__all__ = [
    "FixtureRepairClient",
    "LLMRepairError",
    "LLMRepairParseError",
    "OpenRouterRepairClient",
    "build_llm_repair_cases",
    "disabled_llm_repair_outputs",
    "llm_repair_metrics",
    "merge_repair_outputs",
    "parse_llm_repair_payload",
    "run_local_table_proof_repair",
    "run_llm_repair",
    "validate_llm_repair_payload",
]
