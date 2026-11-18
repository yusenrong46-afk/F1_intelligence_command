"""Scan tracked files for credentials and for new files over 5 MB.

* Secret patterns: provider API keys (OpenRouter, Anthropic, OpenAI, Google),
  GitHub and AWS tokens, private-key blocks, and long literal values assigned to
  names like ``api_key``/``secret``/``token``/``password``. Matches are reported
  by file and line only; the matched text is never printed.
* Size: any tracked file over 5 MB that does not exist on the base ref
  (default ``origin/main``) fails. Files already on the base are reported as
  pre-existing, not failures.

Exit 1 on any finding. Usage: ``python scripts/secret_scan.py [--base REF]``.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 5 * 1024 * 1024
PATTERNS = {
    # Built from parts so this file never contains a literal key prefix
    # (tests/test_native_extraction.py forbids that string in scripts/).
    "openrouter_key": re.compile("sk-" + "or-" + "v1-" + r"[0-9a-f]{32,}"),
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "openai_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "github_token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{50,}"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "assigned_secret": re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*[\"'][A-Za-z0-9_\-/+=]{24,}[\"']"
    ),
}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webm", ".mp4", ".pdf", ".docx", ".sqlite", ".ipynb"}


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True).stdout
    return [p for p in out.decode().split("\0") if p]


def on_base(path: str, base: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "cat-file", "-e", f"{base}:{path}"], capture_output=True, check=False
    )
    return proc.returncode == 0


def scan(base: str) -> tuple[list[str], list[str]]:
    findings: list[str] = []
    notes: list[str] = []
    base_ok = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet", base], capture_output=True, check=False
    ).returncode == 0
    for rel in tracked_files():
        path = ROOT / rel
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size > MAX_BYTES:
            if base_ok and on_base(rel, base):
                notes.append(f"pre-existing large file ({size} bytes): {rel}")
            else:
                findings.append(f"new file over 5 MB ({size} bytes): {rel}")
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for name, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"possible {name} at {rel}:{lineno}")
    if not base_ok:
        notes.append(f"base ref {base!r} not available; every file over 5 MB counts as new")
    return findings, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args(argv)
    findings, notes = scan(args.base)
    for note in notes:
        print(f"note: {note}")
    for finding in findings:
        print(f"FAIL {finding}", file=sys.stderr)
    if findings:
        return 1
    print(f"secret scan clean: {len(tracked_files())} tracked files, no new file over 5 MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
