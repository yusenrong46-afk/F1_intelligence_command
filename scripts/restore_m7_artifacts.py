"""Restore the curated M7 run artifacts from the dashboard repository.

The M7 release artifacts were whitelisted in ``.gitignore`` but only ever
committed to ``yusenrong46-afk/burnaby-verification-dashboard``. This script
copies them byte-for-byte from a pinned commit of that repository and writes
``outputs/m7_runs/MANIFEST.sha256`` so the copies can be re-verified later.

Only files that this repository's ``.gitignore`` already whitelists are
copied, plus any path named with ``--extra`` (files a test needs).

Usage::

    python scripts/restore_m7_artifacts.py --source-repo ../burnaby-verification-dashboard
    python scripts/restore_m7_artifacts.py --verify

``--verify`` recomputes every SHA-256 in the manifest and exits 1 on any
mismatch or missing file. It needs no network and no source repository.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "outputs" / "m7_runs" / "MANIFEST.sha256"
SOURCE_REPO_SLUG = "yusenrong46-afk/burnaby-verification-dashboard"
DEFAULT_COMMIT = "e1a150f"
CITIES = ("burnaby_r1", "calgary_rcg", "vancouver_rs")
HEADER_PREFIX = "# source:"


def _git(repo: Path, *args: str, binary: bool = False) -> bytes | str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True
    ).stdout
    return out if binary else out.decode()


def _whitelisted(paths: list[str]) -> list[str]:
    """Return the paths this repo's .gitignore does NOT ignore."""
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "check-ignore", "--stdin", "-n", "-v"],
        input="\n".join(paths).encode(),
        capture_output=True,
        check=False,
    )
    allowed = []
    for line in proc.stdout.decode().splitlines():
        meta, _, path = line.partition("\t")
        pattern = meta.split(":", 2)[-1] if meta != "::" else ""
        if meta == "::" or pattern.startswith("!"):
            allowed.append(path)
    return sorted(allowed)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restore(source_repo: Path, commit: str, extra: list[str]) -> int:
    full = _git(source_repo, "rev-parse", f"{commit}^{{commit}}").strip()
    listed = _git(source_repo, "ls-tree", "-r", "--name-only", full, "outputs/m7_runs").splitlines()
    candidates = [p for p in listed if p.split("/")[2] in CITIES]
    chosen = sorted(set(_whitelisted(candidates)) | {p for p in extra if p in listed})
    lines = [f"{HEADER_PREFIX} {SOURCE_REPO_SLUG}@{full}", "# sha256  path"]
    for rel in chosen:
        blob = _git(source_repo, "show", f"{full}:{rel}", binary=True)
        dest = ROOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)  # byte-identical copy of the source blob
        lines.append(f"{hashlib.sha256(blob).hexdigest()}  {rel}")
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"restored {len(chosen)} files from {SOURCE_REPO_SLUG}@{full[:7]}")
    return 0


def verify() -> int:
    if not MANIFEST.exists():
        print(f"missing manifest: {MANIFEST.relative_to(ROOT)}", file=sys.stderr)
        return 1
    bad = 0
    count = 0
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        digest, rel = line.split("  ", 1)
        count += 1
        path = ROOT / rel
        if not path.exists():
            print(f"MISSING {rel}", file=sys.stderr)
            bad += 1
        elif sha256(path) != digest:
            print(f"CHANGED {rel}", file=sys.stderr)
            bad += 1
    print(f"verified {count - bad}/{count} M7 artifacts against MANIFEST.sha256")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-repo", type=Path, help="local clone of the dashboard repo")
    parser.add_argument("--commit", default=DEFAULT_COMMIT)
    parser.add_argument("--extra", action="append", default=[], help="extra path to copy")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    if args.verify:
        return verify()
    if args.source_repo is None:
        parser.error("--source-repo is required unless --verify is given")
    return restore(args.source_repo.resolve(), args.commit, args.extra)


if __name__ == "__main__":
    raise SystemExit(main())
