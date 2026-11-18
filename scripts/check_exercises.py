"""Check exercises/ (L5): stand-alone stubs whose tests fail until solved.

For each ``exercises/NN_*`` folder this asserts:

* it has a stub module, a ``test_*.py`` file and ``HINTS.md``;
* no Python file imports the project (``burnaby_prototype`` or ``src``);
* the stub still raises ``NotImplementedError`` (no solution committed);
* running its tests collects them and every one fails (pytest exit code 1,
  zero passed), each with ``NotImplementedError``.

Exit 0 when all hold, 1 otherwise.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXERCISES = ROOT / "exercises"
PROJECT_IMPORT = re.compile(r"^\s*(?:from|import)\s+(?:burnaby_prototype|src)\b", re.MULTILINE)
SUMMARY = re.compile(r"(\d+) (failed|passed|error|errors)\b")


def check_folder(folder: Path) -> list[str]:
    problems: list[str] = []
    py_files = sorted(folder.glob("*.py"))
    tests = [p for p in py_files if p.name.startswith("test_")]
    stubs = [p for p in py_files if not p.name.startswith("test_")]
    if not tests:
        problems.append(f"{folder.name}: no test_*.py")
    if len(stubs) != 1:
        problems.append(f"{folder.name}: expected one stub module, found {[p.name for p in stubs]}")
    if not (folder / "HINTS.md").is_file():
        problems.append(f"{folder.name}: no HINTS.md")
    for path in py_files:
        if PROJECT_IMPORT.search(path.read_text(encoding="utf-8")):
            problems.append(f"{folder.name}/{path.name} imports project code; exercises must stand alone")
    for stub in stubs:
        if "raise NotImplementedError" not in stub.read_text(encoding="utf-8"):
            problems.append(f"{folder.name}/{stub.name} no longer raises NotImplementedError (solution committed?)")
    if problems or not tests:
        return problems
    proc = subprocess.run(  # noqa: S603 - fixed local command
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(folder)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    output = proc.stdout + proc.stderr
    counts = {kind: int(n) for n, kind in SUMMARY.findall(output.splitlines()[-1] if output.strip() else "")}
    failed, passed = counts.get("failed", 0), counts.get("passed", 0)
    if proc.returncode != 1 or failed == 0 or passed or counts.get("error") or counts.get("errors"):
        problems.append(
            f"{folder.name}: expected every test to fail on the stub; pytest exit {proc.returncode}, "
            f"{failed} failed, {passed} passed"
        )
    elif output.count("NotImplementedError") < failed:
        problems.append(f"{folder.name}: some tests fail for a reason other than the unsolved stub")
    else:
        print(f"PASS {folder.name}: {failed} tests fail on the unsolved stub")
    return problems


def main() -> int:
    folders = sorted(p for p in EXERCISES.iterdir() if p.is_dir() and re.match(r"\d\d_", p.name))
    problems: list[str] = []
    if len(folders) != 3:
        problems.append(f"expected 3 exercise folders, found {[p.name for p in folders]}")
    for folder in folders:
        problems.extend(check_folder(folder))
    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
