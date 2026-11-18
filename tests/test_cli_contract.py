"""Contract tests for the ``bylaw-verify`` CLI (contract 1.0, L4).

Each golden case under tests/fixtures/cli_contract/<bucket>/ is one candidate
and its evidence unit copied from the committed Calgary M7 run, with the
decision the verifier gives it. The config is copied to a temporary
``configs/`` so no cached source PDF is picked up and the result is the same
on every machine.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "cli_contract"
BUCKETS = ("verified", "review_needed", "rejected", "not_used")
RESULT_SCHEMA = json.loads((ROOT / "schemas" / "bylaw_verify_result.schema.json").read_text(encoding="utf-8"))

from burnaby_prototype import cli_verify  # noqa: E402


@pytest.fixture()
def hermetic_config(tmp_path: Path) -> Path:
    target = tmp_path / "configs" / "calgary_rcg.json"
    target.parent.mkdir()
    shutil.copy(ROOT / "configs" / "calgary_rcg.json", target)
    return target


def _run(argv: list[str], capsys) -> tuple[int, str, str]:
    code = cli_verify.main(argv)
    out, err = capsys.readouterr()
    return code, out, err


@pytest.mark.parametrize("bucket", BUCKETS)
def test_golden_example_per_bucket(bucket: str, hermetic_config: Path, tmp_path: Path, capsys) -> None:
    case = FIXTURES / bucket
    expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))
    out_dir = tmp_path / "out"
    code, out, _ = _run(
        ["--candidates", str(case / "candidates.json"), "--evidence", str(case / "evidence.json"),
         "--config", str(hermetic_config), "--out-dir", str(out_dir)],
        capsys,
    )
    assert code == cli_verify.EXIT_OK
    envelope = json.loads(out)
    jsonschema.validate(envelope, RESULT_SCHEMA)
    assert envelope["contract_version"] == "1.0"
    assert envelope["source_pdf_used"] is False
    assert envelope["counts"] == expected["counts"]
    assert envelope["decisions"] == expected["decisions"]
    assert [d["decision"] for d in envelope["decisions"]] == [bucket]
    assert json.loads((out_dir / "bylaw_verify_result.json").read_text(encoding="utf-8")) == envelope
    assert {"verified_rules.json", "review_needed.json", "rejected_rules.json", "not_used.json"} <= set(envelope["artifacts"])


def test_full_burnaby_run_matches_committed_counts(tmp_path: Path, capsys) -> None:
    run_dir = ROOT / "outputs" / "m7_runs" / "burnaby_r1" / "google_gemini_3_1_flash_lite"
    config = tmp_path / "configs" / "burnaby_r1.json"
    config.parent.mkdir()
    shutil.copy(ROOT / "configs" / "burnaby_r1.json", config)
    code, out, _ = _run(
        ["--candidates", str(run_dir / "rule_candidates.json"), "--evidence", str(run_dir / "evidence_units.json"),
         "--config", str(config), "--out-dir", str(tmp_path / "out")],
        capsys,
    )
    assert code == 0
    counts = json.loads(out)["counts"]
    committed = json.loads((run_dir / "benchmark_report.json").read_text(encoding="utf-8"))["rule_metrics"]
    assert counts["verified"] == committed["verified_rule_count"] == 87
    assert counts["review_needed"] == committed["review_rule_count"] == 57


def test_missing_input_file_exits_3(hermetic_config: Path, tmp_path: Path, capsys) -> None:
    code, _, err = _run(
        ["--candidates", str(tmp_path / "nope.json"), "--evidence", str(FIXTURES / "verified" / "evidence.json"),
         "--config", str(hermetic_config), "--out-dir", str(tmp_path / "out")],
        capsys,
    )
    assert code == cli_verify.EXIT_INPUT == 3
    assert json.loads(err)["exit_code"] == 3


def test_invalid_json_exits_3(hermetic_config: Path, tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("[{", encoding="utf-8")
    code, _, _ = _run(
        ["--candidates", str(bad), "--evidence", str(FIXTURES / "verified" / "evidence.json"),
         "--config", str(hermetic_config), "--out-dir", str(tmp_path / "out")],
        capsys,
    )
    assert code == 3


def test_schema_violation_exits_4_and_writes_nothing(hermetic_config: Path, tmp_path: Path, capsys) -> None:
    bad = tmp_path / "candidates.json"
    bad.write_text(json.dumps([{"candidate_id": "x", "rule_object": "height"}]), encoding="utf-8")
    out_dir = tmp_path / "out"
    code, _, err = _run(
        ["--candidates", str(bad), "--evidence", str(FIXTURES / "verified" / "evidence.json"),
         "--config", str(hermetic_config), "--out-dir", str(out_dir)],
        capsys,
    )
    assert code == cli_verify.EXIT_INPUT_SCHEMA == 4
    assert "evidence_id" in json.loads(err)["error"]
    assert not out_dir.exists()


def test_missing_config_exits_3(tmp_path: Path, capsys) -> None:
    code, _, _ = _run(
        ["--candidates", str(FIXTURES / "verified" / "candidates.json"),
         "--evidence", str(FIXTURES / "verified" / "evidence.json"),
         "--config", str(tmp_path / "configs" / "nowhere.json"), "--out-dir", str(tmp_path / "out")],
        capsys,
    )
    assert code == 3


def test_usage_error_exits_2() -> None:
    with pytest.raises(SystemExit) as exc:
        cli_verify.main(["--candidates", "x.json"])
    assert exc.value.code == 2


def test_console_script_is_installed_and_documents_exit_codes() -> None:
    script = Path(sys.executable).with_name("bylaw-verify")
    assert script.exists(), "bylaw-verify console script not installed (run make setup)"
    proc = subprocess.run([str(script), "--help"], capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "Exit codes" in proc.stdout and "contract 1.0" in proc.stdout
