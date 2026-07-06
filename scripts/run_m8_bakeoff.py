#!/usr/bin/env python3
"""Run the M8 local bakeoff over existing M7 artifacts.

This is the concise M8-facing command for repeatable comparisons. It delegates
to the M8 pipeline because M8 does not call an LLM in the MVP path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_m8_pipeline.py"),
        *sys.argv[1:],
    ]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
