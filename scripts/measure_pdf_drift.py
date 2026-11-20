"""Re-verify the committed M7 candidates for each benchmarked city with whatever
source PDF is (or is not) at data/bylaws/<city>/source.pdf, score against the
committed gold, and print one JSON line per city. No model call."""
import json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1] if (Path(__file__).resolve().parents[1] / "configs").exists() else Path.cwd()
CITIES = ["burnaby_r1", "calgary_rcg", "vancouver_rs"]
for city in CITIES:
    run = ROOT / "outputs" / "m7_runs" / city / "google_gemini_3_1_flash_lite"
    pdf = ROOT / "data" / "bylaws" / city / "source.pdf"
    with tempfile.TemporaryDirectory() as tmp:
        out, rep = Path(tmp) / "out", Path(tmp) / "rep"
        v = subprocess.run([str(ROOT / ".venv/bin/bylaw-verify"), "--candidates", str(run / "rule_candidates.json"),
                            "--evidence", str(run / "evidence_units.json"), "--config", str(ROOT / "configs" / f"{city}.json"),
                            "--out-dir", str(out)], cwd=ROOT, capture_output=True, text=True)
        env = json.loads(v.stdout) if v.stdout.strip().startswith("{") else {}
        b = subprocess.run([sys.executable, "benchmark/evaluate_benchmark.py", "--city", city, "--output-dir", str(out),
                            "--report-dir", str(rep)], cwd=ROOT, capture_output=True, text=True)
        rp = rep / "benchmark_report.json"
        m = json.loads(rp.read_text())["rule_metrics"] if rp.exists() else {}
        print(json.dumps({"city": city, "source_pdf_present": pdf.exists(), "verify_exit": v.returncode,
                          "source_pdf_used": env.get("source_pdf_used"), "counts": env.get("counts"),
                          "metrics": {k: m.get(k) for k in ("verified_rule_count", "false_verified_count", "verified_precision", "review_needed_count")},
                          "bench_exit": b.returncode, "err": (v.stderr + b.stderr)[-300:] if not m else ""}))
