"""Check that every rule in a draft gold file quotes its cited page exactly (L4).

A draft gold rule (``benchmark/gold/<id>_gold_rules.DRAFT.json``) must carry
``source_page``, a ``quote`` and ``"label_source": "agent_draft_unreviewed"``.
This script reads the page text that ``make onboard`` writes to
``outputs/onboarding/<id>/source_pages.txt`` (``===== page N =====`` markers)
and checks that each quote occurs on its cited page, comparing with whitespace
collapsed (PDF text extraction breaks lines at arbitrary points). It also checks
that the rule's ``value`` occurs in its quote (thousands commas ignored;
1 to 5 may be written as words). It proves the quote is real; it
does not prove the label is right, which is the human review step.

Exit 0 when every rule passes, 1 otherwise. ``--min-rules`` fails a file with
fewer rules than required.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PAGE_RE = re.compile(r"^===== page (\d+) =====$", re.MULTILINE)
REQUIRED = ("gold_id", "rule_object", "constraint_type", "value", "unit", "operator", "source_page", "quote", "label_source")


def _norm(text: str) -> str:
    return " ".join(text.split())


NUMBER_WORDS = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five"}


def _value_in_quote(value: str, quote: str) -> bool:
    """The value occurs in the quote, as written, without thousands commas, or as a small number word."""
    if value in quote or value in quote.replace(",", ""):
        return True
    word = NUMBER_WORDS.get(value)
    return bool(word) and re.search(rf"\b{word}\b", quote, re.IGNORECASE) is not None


def parse_pages(text: str) -> dict[int, str]:
    marks = list(PAGE_RE.finditer(text))
    pages = {}
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        pages[int(mark.group(1))] = _norm(text[mark.end():end])
    return pages


def check(draft: dict, pages: dict[int, str], min_rules: int = 0) -> list[str]:
    problems: list[str] = []
    rules = draft.get("rules", [])
    if draft.get("label_source") != "agent_draft_unreviewed":
        problems.append("file-level label_source is not agent_draft_unreviewed")
    if len(rules) < min_rules:
        problems.append(f"{len(rules)} rules, fewer than the required {min_rules}")
    seen: set[str] = set()
    for rule in rules:
        rid = rule.get("gold_id", "?")
        missing = [key for key in REQUIRED if rule.get(key) in (None, "")]
        if missing:
            problems.append(f"{rid}: missing {', '.join(missing)}")
            continue
        if rid in seen:
            problems.append(f"{rid}: duplicate gold_id")
        seen.add(rid)
        if rule["label_source"] != "agent_draft_unreviewed":
            problems.append(f"{rid}: label_source is {rule['label_source']!r}")
        page = pages.get(rule["source_page"])
        if page is None:
            problems.append(f"{rid}: page {rule['source_page']} is not in the page text")
            continue
        quote = _norm(rule["quote"])
        if quote not in page:
            problems.append(f"{rid}: quote not found on page {rule['source_page']}: {quote[:60]!r}")
        if not _value_in_quote(str(rule["value"]), quote):
            problems.append(f"{rid}: value {rule['value']!r} does not occur in its quote")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--pages", type=Path, required=True, help="source_pages.txt written by make onboard")
    parser.add_argument("--min-rules", type=int, default=0)
    args = parser.parse_args(argv)
    draft = json.loads(args.gold.read_text(encoding="utf-8"))
    pages = parse_pages(args.pages.read_text(encoding="utf-8"))
    problems = check(draft, pages, args.min_rules)
    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"draft gold OK: {len(draft['rules'])} rules, every quote found on its cited page ({args.gold.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
