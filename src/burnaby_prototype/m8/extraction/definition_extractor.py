"""Small deterministic definition-dependency detector."""

from __future__ import annotations

import re
from typing import Any


_DEFINITION_RE = re.compile(r"\bmeans\b|\bdefinition\b|\bdefined\s+as\b", re.I)


def definition_dependencies(rule: dict[str, Any] | str) -> list[str]:
    text = rule if isinstance(rule, str) else " ".join(str(rule.get(k) or "") for k in ("condition", "exception", "rule_sentence"))
    if _DEFINITION_RE.search(str(text or "")):
        return ["definition_dependency"]
    return []
