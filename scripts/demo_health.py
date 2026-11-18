"""Start the demo exactly as ``make demo`` does, require /_stcore/health == ok, stop it."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo_check import ROOT, SECRET_ENV, demo_command, wait_for_health  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8631)
    args = parser.parse_args(argv)
    env = {k: v for k, v in os.environ.items() if k not in SECRET_ENV}
    server = subprocess.Popen(demo_command(args.port), cwd=ROOT, env=env,  # noqa: S603
                              stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        body = wait_for_health(args.port)
        print(f"PASS http://127.0.0.1:{args.port}/_stcore/health -> {body} (no API key in env)")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=15)


if __name__ == "__main__":
    raise SystemExit(main())
