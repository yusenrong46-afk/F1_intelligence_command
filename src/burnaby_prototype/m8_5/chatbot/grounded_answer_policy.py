"""M8.5 grounded answer policy."""

from __future__ import annotations


UNSUPPORTED_RESPONSE = (
    "not available: the M8.5 artifacts do not support that legal conclusion. "
    "M8.5 can explain artifact status, table lineage, dependencies, repair "
    "evaluations, and reviewer workflow, but it cannot approve or verify rules."
)


def refuses_legal_override(question: str) -> bool:
    text = str(question or "").lower()
    return any(
        cue in text
        for cue in (
            "approve this rule",
            "verify this rule",
            "promote this rule",
            "change status",
            "mark as verified",
            "override verifier",
            "export to gis",
        )
    )


def missing_response(*artifact_names: str) -> str:
    wanted = ", ".join(name for name in artifact_names if name) or "required artifacts"
    return f"not available: missing {wanted}."
