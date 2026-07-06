"""Exception helpers for M8 dependency analysis."""

from __future__ import annotations

import re
from typing import Any


_EXCEPTION_RE = re.compile(r"\b(except|unless|notwithstanding|subject to|despite)\b", re.I)


def exception_dependencies(rule: dict[str, Any] | str) -> list[str]:
    text = rule if isinstance(rule, str) else " ".join(str(rule.get(k) or "") for k in ("exception", "condition", "rule_sentence"))
    if _EXCEPTION_RE.search(str(text or "")):
        return ["exception_or_override_dependency"]
    return []
