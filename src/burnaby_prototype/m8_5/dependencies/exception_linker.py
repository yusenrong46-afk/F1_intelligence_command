"""Exception dependency linker for M8.5."""

from __future__ import annotations

import re


_EXCEPTION_RE = re.compile(
    r"\b(?P<cue>except|unless|notwithstanding|save and except)\b(?P<body>[^.;]*)",
    re.IGNORECASE,
)


class ExceptionLinker:
    def extract_exceptions(self, text: str) -> list[str]:
        refs = []
        seen = set()
        for match in _EXCEPTION_RE.finditer(str(text or "")):
            reference = " ".join(f"{match.group('cue')} {match.group('body')}".split())
            key = reference.lower()
            if reference and key not in seen:
                seen.add(key)
                refs.append(reference)
        return refs

