"""Deterministic query planning for M8 retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_SYNONYMS = {
    "height": ("maximum height", "building height", "how tall"),
    "setback": ("yard setback", "property line", "lot line"),
    "coverage": ("lot coverage", "impervious surface", "site coverage"),
    "unit": ("dwelling unit", "suite", "density"),
    "area": ("lot area", "floor area", "gross floor area"),
    "fsr": ("floor space ratio", "floor area ratio"),
}


@dataclass(frozen=True)
class PlannedQuery:
    original: str
    exact_phrases: tuple[str, ...]
    semantic_variants: tuple[str, ...]
    filters: dict[str, Any]

    def all_queries(self) -> tuple[str, ...]:
        seen: list[str] = []
        for value in (self.original, *self.exact_phrases, *self.semantic_variants):
            clean = str(value or "").strip()
            if clean and clean not in seen:
                seen.append(clean)
        return tuple(seen)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original": self.original,
            "exact_phrases": list(self.exact_phrases),
            "semantic_variants": list(self.semantic_variants),
            "filters": dict(self.filters),
        }


def plan_query(question: str, *, city: str | None = None, rule_family: str | None = None, page: int | None = None) -> PlannedQuery:
    tokens = re.findall(r"[a-z0-9]+(?:\.[0-9]+)*", str(question or "").lower())
    exact: list[str] = []
    semantic: list[str] = []
    for token in tokens:
        if token in _SYNONYMS:
            semantic.extend(_SYNONYMS[token])
    if rule_family:
        exact.append(str(rule_family).replace("_", " "))
    if "r1" in tokens and "r1" not in exact:
        exact.append("R1")
    filters: dict[str, Any] = {}
    if city:
        filters["city"] = city
    if rule_family:
        filters["rule_family"] = rule_family
    if page is not None:
        filters["page"] = page
    return PlannedQuery(
        original=str(question or ""),
        exact_phrases=tuple(dict.fromkeys(exact)),
        semantic_variants=tuple(dict.fromkeys(semantic)),
        filters=filters,
    )
