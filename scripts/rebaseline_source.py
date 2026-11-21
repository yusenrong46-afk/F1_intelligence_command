"""Re-baseline one city's committed source PDF on purpose (owner decision only).

``make fetch-sources`` never rewrites provenance. When the owner decides to
accept a changed official PDF, this script does it in one reviewed step:

* downloads the URL recorded in ``data/bylaws/<city>/provenance.json`` to
  ``source.pdf`` (the whole PDF, never sliced, so page numbers stay official);
* rewrites only ``sha256``, ``bytes``, ``fetched_at`` and ``page_count``, keeps
  every other field (``pages``, ``pages_rationale`` ...), and records the old
  values under ``rebaselined_from``;
* when the city has a committed M7 run, reports how many committed evidence
  texts still occur on their cited page of the new PDF, so a page shift that
  would invalidate ``pages`` scoping is visible before the commit.

Refuses to write without ``--confirm`` (prints what would change). No model call.
Unlike ``fetch_bylaw.py --url``, it does not drop ``pages`` scoping.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_bylaw  # noqa: E402

MODEL_DIR = "google_gemini_3_1_flash_lite"
KEPT_FROM_OLD = ("sha256", "bytes", "fetched_at", "page_count")


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": fetch_bylaw.USER_AGENT})
    with fetch_bylaw.cookie_opener()(request) as response:
        return response.read()


def new_provenance(old: dict, payload: bytes, page_count: int | None, now: str) -> dict:
    new = dict(old)
    new.pop("rebaselined_from", None)
    new.update({
        "fetched_at": now,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "page_count": page_count,
        "rebaselined_from": {key: old.get(key) for key in KEPT_FROM_OLD},
    })
    return new


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def evidence_page_matches(page_texts: list[str], units: list[dict]) -> tuple[int, int]:
    """(units whose text occurs on their cited page, units with a page and text)."""
    pages = [_norm(t) for t in page_texts]
    found = total = 0
    for unit in units:
        try:
            page = int(unit.get("page"))
        except (TypeError, ValueError):
            continue
        text = _norm(str(unit.get("evidence_text") or ""))
        if not text or not 1 <= page <= len(pages):
            continue
        total += 1
        found += text in pages[page - 1]
    return found, total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", required=True)
    parser.add_argument("--confirm", action="store_true", help="write source.pdf and provenance.json")
    args = parser.parse_args(argv)
    base = ROOT / "data" / "bylaws" / args.city
    old = json.loads((base / "provenance.json").read_text(encoding="utf-8"))
    payload = download(old["url"])
    new = new_provenance(old, payload, fetch_bylaw._page_count(payload),
                         datetime.now(timezone.utc).isoformat(timespec="seconds"))
    print(f"{args.city}: sha256 {old['sha256'][:12]}… -> {new['sha256'][:12]}…, bytes {old['bytes']} -> {new['bytes']}, "
          f"pages in PDF {old.get('page_count')} -> {new['page_count']}, scoped pages kept: {old.get('pages')}")
    units_path = ROOT / "outputs" / "m7_runs" / args.city / MODEL_DIR / "evidence_units.json"
    if units_path.exists():
        from pypdf import PdfReader  # noqa: PLC0415
        import io  # noqa: PLC0415

        texts = [(p.extract_text() or "") for p in PdfReader(io.BytesIO(payload)).pages]
        found, total = evidence_page_matches(texts, json.loads(units_path.read_text(encoding="utf-8")))
        print(f"{args.city}: {found} of {total} committed evidence texts occur on their cited page of the new PDF")
    if new["sha256"] == old["sha256"]:
        print(f"{args.city}: unchanged, nothing to re-baseline")
        return 0
    if not args.confirm:
        print(f"{args.city}: dry run, nothing written (add --confirm after the owner decides)")
        return 0
    (base / "source.pdf").write_bytes(payload)
    (base / "provenance.json").write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")
    print(f"{args.city}: wrote source.pdf and provenance.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
