"""Assert the README's first screen meets the portfolio standard (L1).

The first screen is everything before the first ``## `` heading. It must hold:

1. one sentence saying what the project does and for whom;
2. one dated result with its number (an ISO date and a number on one line);
3. one image whose file exists;
4. how to see it: a demo link or one command (``make demo``).

Every relative link and image in the whole README must resolve to a file or
directory in the repository. Exit 1 and list the problems otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
DATE = re.compile(r"\b20\d\d-\d\d-\d\d\b")
NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")
FOR_WHOM = re.compile(r"\bfor\b", re.IGNORECASE)
FIRST_SCREEN_MAX_LINES = 40


def first_screen(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    for index, line in enumerate(lines):
        if index > 0 and line.startswith("## "):
            break
        out.append(line)
    return "\n".join(out[:FIRST_SCREEN_MAX_LINES])


def _is_relative(target: str) -> bool:
    return not re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE) and not target.startswith("#")


def check(readme: Path) -> list[str]:
    text = readme.read_text(encoding="utf-8")
    screen = first_screen(text)
    problems: list[str] = []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", screen) if p.strip()]
    prose = [p for p in paragraphs if not p.startswith(("#", "!", "```", "|", "<!--", "-"))]
    if not prose or not prose[0].rstrip().endswith(".") or not FOR_WHOM.search(prose[0]):
        problems.append("first screen: first paragraph must be a sentence saying what it does and for whom")

    dated = [line for line in screen.splitlines() if DATE.search(line) and NUMBER.search(DATE.sub("", line))]
    if not dated:
        problems.append("first screen: no dated result (an ISO date and a number on one line)")

    images = IMAGE.findall(screen)
    if not images:
        problems.append("first screen: no image")
    for target in images:
        if _is_relative(target) and not (readme.parent / target.split("#")[0]).exists():
            problems.append(f"first screen: image does not exist: {target}")

    if "make demo" not in screen and not re.search(r"https?://\S*(demo|streamlit\.app)", screen):
        problems.append("first screen: no way to see it (a demo link or `make demo`)")

    for target in LINK.findall(text):
        if not _is_relative(target):
            continue
        path = target.split("#", 1)[0]
        if path and not (readme.parent / path).exists():
            problems.append(f"broken relative link: {target}")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    readme = Path(args[0]) if args else ROOT / "README.md"
    problems = check(readme)
    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"README first screen OK ({readme.relative_to(ROOT) if readme.is_relative_to(ROOT) else readme})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
