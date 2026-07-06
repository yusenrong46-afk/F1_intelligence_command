#!/usr/bin/env python3
"""Run the M7 exhaustive extraction/verifier path."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_m7_bakeoff_engine.py"),
        "--discovery-mode",
        "exhaustive",
        "--out-root",
        str(ROOT / "outputs" / "m7_runs"),
        *sys.argv[1:],
    ]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
