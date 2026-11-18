"""L1 benchmark smoke check over the committed M7 artifacts.

For each benchmarked city, run ``benchmark/evaluate_benchmark.py`` against the
committed run directory, writing reports to a temporary ``--report-dir`` so
the committed artifacts stay byte-identical. Require the printed lines
``Verified precision: 1.00`` and ``False verified: 0``. Then require that the
same command on a missing directory exits non-zero.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CITIES = ("burnaby_r1", "calgary_rcg", "vancouver_rs")
MODEL_DIR = "google_gemini_3_1_flash_lite"
REQUIRED_LINES = ("Verified precision: 1.00", "False verified: 0")


def evaluate(city: str, output_dir: str, report_dir: str | None) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "benchmark/evaluate_benchmark.py", "--city", city, "--output-dir", output_dir]
    if report_dir:
        cmd += ["--report-dir", report_dir]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for city in CITIES:
            proc = evaluate(city, f"outputs/m7_runs/{city}/{MODEL_DIR}", str(Path(tmp) / city))
            lines = proc.stdout.splitlines()
            missing = [line for line in REQUIRED_LINES if line not in lines]
            if proc.returncode != 0 or missing:
                failures += 1
                print(f"FAIL {city}: exit={proc.returncode} missing={missing}\n{proc.stderr}", file=sys.stderr)
            else:
                print(f"PASS {city}: {' | '.join(REQUIRED_LINES)}")
        proc = evaluate("burnaby_r1", str(Path(tmp) / "missing_dir"), None)
        if proc.returncode == 0:
            failures += 1
            print("FAIL missing directory: evaluator exited 0", file=sys.stderr)
        else:
            print(f"PASS missing directory: exit={proc.returncode} ({proc.stderr.strip().splitlines()[0]})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
