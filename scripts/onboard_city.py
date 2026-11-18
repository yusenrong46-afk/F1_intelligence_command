"""Set up a new city from config, with no source edits (L4 onboarding kit).

``make onboard CITY=<id> URL=<official PDF URL> [PAGES=a-b] [LOCATE=<regex>]``
runs these steps and times each one:

1. **config**: create ``configs/<id>.json`` from ``configs/_template.json``
   (or keep an existing reviewed config unchanged);
2. **source**: when ``data/bylaws/<id>/provenance.json`` already exists, fetch
   its URL and require the committed SHA-256 (provenance is never rewritten);
   otherwise download ``URL`` and record new provenance with the page scope;
3. **validate_config**: ``scripts/validate_config.py configs/<id>.json``;
4. **locate** (optional): list the pages whose text matches ``LOCATE``, to
   choose ``PAGES``;
5. **page_text**: write the scoped pages' text to
   ``outputs/onboarding/<id>/source_pages.txt`` (gitignored) for gold drafting;
6. **dry_run**: ``scripts/run_m7_bakeoff.py --city <id> --models
   google/gemini-3.1-flash-lite --dry-run`` with no API key in the
   environment, writing under ``outputs/onboarding/<id>/``;
7. **gold_draft**: create ``benchmark/gold/<id>_gold_rules.DRAFT.json`` if it
   does not exist (rules marked ``agent_draft_unreviewed``; never overwritten).

It then writes ``outputs/onboarding/<id>/ONBOARDING_REPORT.md`` and
``onboarding_summary.json``. A step that cannot run (for example the source
hash no longer matches) is recorded with its reason and the steps that depend
on it are recorded as NOT RUN. Exit 0 when every step that ran passed, else 1.
No model call, no paid call.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_bylaw  # noqa: E402

MODEL = "google/gemini-3.1-flash-lite"
SECRET_ENV = ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY")
PLACEHOLDER = re.compile(r"__[A-Z_]+__")


class Step:
    def __init__(self, name: str) -> None:
        self.name = name
        self.status = "NOT RUN"
        self.seconds: float | None = None
        self.detail = ""

    def as_dict(self) -> dict[str, Any]:
        return {"step": self.name, "status": self.status, "seconds": self.seconds, "detail": self.detail}


def _parse_pages(pages: str | None) -> list[int] | None:
    if not pages:
        return None
    match = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", pages)
    if not match or int(match.group(1)) > int(match.group(2)):
        raise SystemExit(f"PAGES must look like 12-34, got {pages!r}")
    return [int(match.group(1)), int(match.group(2))]


def _timed(step: Step, fn: Callable[[], tuple[str, str]]) -> bool:
    started = time.perf_counter()
    try:
        step.status, step.detail = fn()
    except Exception as exc:  # noqa: BLE001 - every failure is reported, none hidden
        step.status, step.detail = "FAIL", f"{type(exc).__name__}: {exc}"
    step.seconds = round(time.perf_counter() - started, 2)
    return step.status == "PASS"


def make_config(city: str, url: str | None, args: argparse.Namespace) -> tuple[str, str]:
    path = ROOT / "configs" / f"{city}.json"
    if path.exists():
        return "PASS", f"kept existing reviewed config configs/{city}.json unchanged"
    template = json.loads((ROOT / "configs" / "_template.json").read_text(encoding="utf-8"))
    fills = {
        "__CITY__": args.name or city.split("_")[0].title(),
        "__ZONE__": args.zone or "__ZONE__",
        "__BYLAW__": args.bylaw or "__BYLAW__",
        "__SOURCE_URL__": url or "__SOURCE_URL__",
    }
    text = json.dumps(template, indent=2, ensure_ascii=False)
    for key, value in fills.items():
        text = text.replace(key, value.replace('"', "'"))
    config = json.loads(text)
    config["known_aliases"] = list(args.alias or [])
    config["_note"] = (
        f"Created by make onboard on {datetime.now(timezone.utc).date().isoformat()} from configs/_template.json. "
        "Exploratory: no reviewed gold benchmark. " + template["_note"]
    )
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    left = sorted(set(PLACEHOLDER.findall(path.read_text(encoding="utf-8"))))
    return "PASS", f"created configs/{city}.json from the template" + (
        f"; placeholders left to fill: {', '.join(left)}" if left else ""
    )


def get_source(city: str, url: str | None, pages: list[int] | None, rationale: str | None) -> tuple[str, str]:
    base = ROOT / "data" / "bylaws" / city
    provenance_path = base / "provenance.json"
    if provenance_path.exists():
        try:
            result = fetch_bylaw.fetch_verified_source(city)
        except fetch_bylaw.ProvenanceMismatch as exc:
            return "FAIL", f"source hash no longer matches committed provenance (not rewritten): {exc}"
        except OSError as exc:
            return "FAIL", f"source unavailable: {type(exc).__name__}: {exc}"
        return "PASS", f"{result['status']}: sha256 {result['sha256']} matches committed provenance"
    if not url:
        return "FAIL", "no committed provenance and no URL given"
    result = fetch_bylaw.fetch_bylaw(city, url)  # whole PDF, so page numbers stay the official ones
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if pages:
        provenance["pages"] = pages
        provenance["pages_rationale"] = rationale or "Scoped by make onboard PAGES."
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return "PASS", f"fetched {provenance['bytes']} bytes, sha256 {provenance['sha256']}, {provenance['page_count']} pages; recorded new provenance"


def validate(city: str) -> tuple[str, str]:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/validate_config.py", f"configs/{city}.json"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    last = (proc.stdout.strip().splitlines() or [""])[-1]
    return ("PASS" if proc.returncode == 0 else "FAIL"), f"exit {proc.returncode}: {last or proc.stderr.strip()[-300:]}"


def _page_texts(city: str) -> list[str]:
    from pypdf import PdfReader  # noqa: PLC0415

    reader = PdfReader(str(ROOT / "data" / "bylaws" / city / "source.pdf"))
    return [(page.extract_text() or "") for page in reader.pages]


def locate(city: str, pattern: str, found: dict[str, Any]) -> tuple[str, str]:
    regex = re.compile(pattern, re.IGNORECASE)
    hits = [index + 1 for index, text in enumerate(_page_texts(city)) if regex.search(text)]
    found["locate_pages"] = hits
    shown = ", ".join(str(p) for p in hits[:60]) + (" ..." if len(hits) > 60 else "")
    return "PASS", f"{len(hits)} page(s) match /{pattern}/: {shown or 'none'}"


def page_text(city: str, out: Path) -> tuple[str, str]:
    provenance = json.loads((ROOT / "data" / "bylaws" / city / "provenance.json").read_text(encoding="utf-8"))
    texts = _page_texts(city)
    pages = provenance.get("pages")
    first, last = (pages[0], pages[1]) if isinstance(pages, list) and len(pages) == 2 and all(isinstance(p, int) for p in pages) else (1, len(texts))
    chunks = [f"===== page {n} =====\n{texts[n - 1]}" for n in range(first, min(last, len(texts)) + 1)]
    (out / "source_pages.txt").write_text("\n".join(chunks) + "\n", encoding="utf-8")
    return "PASS", f"pages {first}-{last} written to source_pages.txt (gitignored)"


def dry_run(city: str, out: Path, found: dict[str, Any]) -> tuple[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in SECRET_ENV}
    run_root = out / "bakeoff_dry_run"
    cmd = [
        sys.executable, "scripts/run_m7_bakeoff.py", "--city", city, "--models", MODEL, "--dry-run",
        # Keep everything this run writes inside outputs/onboarding/<id>/:
        # the wrapper's default --out-root is outputs/m7_runs (argparse: last wins).
        "--out-root", str(run_root), "--db", str(out / "m7_cache.sqlite"), "--no-source-corpus",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, check=False)  # noqa: S603
    (out / "dry_run.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    summaries = sorted(run_root.rglob("extraction_summary.json")) if run_root.exists() else []
    if summaries:
        summary = json.loads(summaries[0].read_text(encoding="utf-8"))
        found["dry_run_summary"] = {k: v for k, v in summary.items() if isinstance(v, (int, float, str, bool)) or v is None}
    cost = sorted(run_root.rglob("model_cost_report.json")) if run_root.exists() else []
    if cost:
        found["dry_run_cost"] = json.loads(cost[0].read_text(encoding="utf-8")).get("estimated_cost_usd")
    tail = " | ".join(line for line in (proc.stdout + proc.stderr).strip().splitlines()[-3:])
    return ("PASS" if proc.returncode == 0 else "FAIL"), f"exit {proc.returncode}; no API key in env; log dry_run.log; {tail[-400:]}"


def gold_draft(city: str, args: argparse.Namespace) -> tuple[str, str]:
    path = ROOT / "benchmark" / "gold" / f"{city}_gold_rules.DRAFT.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return "PASS", f"kept existing draft ({len(data.get('rules', []))} rules)"
    draft = {
        "city": city,
        "status": "exploratory",
        "label_source": "agent_draft_unreviewed",
        "note": "Draft gold rules. Not a benchmark until a person reviews every rule against the source PDF. "
        "Each rule needs source_page and an exact quoted span.",
        "source": f"data/bylaws/{city}/provenance.json",
        "rules": [],
    }
    path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return "PASS", "created an empty draft for review"


def config_knobs(city: str) -> list[str]:
    config = json.loads((ROOT / "configs" / f"{city}.json").read_text(encoding="utf-8"))
    verification = config.get("verification", {})
    knobs = [f"{key} = {json.dumps(value)}" for key, value in verification.items() if key != "rule_family_direction"]
    knobs += [f"direction {k} = {v}" for k, v in sorted(verification.get("rule_family_direction", {}).items())]
    nonempty = [k for k, v in (config.get("normalization") or {}).items() if v]
    knobs.append(f"normalization knobs set: {', '.join(nonempty) or 'none (all empty)'}")
    return knobs


def write_report(city: str, out: Path, steps: list[Step], found: dict[str, Any], args: argparse.Namespace) -> None:
    provenance_path = ROOT / "data" / "bylaws" / city / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8")) if provenance_path.exists() else {}
    lines = [
        f"# Onboarding report: {city}",
        "",
        "Status: **exploratory**. This city has no reviewed gold benchmark, so no",
        "number from it may be reported as accuracy.",
        "",
        f"Command: `make onboard CITY={city}" + (f" URL={args.url}" if args.url else "")
        + (f" PAGES={args.pages}" if args.pages else "") + "`",
        f"Run on: {datetime.now(timezone.utc).date().isoformat()} (timings below are wall-clock seconds)",
        "",
        "## Source",
        "",
        f"- URL: {provenance.get('url', 'not recorded')}",
        f"- SHA-256 (committed provenance): `{provenance.get('sha256', 'not recorded')}`",
        f"- Pages in PDF: {provenance.get('page_count', 'not recorded')}; scoped pages: {provenance.get('pages') or 'whole PDF'}",
        f"- Fetched at (provenance): {provenance.get('fetched_at', 'not recorded')}",
        "",
        "## Steps",
        "",
        "| Step | Status | Seconds | Detail |",
        "|---|---|---:|---|",
    ]
    for step in steps:
        detail = step.detail.replace(str(ROOT) + "/", "").replace("|", "/").replace("\n", " ")
        lines.append(f"| {step.name} | {step.status} | {'' if step.seconds is None else step.seconds} | {detail} |")
    if found.get("dry_run_summary"):
        lines += ["", "## Dry run summary (no model call)", ""]
        lines += [f"- {k}: {v}" for k, v in sorted(found["dry_run_summary"].items())]
        if "dry_run_cost" in found:
            lines.append(f"- estimated_cost_usd reported by the dry run: {found['dry_run_cost']}")
    lines += [
        "",
        "## NOT RUN",
        "",
        f"- Real-model extraction (`make extract CITY={city} CONFIRM_PAID=yes`): paid, not authorized here.",
        "- Verification of model-extracted candidates and any benchmark score: needs the extraction above and a reviewed gold set.",
        f"- Human review of `benchmark/gold/{city}_gold_rules.DRAFT.json`.",
        "",
        "## Config knobs",
        "",
        "Every knob is a reviewed trust decision (see `scripts/validate_config.py`).",
        "",
    ]
    lines += [f"- {knob}" for knob in config_knobs(city)] if (ROOT / "configs" / f"{city}.json").exists() else ["- config not created"]
    lines += [
        "",
        "## Roll back",
        "",
        f"Delete `configs/{city}.json`, `data/bylaws/{city}/`, `outputs/onboarding/{city}/` and",
        f"`benchmark/gold/{city}_gold_rules.DRAFT.json` (only those this run created).",
        "",
    ]
    (out / "ONBOARDING_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    summary = {"city": city, "steps": [s.as_dict() for s in steps], **{k: v for k, v in found.items()}}
    (out / "onboarding_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", required=True, help="city id, e.g. toronto_rd")
    parser.add_argument("--url", default=None, help="official bylaw PDF URL (new city only)")
    parser.add_argument("--pages", default=None, help="page scope a-b, recorded in new provenance")
    parser.add_argument("--pages-rationale", default=None)
    parser.add_argument("--locate", default=None, help="regex; list the pages that match, to choose --pages")
    parser.add_argument("--name", default=None)
    parser.add_argument("--zone", default=None)
    parser.add_argument("--bylaw", default=None)
    parser.add_argument("--alias", action="append")
    args = parser.parse_args(argv)
    city = args.city
    if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", city):
        raise SystemExit(f"CITY must be lower_snake_case, got {city!r}")
    pages = _parse_pages(args.pages)
    out = ROOT / "outputs" / "onboarding" / city
    out.mkdir(parents=True, exist_ok=True)

    steps = {name: Step(name) for name in ("config", "source", "validate_config", "locate", "page_text", "dry_run", "gold_draft")}
    found: dict[str, Any] = {}
    config_ok = _timed(steps["config"], lambda: make_config(city, args.url, args))
    source_ok = _timed(steps["source"], lambda: get_source(city, args.url, pages, args.pages_rationale))
    if config_ok:
        _timed(steps["validate_config"], lambda: validate(city))
    else:
        steps["validate_config"].detail = "config step failed"
    if args.locate and source_ok:
        _timed(steps["locate"], lambda: locate(city, args.locate, found))
    else:
        steps["locate"].detail = "no LOCATE given" if not args.locate else "needs the source step"
    if source_ok:
        _timed(steps["page_text"], lambda: page_text(city, out))
    else:
        steps["page_text"].detail = "needs a source PDF that matches provenance"
    if source_ok and steps["validate_config"].status == "PASS":
        _timed(steps["dry_run"], lambda: dry_run(city, out, found))
    else:
        steps["dry_run"].detail = "needs a source PDF that matches provenance and a valid config"
    _timed(steps["gold_draft"], lambda: gold_draft(city, args))

    write_report(city, out, list(steps.values()), found, args)
    for step in steps.values():
        print(f"{step.status:8} {step.name:16} {step.seconds if step.seconds is not None else '':>7}  {step.detail[:160]}")
    print(f"report: outputs/onboarding/{city}/ONBOARDING_REPORT.md")
    return 0 if all(s.status in {"PASS", "NOT RUN"} for s in steps.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
