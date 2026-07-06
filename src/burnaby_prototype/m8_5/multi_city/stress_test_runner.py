"""Run M8.5 stress across available city artifacts."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .city_format_profile import build_city_format_profile
from .city_run_matrix import CityRunResult, build_city_run_matrix
from .generalization_report import build_cross_city_summary, render_generalization_report


M8_REQUIRED_INPUTS = (
    "source_spans.json",
    "structured_rules.json",
    "verification_decisions.json",
    "repair_attempts.json",
    "m7_m8_comparison.json",
    "m8_summary.json",
)


@dataclass(frozen=True)
class CitySpec:
    city: str
    config_path: Path
    source_pdf: Path
    source_provenance: Path
    m7_input_dir: Path
    m8_input_dir: Path
    output_dir: Path


CommandRunner = Callable[[list[str]], int]


def default_city_specs(root: Path, output_root: Path) -> list[CitySpec]:
    cities = ("burnaby_r1", "vancouver_rs", "calgary_rcg", "surrey_r3")
    return [
        CitySpec(
            city=city,
            config_path=root / "configs" / f"{city}.json",
            source_pdf=root / "data" / "bylaws" / city / "source.pdf",
            source_provenance=root / "data" / "bylaws" / city / "provenance.json",
            m7_input_dir=root / "outputs" / "m7_runs" / city / "google_gemini_3_1_flash_lite",
            m8_input_dir=root / "outputs" / "m8_runs" / city / "local_m8",
            output_dir=output_root / city / "local_m8_5",
        )
        for city in cities
    ]


def run_multi_city_stress(
    *,
    root: Path,
    output_root: Path,
    cities: list[str] | None = None,
    dry_run: bool = True,
    bootstrap_m8: bool = True,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    command_runner = command_runner or _run_command
    selected = set(cities or [])
    specs = [
        spec for spec in default_city_specs(root, output_root)
        if not selected or spec.city in selected
    ]
    results: list[CityRunResult] = []
    profiles: list[dict[str, Any]] = []
    for spec in specs:
        source_status = _source_status(spec)
        if not spec.config_path.exists():
            results.append(_skip(spec, "config missing", source_status=source_status))
            continue
        if not _has_m8_inputs(spec.m8_input_dir):
            if bootstrap_m8 and spec.m7_input_dir.exists():
                code = command_runner(_m8_command(root, spec, dry_run=dry_run))
                if code != 0 and not _has_m8_inputs(spec.m8_input_dir):
                    results.append(_failed(spec, code, _m8_command(root, spec, dry_run=dry_run), source_status=source_status))
                    continue
            if not _has_m8_inputs(spec.m8_input_dir):
                reason = "M8 input artifacts missing"
                if source_status == "source_fetched":
                    reason = "M8 input artifacts missing; official source fetched only"
                results.append(_skip(spec, reason, source_status=source_status))
                continue
        if not (spec.m7_input_dir / "evidence_units.json").exists():
            results.append(_skip(spec, "M7 evidence_units.json missing for repair rerun", source_status=source_status))
            continue
        command = _m8_5_command(root, spec, dry_run=dry_run)
        code = command_runner(command)
        summary = _read_json(spec.output_dir / "m8_5_summary.json", {})
        comparison = _read_json(spec.output_dir / "m8_m8_5_comparison.json", {})
        table_blocks = _read_json(spec.output_dir / "table_blocks.json", [])
        if code != 0 and not comparison:
            results.append(_failed(spec, code, command, source_status=source_status))
            continue
        metrics = (comparison.get("m8_5") or summary.get("m8_5_metrics") or {})
        status = "measured"
        if code != 0 or int(metrics.get("false_verified_count", 0) or 0) or int(metrics.get("false_approval_count", 0) or 0):
            status = "measured_unsafe"
        results.append(
            CityRunResult(
                city=spec.city,
                status=status,
                config_path=str(spec.config_path),
                m8_input_dir=str(spec.m8_input_dir),
                output_dir=str(spec.output_dir),
                source_pdf=str(spec.source_pdf),
                source_provenance=str(spec.source_provenance),
                source_status=source_status,
                return_code=code,
                measured_metrics=metrics,
                command=command,
            )
        )
        profiles.append(build_city_format_profile(city=spec.city, summary=summary, comparison=comparison, table_blocks=table_blocks))
    matrix = build_city_run_matrix(results)
    summary = build_cross_city_summary(results, profiles)
    return {
        "city_run_matrix": matrix,
        "cross_city_summary": summary,
        "city_format_profiles": profiles,
        "generalization_report": render_generalization_report(summary),
    }


def _has_m8_inputs(path: Path) -> bool:
    return all((path / name).exists() for name in M8_REQUIRED_INPUTS)


def _m8_command(root: Path, spec: CitySpec, *, dry_run: bool) -> list[str]:
    command = [
        str(root / ".venv" / "bin" / "python"),
        str(root / "scripts" / "run_m8_pipeline.py"),
        "--city",
        spec.city,
        "--config",
        str(spec.config_path),
        "--input-dir",
        str(spec.m7_input_dir),
        "--output-dir",
        str(spec.m8_input_dir),
        "--max-repair-attempts",
        "3",
    ]
    if dry_run:
        command.append("--dry-run")
    return command


def _m8_5_command(root: Path, spec: CitySpec, *, dry_run: bool) -> list[str]:
    command = [
        str(root / ".venv" / "bin" / "python"),
        str(root / "scripts" / "run_m8_5_pipeline.py"),
        "--city",
        spec.city,
        "--config",
        str(spec.config_path),
        "--m8-input-dir",
        str(spec.m8_input_dir),
        "--m7-input-dir",
        str(spec.m7_input_dir),
        "--output-dir",
        str(spec.output_dir),
        "--max-repair-attempts",
        "3",
        "--enable-table-parsing",
        "--enable-dependency-graph",
        "--enable-review-packets",
        "--enable-repair-rerun",
        "--apply-guarded-repair-promotions",
        "--enable-llm-repair",
    ]
    if dry_run:
        command.append("--dry-run")
    return command


def _source_status(spec: CitySpec) -> str:
    if spec.source_pdf.exists() and spec.source_provenance.exists():
        return "source_fetched"
    if spec.source_pdf.exists():
        return "source_pdf_only"
    return "source_missing"


def _skip(spec: CitySpec, reason: str, *, source_status: str = "") -> CityRunResult:
    return CityRunResult(
        city=spec.city,
        status="skipped",
        config_path=str(spec.config_path),
        m8_input_dir=str(spec.m8_input_dir),
        output_dir=str(spec.output_dir),
        source_pdf=str(spec.source_pdf),
        source_provenance=str(spec.source_provenance),
        source_status=source_status,
        skip_reason=reason,
    )


def _failed(spec: CitySpec, return_code: int, command: list[str], *, source_status: str = "") -> CityRunResult:
    return CityRunResult(
        city=spec.city,
        status="failed",
        config_path=str(spec.config_path),
        m8_input_dir=str(spec.m8_input_dir),
        output_dir=str(spec.output_dir),
        source_pdf=str(spec.source_pdf),
        source_provenance=str(spec.source_provenance),
        source_status=source_status,
        return_code=return_code,
        command=command,
    )


def _run_command(command: list[str]) -> int:
    return subprocess.run(command, check=False).returncode


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
