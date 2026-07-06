"""M8 additive upgrade layer.

M8 is intentionally layered beside M7. It can structure candidates, retrieve
more context, propose repairs, and explain analytics, but it does not replace
the deterministic verifier or write GIS-approved rules directly.
"""

from .extraction.rule_schema import (
    EvidenceBundle,
    EvidencePointer,
    M8RunSummary,
    RepairAttempt,
    RepairCritique,
    RepairPatch,
    SourceSpan,
    StructuredRule,
    VerificationDecision,
)

__all__ = [
    "EvidenceBundle",
    "EvidencePointer",
    "M8RunSummary",
    "RepairAttempt",
    "RepairCritique",
    "RepairPatch",
    "SourceSpan",
    "StructuredRule",
    "VerificationDecision",
]
