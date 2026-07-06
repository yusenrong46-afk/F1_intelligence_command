"""Run matrix contracts for M8.5 multi-city stress."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CityRunResult:
    city: str
    status: str
    config_path: str
    m8_input_dir: str
    output_dir: str
    source_pdf: str = ""
    source_provenance: str = ""
    source_status: str = ""
    skip_reason: str = ""
    return_code: int | None = None
    measured_metrics: dict[str, Any] = field(default_factory=dict)
    command: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "city": self.city,
            "status": self.status,
            "config_path": self.config_path,
            "m8_input_dir": self.m8_input_dir,
            "output_dir": self.output_dir,
            "source_pdf": self.source_pdf,
            "source_provenance": self.source_provenance,
            "source_status": self.source_status,
            "skip_reason": self.skip_reason,
            "return_code": self.return_code,
            "measured_metrics": dict(self.measured_metrics),
            "command": list(self.command),
        }


def build_city_run_matrix(results: list[CityRunResult]) -> dict[str, Any]:
    return {
        "city_count": len(results),
        "measured_count": sum(1 for result in results if result.status.startswith("measured")),
        "skipped_count": sum(1 for result in results if result.status == "skipped"),
        "failed_count": sum(1 for result in results if result.status == "failed"),
        "results": [result.to_dict() for result in results],
    }
