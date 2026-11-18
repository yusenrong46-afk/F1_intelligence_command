"""Check the L5 presentation documents.

* ``docs/CASE_STUDY.md``:
  - carries the ``agent_draft_unreviewed`` label;
  - has the customer-loop sections in order: Problem, Discovery, Scope, Build,
    Demo-back, Result, What I would change;
  - cites only the four allowed sources, each as ``[source: <file> §<section>]``
    where the file exists and has a heading that starts with that section;
  - in sections 1 to 6, every paragraph that states a number is cited, either in
    the paragraph or by a citation-only paragraph right after it (for tables);
  - says "not recorded" where the sources are silent about the client.
* ``docs/DEMO_SCRIPT.md``: has a 90-second demo and a 5-minute deep-dive.
* ``upgrade/RESUME_BULLETS.md``: exactly three generated bullets that match the
  measured numbers (``scripts/render_resume_bullets.py --check``).

Exit 0 when all hold, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import render_resume_bullets  # noqa: E402

ALLOWED_SOURCES = (
    "docs/M7_SYSTEM_HANDOFF.md",
    "docs/M7_FINAL_RELEASE.md",
    "docs/M7_PRESENTATION_NOTE.md",
    "docs/M8_CANVA_STAKEHOLDER_REPORT.md",
)
SECTIONS = ("Problem", "Discovery", "Scope", "Build", "Demo-back", "Result", "What I would change")
CITATION_RE = re.compile(r"\[source: ([^\]§]+?) §([^\]]+)\]")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


def _headings(path: Path) -> list[str]:
    return [h.strip() for h in HEADING_RE.findall(path.read_text(encoding="utf-8"))]


def _section_exists(headings: list[str], section: str) -> bool:
    section = section.strip()
    for heading in headings:
        if heading == section:
            return True
        if heading.startswith(section) and not heading[len(section)].isalnum():
            return True
    return False


def check_case_study(text: str) -> list[str]:
    problems: list[str] = []
    if "agent_draft_unreviewed" not in text:
        problems.append("CASE_STUDY.md lacks the agent_draft_unreviewed label")
    if "not recorded" not in text:
        problems.append("CASE_STUDY.md never says 'not recorded' for missing client words or reactions")
    found = re.findall(r"^## \d+\. (.+)$", text, re.MULTILINE)
    if tuple(found) != SECTIONS:
        problems.append(f"CASE_STUDY.md sections {found} != {list(SECTIONS)}")
    for source, section in CITATION_RE.findall(text):
        source = source.strip()
        if source not in ALLOWED_SOURCES:
            problems.append(f"CASE_STUDY.md cites {source}, which is not one of the four allowed sources")
            continue
        path = ROOT / source
        if not path.is_file():
            problems.append(f"CASE_STUDY.md cites missing file {source}")
        elif not _section_exists(_headings(path), section):
            problems.append(f"CASE_STUDY.md cites {source} §{section}, but no heading starts with that")
    parts = re.split(r"^## \d+\. .+$", text, flags=re.MULTILINE)[1:]
    for name, body in zip(SECTIONS[:6], parts[:6]):
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        for i, para in enumerate(paragraphs):
            if not re.search(r"\d", CITATION_RE.sub("", para)):
                continue
            cited = CITATION_RE.search(para)
            next_is_citation = i + 1 < len(paragraphs) and not CITATION_RE.sub("", paragraphs[i + 1]).strip()
            if not cited and not next_is_citation:
                problems.append(f"CASE_STUDY.md {name}: uncited paragraph with a number: {para[:70]!r}")
    return problems


def check_demo_script(text: str) -> list[str]:
    problems = []
    for heading in ("## 90-second demo", "## 5-minute deep-dive"):
        if heading not in text:
            problems.append(f"DEMO_SCRIPT.md lacks '{heading}'")
    return problems


def check_resume_bullets() -> list[str]:
    text = render_resume_bullets.TARGET.read_text(encoding="utf-8")
    block = text.split(render_resume_bullets.START, 1)[-1].split(render_resume_bullets.END, 1)[0]
    problems = []
    count = len([line for line in block.splitlines() if line.startswith("- ")])
    if count != 3:
        problems.append(f"RESUME_BULLETS.md has {count} bullets, expected 3")
    if render_resume_bullets.main(["--check"]) != 0:
        problems.append("RESUME_BULLETS.md numbers do not match their sources")
    return problems


def main() -> int:
    problems: list[str] = []
    for rel in ("docs/CASE_STUDY.md", "docs/DEMO_SCRIPT.md", "docs/WALKTHROUGH.md", "upgrade/RESUME_BULLETS.md"):
        if not (ROOT / rel).is_file():
            problems.append(f"missing {rel}")
    if not problems:
        problems += check_case_study((ROOT / "docs" / "CASE_STUDY.md").read_text(encoding="utf-8"))
        problems += check_demo_script((ROOT / "docs" / "DEMO_SCRIPT.md").read_text(encoding="utf-8"))
        problems += check_resume_bullets()
    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    if problems:
        return 1
    print("L5 docs OK: case study cited from the four sources, demo script, three measured bullets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
