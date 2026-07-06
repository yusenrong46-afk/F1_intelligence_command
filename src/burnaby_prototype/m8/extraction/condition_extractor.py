"""Condition helpers for M8 dependency analysis."""

from __future__ import annotations

import re
from typing import Any


_CONDITION_RE = re.compile(r"\b(where|when|if|subject to|provided that|for lots?|for parcels?)\b", re.I)


def material_conditions(rule: dict[str, Any]) -> list[str]:
    values = [str(rule.get("condition") or "")]
    sentence = str(rule.get("rule_sentence") or "")
    if _CONDITION_RE.search(sentence):
        values.append(sentence)
    return [value.strip() for value in values if value.strip()]
