import json
from pathlib import Path

from burnaby_prototype.m8_5.multi_city import (
    CityRunResult,
    build_city_format_profile,
    build_cross_city_summary,
    run_multi_city_stress,
)
from burnaby_prototype.m8_5.multi_city.stress_test_runner import M8_REQUIRED_INPUTS


def test_multi_city_stress_can_run_in_dry_run_mode(tmp_path):
    _seed_config(tmp_path, "burnaby_r1")
    _seed_m8_inputs(tmp_path, "burnaby_r1")
    _seed_m7_inputs(tmp_path, "burnaby_r1")

    def fake_runner(command):
        output_dir = Path(command[command.index("--output-dir") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_json(output_dir / "m8_5_summary.json", {"city": "burnaby_r1", "m8_5_metrics": {}})
        _write_json(
            output_dir / "m8_m8_5_comparison.json",
            {
                "m8_5": {
                    "verified_like_count": 1,
                    "false_verified_count": 0,
                    "false_approval_count": 0,
                }
            },
        )
        _write_json(output_dir / "table_blocks.json", [])
        return 0

    result = run_multi_city_stress(
        root=tmp_path,
        output_root=tmp_path / "outputs" / "m8_5_runs",
        cities=["burnaby_r1"],
        dry_run=True,
        command_runner=fake_runner,
    )

    assert result["city_run_matrix"]["measured_count"] == 1
    assert result["cross_city_summary"]["false_verified_total"] == 0


def test_missing_city_data_produces_clear_skip_reason(tmp_path):
    _seed_config(tmp_path, "vancouver_rs")

    result = run_multi_city_stress(
        root=tmp_path,
        output_root=tmp_path / "outputs" / "m8_5_runs",
        cities=["vancouver_rs"],
        dry_run=True,
        bootstrap_m8=False,
        command_runner=lambda command: 0,
    )

    row = result["city_run_matrix"]["results"][0]
    assert row["status"] == "skipped"
    assert row["skip_reason"] == "M8 input artifacts missing"


def test_cross_city_summary_separates_measured_and_skipped_and_aggregates_safety():
    results = [
        CityRunResult(
            city="burnaby_r1",
            status="measured",
            config_path="configs/burnaby_r1.json",
            m8_input_dir="outputs/m8_runs/burnaby_r1/local_m8",
            output_dir="outputs/m8_5_runs/burnaby_r1/local_m8_5",
            measured_metrics={"false_verified_count": 0, "false_approval_count": 0},
        ),
        CityRunResult(
            city="vancouver_rs",
            status="skipped",
            config_path="configs/vancouver_rs.json",
            m8_input_dir="outputs/m8_runs/vancouver_rs/local_m8",
            output_dir="outputs/m8_5_runs/vancouver_rs/local_m8_5",
            skip_reason="M8 input artifacts missing",
        ),
    ]

    summary = build_cross_city_summary(results, profiles=[])

    assert summary["measured_city_count"] == 1
    assert summary["skipped_city_count"] == 1
    assert summary["false_verified_total"] == 0
    assert summary["safety_preserved"] is True


def test_city_format_profile_serializes():
    profile = build_city_format_profile(
        city="burnaby_r1",
        summary={},
        comparison={
            "m8_5": {
                "table_block_count": 2,
                "table_derived_rules_count": 3,
                "dependency_total_count": 1,
                "dependency_unresolved_count": 1,
                "false_verified_count": 0,
            }
        },
        table_blocks=[],
    )

    assert profile["city"] == "burnaby_r1"
    assert "table-derived rules present" in profile["format_notes"]
    json.dumps(profile)


def _seed_config(root: Path, city: str) -> None:
    config_dir = root / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    _write_json(config_dir / f"{city}.json", {"city": city, "zone": city})


def _seed_m8_inputs(root: Path, city: str) -> None:
    m8_dir = root / "outputs" / "m8_runs" / city / "local_m8"
    m8_dir.mkdir(parents=True, exist_ok=True)
    for name in M8_REQUIRED_INPUTS:
        _write_json(m8_dir / name, {})


def _seed_m7_inputs(root: Path, city: str) -> None:
    m7_dir = root / "outputs" / "m7_runs" / city / "google_gemini_3_1_flash_lite"
    m7_dir.mkdir(parents=True, exist_ok=True)
    _write_json(m7_dir / "evidence_units.json", [])


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
