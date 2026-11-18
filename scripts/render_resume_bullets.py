"""Generate upgrade/RESUME_BULLETS.md from measured repository numbers (L5).

Every number in the three bullets comes from a generated or committed source:

* ``outputs/eval_summary.json`` (``make eval``): verified rules, precision,
  false-verified rules, poisoned cases and bundles, cities;
* ``src/burnaby_prototype/cli_verify.py``: contract version and exit codes;
* ``tests/fixtures/cli_contract/``: golden examples, one per decision bucket.

``--check`` rewrites nothing and exits 1 when the file differs from what the
sources generate (part of ``make l5-checks``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from burnaby_prototype import cli_verify  # noqa: E402

TARGET = ROOT / "upgrade" / "RESUME_BULLETS.md"
START, END = "<!-- bullets:start -->", "<!-- bullets:end -->"


def numbers() -> dict[str, Any]:
    summary = json.loads((ROOT / "outputs" / "eval_summary.json").read_text(encoding="utf-8"))
    totals = summary["totals"]
    exit_codes = [name for name in dir(cli_verify) if name.startswith("EXIT_")]
    golden = sorted(p.name for p in (ROOT / "tests" / "fixtures" / "cli_contract").iterdir() if p.is_dir())
    return {
        "cities": len(summary["cities"]),
        "verified": totals["verified_rule_count"],
        "precision": totals["min_verified_precision"],
        "false_verified": totals["false_verified_count"],
        "poisoned_cases": totals["adversarial_cases"],
        "poisoned_bundles": totals["adversarial_bundles"],
        "leaked": totals["adversarial_leaked"],
        "model_calls": summary["model_calls"],
        "contract": cli_verify.CONTRACT_VERSION,
        "exit_codes": len(exit_codes),
        "golden": len(golden),
    }


def bullets(n: dict[str, Any]) -> str:
    blocked = n["poisoned_cases"] + n["poisoned_bundles"] - n["leaked"]
    return "\n".join([
        f"- Built a verification-first pipeline that turns municipal zoning bylaws into GIS-ready rules: "
        f"an LLM only proposes, a deterministic verifier decides. {n['verified']} rules verified across "
        f"{n['cities']} cities at verified precision {n['precision']:.2f} with {n['false_verified']} "
        "false-verified rules against hand-built gold benchmarks.",
        f"- Designed a safety benchmark of {n['poisoned_cases']} poisoned rule candidates and "
        f"{n['poisoned_bundles']} poisoned evidence bundles (wrong table column, flipped operator, value "
        f"absent from its evidence); {blocked} of {n['poisoned_cases'] + n['poisoned_bundles']} are blocked, "
        f"re-scored offline with {n['model_calls']} model calls and enforced in CI against per-city baselines.",
        f"- Shipped a versioned command-line contract (contract {n['contract']}, JSON schemas, "
        f"{n['exit_codes']} documented exit codes, {n['golden']} golden tests, one per decision bucket), "
        "a container image with a smoke test, and a one-command kit for onboarding a new city.",
    ])


def render(text: str, body: str) -> str:
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{body}\n{END}{tail}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    current = TARGET.read_text(encoding="utf-8")
    expected = render(current, bullets(numbers()))
    if args.check:
        if current != expected:
            print(f"FAIL {TARGET.name} differs from the measured numbers; run scripts/render_resume_bullets.py",
                  file=sys.stderr)
            return 1
        print(f"resume bullets OK: {TARGET.name} matches outputs/eval_summary.json and the CLI contract")
        return 0
    TARGET.write_text(expected, encoding="utf-8")
    print(f"updated {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
