"""M8 chatbot answer policy."""

from __future__ import annotations


UNSUPPORTED_RESPONSE = (
    "I cannot support that from the M8 artifacts. M8 can explain verified, "
    "review-needed, repaired, and context-required records, but it cannot invent "
    "or approve rules."
)


def refuses_mutation(question: str) -> bool:
    text = str(question or "").lower()
    return any(
        cue in text
        for cue in (
            "approve this rule",
            "verify this rule",
            "promote this rule",
            "change status",
            "mark as verified",
        )
    )
