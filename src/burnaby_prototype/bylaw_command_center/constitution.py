"""F1 safety constitution constants."""

from __future__ import annotations


F1_CONSTITUTION_RULES: tuple[str, ...] = (
    "Source documents are ground truth.",
    "Extraction proposes candidate rules.",
    "RAG retrieves evidence, not truth.",
    "Repair proposes patches, never approval.",
    "Verification is the only promotion authority.",
    "Chatbot explains and navigates, but cannot verify or approve.",
    "GIS and compliance consume verified-only rules.",
    "No dry-run result may be described as a real measured result.",
    "Every upgrade must be proven by benchmark or clearly labeled exploratory.",
    "A city without gold benchmark is exploratory only.",
)


def constitution_text() -> str:
    return "\n".join(f"{index}. {rule}" for index, rule in enumerate(F1_CONSTITUTION_RULES, start=1))
