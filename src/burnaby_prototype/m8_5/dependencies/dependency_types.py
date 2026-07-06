"""M8.5 dependency enums and helpers."""

from __future__ import annotations


DEPENDENCY_TYPES = frozenset(
    {
        "definition",
        "condition",
        "exception",
        "cross_reference",
        "overlay",
        "covenant",
        "heritage",
        "measurement_method",
        "rule_family",
        "table_context",
        "city_specific_scope",
    }
)

DEPENDENCY_STATUSES = frozenset({"resolved", "unresolved", "conflicting", "not_applicable"})

BLOCKING_STATUSES = frozenset({"unresolved", "conflicting"})


def normalize_reference(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def normalized_lookup_key(value: str) -> str:
    return normalize_reference(value).lower().replace("§", "section")

