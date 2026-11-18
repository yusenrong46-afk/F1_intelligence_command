"""Regression tests added by the portfolio upgrade (L1 Reachable).

* ``benchmark/evaluate_benchmark.py`` must fail loudly, not print
  "Benchmark complete" with precision 0.00, when pointed at a directory with no
  ``verified_rules.json``.
* ``--report-dir`` keeps the committed M7 artifacts byte-identical, and the
  regenerated Calgary and Vancouver reports reproduce the committed ones.
* ``scripts/fetch_bylaw.py --verify-provenance`` never rewrites provenance and
  refuses bytes whose SHA-256 differs from the committed value.
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / "benchmark" / "evaluate_benchmark.py"
M7 = ROOT / "outputs" / "m7_runs"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import fetch_bylaw  # noqa: E402


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(EVALUATOR), *args], cwd=ROOT, capture_output=True, text=True, check=False
    )


def test_benchmark_exits_nonzero_on_missing_output_dir(tmp_path: Path) -> None:
    proc = _run("--city", "burnaby_r1", "--output-dir", str(tmp_path / "does_not_exist"))
    assert proc.returncode != 0
    assert "no verified_rules.json" in proc.stderr
    assert "Benchmark complete" not in proc.stdout


def test_benchmark_exits_nonzero_on_dir_without_verified_rules(tmp_path: Path) -> None:
    (tmp_path / "rule_candidates.json").write_text("[]", encoding="utf-8")
    proc = _run("--city", "burnaby_r1", "--output-dir", str(tmp_path))
    assert proc.returncode != 0
    assert not (tmp_path / "benchmark_report.json").exists()


@pytest.mark.parametrize("city", ["calgary_rcg", "vancouver_rs"])
def test_report_dir_reproduces_committed_report_without_touching_artifacts(city: str, tmp_path: Path) -> None:
    output_dir = M7 / city / "google_gemini_3_1_flash_lite"
    committed = output_dir / "benchmark_report.json"
    before = committed.read_bytes()
    proc = _run("--city", city, "--output-dir", str(output_dir.relative_to(ROOT)), "--report-dir", str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert committed.read_bytes() == before, "committed artifact must stay byte-identical"
    assert (tmp_path / "benchmark_report.json").read_bytes() == before


def test_missing_retrieval_artifact_is_not_scored_as_zero_recall(tmp_path: Path) -> None:
    proc = _run(
        "--city", "vancouver_rs",
        "--output-dir", "outputs/m7_runs/vancouver_rs/google_gemini_3_1_flash_lite",
        "--report-dir", str(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr
    metrics = json.loads((tmp_path / "benchmark_report.json").read_text(encoding="utf-8"))["rule_metrics"]
    assert metrics["retrieval_recall_applicable"] is False
    assert metrics["retrieval_recall"] is None


class _FakeResponse(io.BytesIO):
    def __enter__(self):  # noqa: D401 - context manager protocol
        return self

    def __exit__(self, *exc):
        return False


def _seed_city(root: Path, payload: bytes, *, sha: str | None = None) -> Path:
    base = root / "data" / "bylaws" / "testville"
    base.mkdir(parents=True)
    provenance = {
        "url": "https://example.test/testville.pdf",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "sha256": sha or hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }
    (base / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return base


def test_fetch_verified_source_writes_pdf_and_never_touches_provenance(tmp_path: Path) -> None:
    payload = b"%PDF-1.4 fictional testville bylaw"
    base = _seed_city(tmp_path, payload)
    provenance_before = (base / "provenance.json").read_bytes()
    result = fetch_bylaw.fetch_verified_source(
        "testville", root=tmp_path, opener=lambda request: _FakeResponse(payload)
    )
    assert result["status"] == "fetched"
    assert (base / "source.pdf").read_bytes() == payload
    assert (base / "provenance.json").read_bytes() == provenance_before
    again = fetch_bylaw.fetch_verified_source("testville", root=tmp_path, opener=None)
    assert again["status"] == "unchanged"


def test_fetch_verified_source_refuses_hash_mismatch(tmp_path: Path) -> None:
    base = _seed_city(tmp_path, b"original", sha="0" * 64)
    provenance_before = (base / "provenance.json").read_bytes()
    with pytest.raises(fetch_bylaw.ProvenanceMismatch):
        fetch_bylaw.fetch_verified_source(
            "testville", root=tmp_path, opener=lambda request: _FakeResponse(b"tampered")
        )
    assert not (base / "source.pdf").exists()
    assert (base / "provenance.json").read_bytes() == provenance_before


def test_fetch_verified_source_follows_cookie_gated_redirect(tmp_path: Path) -> None:
    """calgary.ca sets a cookie in a 302 to the same URL; plain urlopen loops."""
    import hashlib
    import http.server
    import threading

    payload = b"%PDF-1.4 cookie gated fixture"

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib API
            if "visited=1" in (self.headers.get("Cookie") or ""):
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                self.send_response(302)
                self.send_header("Set-Cookie", "visited=1; Path=/")
                self.send_header("Location", self.path)
                self.end_headers()

        def log_message(self, *args) -> None:
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        city_dir = tmp_path / "data" / "bylaws" / "cookieville"
        city_dir.mkdir(parents=True)
        provenance = {
            "url": f"http://127.0.0.1:{server.server_port}/bylaw.pdf",
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        (city_dir / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
        before = (city_dir / "provenance.json").read_bytes()
        result = fetch_bylaw.fetch_verified_source("cookieville", root=tmp_path)
        assert result["status"] == "fetched"
        assert (city_dir / "source.pdf").read_bytes() == payload
        assert (city_dir / "provenance.json").read_bytes() == before
    finally:
        server.shutdown()
