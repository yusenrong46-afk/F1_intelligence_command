"""Check docs/WALKTHROUGH.md (L5): ten questions, short answers, live code pointers.

Rules checked:

* exactly ten ``## N. ...`` question headings, numbered 1 to 10;
* each answer (the text under a heading) is under 120 words;
* each answer has at least one pointer written as ```file::symbol```;
* every pointed-to file exists, and the symbol is defined there:
  - ``.py``: ``def symbol``, ``class symbol`` or ``symbol =`` / ``symbol:`` at any indent;
  - ``.json``: ``"symbol"`` appears as a key.

Exit 0 when all pass, 1 otherwise (problems on stderr).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTION_RE = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)
POINTER_RE = re.compile(r"`([\w./-]+)::([A-Za-z_][\w]*)`")
MAX_WORDS = 120
EXPECTED_QUESTIONS = 10


def symbol_defined(path: Path, symbol: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        pattern = rf"^\s*(?:async\s+def|def|class)\s+{re.escape(symbol)}\b|^\s*{re.escape(symbol)}\s*[:=]"
        return re.search(pattern, text, re.MULTILINE) is not None
    if path.suffix == ".json":
        return f'"{symbol}"' in text
    return symbol in text


def sections(text: str) -> list[tuple[int, str, str]]:
    matches = list(QUESTION_RE.finditer(text))
    out = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((int(match.group(1)), match.group(2).strip(), text[match.end():end].strip()))
    return out


def check(text: str, root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    found = sections(text)
    numbers = [n for n, _, _ in found]
    if numbers != list(range(1, EXPECTED_QUESTIONS + 1)):
        problems.append(f"expected questions numbered 1..{EXPECTED_QUESTIONS}, found {numbers}")
    for number, question, body in found:
        words = len(body.split())
        if words >= MAX_WORDS:
            problems.append(f"Q{number} answer has {words} words (limit: under {MAX_WORDS})")
        pointers = POINTER_RE.findall(body)
        if not pointers:
            problems.append(f"Q{number} ({question}) has no `file::symbol` pointer")
        for rel, symbol in pointers:
            path = root / rel
            if not path.is_file():
                problems.append(f"Q{number}: {rel} does not exist")
            elif not symbol_defined(path, symbol):
                problems.append(f"Q{number}: {symbol} is not defined in {rel}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", type=Path, default=ROOT / "docs" / "WALKTHROUGH.md")
    args = parser.parse_args(argv)
    text = args.file.read_text(encoding="utf-8")
    problems = check(text)
    if problems:
        for problem in problems:
            print(f"FAIL {problem}", file=sys.stderr)
        return 1
    pointers = len(POINTER_RE.findall(text))
    print(f"walkthrough OK: {len(sections(text))} questions, {pointers} pointers, every answer under {MAX_WORDS} words")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
