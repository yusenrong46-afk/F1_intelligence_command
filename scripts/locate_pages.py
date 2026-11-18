"""Find which pages of an official bylaw PDF hold a zone, to choose PAGES (L4).

Downloads the PDF to a temporary file (nothing in the repo is written), lists
the pages whose text matches a regex, and suggests the largest run of matching
pages (gaps of up to ``--max-gap`` pages are bridged) as ``PAGES=a-b`` for
``make onboard``. Read the suggestion against the PDF before using it.

Usage: ``python scripts/locate_pages.py --url <pdf url> --pattern '<regex>'``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_bylaw  # noqa: E402


def matching_pages(pdf: Path, pattern: str) -> list[int]:
    from pypdf import PdfReader  # noqa: PLC0415

    regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    return [i + 1 for i, page in enumerate(PdfReader(str(pdf)).pages) if regex.search(page.extract_text() or "")]


def largest_run(pages: list[int], max_gap: int = 1) -> tuple[int, int] | None:
    if not pages:
        return None
    runs: list[list[int]] = [[pages[0]]]
    for page in pages[1:]:
        if page - runs[-1][-1] <= max_gap + 1:
            runs[-1].append(page)
        else:
            runs.append([page])
    best = max(runs, key=lambda run: (len(run), -run[0]))
    return best[0], best[-1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--max-gap", type=int, default=1)
    args = parser.parse_args(argv)
    request = urllib.request.Request(args.url, headers={"User-Agent": fetch_bylaw.USER_AGENT})
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "source.pdf"
        with fetch_bylaw.cookie_opener()(request) as response:
            pdf.write_bytes(response.read())
        pages = matching_pages(pdf, args.pattern)
    run = largest_run(pages, args.max_gap)
    print(json.dumps({"pattern": args.pattern, "pages": pages, "suggested": f"{run[0]}-{run[1]}" if run else None}))
    return 0 if run else 1


if __name__ == "__main__":
    raise SystemExit(main())
