#!/usr/bin/env python3
"""Run M8 release checks without hiding failures."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", default="burnaby_r1")
    parser.add_argument(
        "--m7-output-dir",
        default=str(ROOT / "outputs" / "m7_runs" / "burnaby_r1" / "google_gemini_3_1_flash_lite"),
    )
    parser.add_argument("--m8-output-dir", default=str(ROOT / "outputs" / "m8_runs" / "burnaby_r1" / "local_m8"))
    parser.add_argument("--out-dir", default=str(ROOT / "outputs" / "m8_runs" / "release_check"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    python = sys.executable
    m8_tests = sorted(str(path) for path in (ROOT / "tests").glob("test_m8_*.py"))
    checks = [
        ("compileall", [python, "-m", "compileall", "-q", "src", "scripts", "dashboard", "benchmark", "tests"]),
        ("m7_status", [python, "scripts/run_consolidated_prototype.py", "status"]),
        ("m7_benchmark", [python, "benchmark/evaluate_benchmark.py", "--city", args.city, "--output-dir", args.m7_output_dir]),
        (
            "m7_adversarial",
            [
                python,
                "benchmark/evaluate_adversarial.py",
                "--config",
                f"configs/{args.city}.json",
                "--cases",
                f"benchmark/gold/{args.city}_adversarial_cases.json",
                "--bundle-cases",
                f"benchmark/gold/{args.city}_adversarial_bundles.json",
            ],
        ),
        ("m7_chatbot_gold", [python, "benchmark/evaluate_m7_chatbot.py", "--cases", "benchmark/gold/m7_chatbot_gold_cases.json"]),
        ("m8_unit_tests", [python, "-m", "pytest", "-q", *m8_tests]),
        (
            "m8_pipeline_smoke",
            [
                python,
                "scripts/run_m8_pipeline.py",
                "--city",
                args.city,
                "--config",
                f"configs/{args.city}.json",
                "--input-dir",
                args.m7_output_dir,
                "--output-dir",
                args.m8_output_dir,
                "--dry-run",
            ],
        ),
        ("m8_chatbot_gold", [python, "benchmark/evaluate_m8_chatbot.py", "--cases", "benchmark/gold/m8_chatbot_gold_cases.json", "--output-dir", args.m8_output_dir]),
        ("m8_summary_exists", [python, "-c", f"from pathlib import Path; raise SystemExit(0 if Path({str(Path(args.m8_output_dir) / 'm8_summary.json')!r}).exists() else 1)"]),
    ]
    rows = [run_check(name, command) for name, command in checks]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "report": "m8_release_check",
        "passed": all(row["returncode"] == 0 for row in rows),
        "m7_safety_preserved": _m7_safety_preserved(Path(args.m8_output_dir)),
        "checks": rows,
        "m8_output_dir": args.m8_output_dir,
        "output_path": str(out_dir / "m8_release_check.json"),
        "markdown_output_path": str(out_dir / "m8_release_check.md"),
        "m8_metrics": _m8_metrics(Path(args.m8_output_dir)),
    }
    (out_dir / "m8_release_check.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "m8_release_check.md").write_text(render_markdown(report), encoding="utf-8")
    print(f"M8 release check written: {out_dir / 'm8_release_check.md'}")
    print(f"Passed: {report['passed']}")
    return 0 if report["passed"] and report["m7_safety_preserved"] else 1


def run_check(name: str, command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        "name": name,
        "command": command,
        "returncode": result.returncode,
        "stdout_tail": tail(result.stdout),
        "stderr_tail": tail(result.stderr),
    }


def _m7_safety_preserved(m8_output_dir: Path) -> bool:
    path = m8_output_dir / "m7_m8_comparison.json"
    if not path.exists():
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    return bool((payload.get("safety") or {}).get("m7_safety_preserved"))


def _m8_metrics(m8_output_dir: Path) -> dict[str, Any]:
    path = m8_output_dir / "m8_summary.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("m8_metrics") or {}


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M8 Release Check",
        "",
        f"Passed: `{report['passed']}`",
        f"M7 safety preserved: `{report['m7_safety_preserved']}`",
        f"Output: `{report['output_path']}`",
        "",
        "| Check | Return code |",
        "|---|---:|",
    ]
    for row in report["checks"]:
        lines.append(f"| {row['name']} | {row['returncode']} |")
    lines.append("")
    return "\n".join(lines)


def tail(text: str, limit: int = 3000) -> str:
    return text[-limit:] if len(text) > limit else text


if __name__ == "__main__":
    raise SystemExit(main())
