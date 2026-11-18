"""``bylaw-verify``: the versioned command-line contract for the verifier (L4).

This is a thin adapter over :func:`burnaby_prototype.slim_pipeline.run_slim_verification`,
the same path ``scripts/run_slim_verifier.py --native-extraction`` uses. It is
not a second implementation: it validates the two input files against
``schemas/``, calls the existing pipeline, and writes one output envelope,
``<out-dir>/bylaw_verify_result.json`` (validated against
``schemas/bylaw_verify_result.schema.json``), which it also prints on stdout.

The pipeline's own detailed files (``verified_rules.json``,
``review_needed.json``, ``rejected_rules.json``, ``not_used.json`` and the
reports) are written to ``--out-dir`` unchanged and listed in ``artifacts``.
When the city's cached source PDF exists at ``data/bylaws/<config stem>/source.pdf``
the pipeline uses it for source repair and table anchoring, as it always has;
``source_pdf_used`` records whether it did.

Exit codes:
  0  ran; decisions are in the envelope (review_needed and rejected are results, not errors)
  1  unexpected internal error
  2  bad command line (argparse)
  3  an input file is missing or is not valid JSON
  4  an input file does not match its schema
  5  the output envelope does not match its schema (contract bug)

No model call, no network. Usage::

    bylaw-verify --candidates rule_candidates.json --evidence evidence_units.json \
        --config configs/burnaby_r1.json --out-dir outputs/cli/burnaby_r1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "1.0"
EXIT_OK, EXIT_INTERNAL, EXIT_USAGE, EXIT_INPUT, EXIT_INPUT_SCHEMA, EXIT_OUTPUT_SCHEMA = 0, 1, 2, 3, 4, 5
ENVELOPE_NAME = "bylaw_verify_result.json"
BUCKET_FILES = {
    "verified": "verified_rules.json",
    "review_needed": "review_needed.json",
    "rejected": "rejected_rules.json",
    "not_used": "not_used.json",
}


def schema_dir() -> Path:
    """``schemas/`` next to ``src/`` in a checkout or the container image."""
    return Path(__file__).resolve().parents[2] / "schemas"


def load_schema(name: str) -> dict[str, Any]:
    return json.loads((schema_dir() / name).read_text(encoding="utf-8"))


class ContractError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def _read_input(path: Path, schema_name: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import jsonschema  # noqa: PLC0415 - core dependency, imported where used

    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(EXIT_INPUT, f"cannot read {path}: {exc}") from exc
    validator = jsonschema.Draft202012Validator(load_schema(schema_name))
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        where = "/".join(str(p) for p in first.absolute_path) or "(root)"
        raise ContractError(
            EXIT_INPUT_SCHEMA, f"{path} does not match {schema_name} at {where}: {first.message} ({len(errors)} error(s))"
        )
    info = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "count": len(data)}
    return data, info


def _decision_rows(out_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket, name in BUCKET_FILES.items():
        path = out_dir / name
        rules = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        for rule in rules:
            candidate = rule.get("candidate") if isinstance(rule.get("candidate"), dict) else {}
            source = rule.get("source") if isinstance(rule.get("source"), dict) else {}
            page = source.get("page")
            rows.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "rule_id": str(rule.get("rule_id") or ""),
                    "decision": bucket,
                    "evidence_id": source.get("evidence_id"),
                    "page": page if isinstance(page, int) else None,
                    "support_gaps": [str(gap) for gap in rule.get("support_gaps") or []],
                }
            )
    return rows


def run(candidates_path: Path, evidence_path: Path, config_path: Path, out_dir: Path) -> dict[str, Any]:
    import jsonschema  # noqa: PLC0415

    from burnaby_prototype.config import load_config  # noqa: PLC0415
    from burnaby_prototype.slim_pipeline import run_slim_verification  # noqa: PLC0415

    candidates, candidates_info = _read_input(candidates_path, "bylaw_verify_candidates.schema.json")
    evidence, evidence_info = _read_input(evidence_path, "bylaw_verify_evidence.schema.json")
    try:
        config = load_config(config_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(EXIT_INPUT, f"cannot read config {config_path}: {exc}") from exc

    summary = run_slim_verification(
        config_path=config,
        output_dir=out_dir,
        evidence_units=evidence,
        rule_candidates=candidates,
        input_mode="bylaw_verify_cli",
        use_cache=False,
    )
    decisions = _decision_rows(out_dir)
    repair = {}
    repair_path = out_dir / "source_repair_report.json"
    if repair_path.exists():
        repair = json.loads(repair_path.read_text(encoding="utf-8"))
    envelope = {
        "contract_version": CONTRACT_VERSION,
        "tool": "bylaw-verify",
        "city": config_path.stem,
        "config": str(config_path),
        "inputs": {"candidates": candidates_info, "evidence": evidence_info},
        "source_pdf_used": bool(repair.get("source_pdf")),
        "counts": {
            "candidates": int(summary["candidate_rule_count"]),
            "verified": int(summary["verified_rule_count"]),
            "review_needed": int(summary["review_rule_count"]),
            "rejected": int(summary["rejected_rule_count"]),
            "not_used": int(summary["not_used_rule_count"]),
        },
        "decisions": decisions,
        "artifacts": sorted(p.name for p in out_dir.iterdir() if p.is_file() and p.name != ENVELOPE_NAME),
    }
    errors = list(jsonschema.Draft202012Validator(load_schema("bylaw_verify_result.schema.json")).iter_errors(envelope))
    if errors:
        raise ContractError(EXIT_OUTPUT_SCHEMA, f"output envelope violates the contract: {errors[0].message}")
    (out_dir / ENVELOPE_NAME).write_text(json.dumps(envelope, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return envelope


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bylaw-verify",
        description="Verify extracted zoning-rule candidates against their cited bylaw text "
        f"(contract {CONTRACT_VERSION}). No model call.",
        epilog="Exit codes: 0 ok, 1 internal error, 2 usage, 3 unreadable input, "
        "4 input fails its schema, 5 output fails its schema. Schemas: schemas/bylaw_verify_*.schema.json.",
    )
    parser.add_argument("--candidates", required=True, type=Path, help="rule_candidates.json")
    parser.add_argument("--evidence", required=True, type=Path, help="evidence_units.json")
    parser.add_argument("--config", required=True, type=Path, help="configs/<city>.json")
    parser.add_argument("--out-dir", required=True, type=Path, help="directory for the envelope and pipeline outputs")
    parser.add_argument("--version", action="version", version=f"bylaw-verify contract {CONTRACT_VERSION}")
    return parser


def _error(code: int, message: str) -> int:
    payload = {"contract_version": CONTRACT_VERSION, "tool": "bylaw-verify", "error": message, "exit_code": code}
    print(json.dumps(payload), file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.config.exists():
        return _error(EXIT_INPUT, f"config not found: {args.config}")
    try:
        envelope = run(args.candidates, args.evidence, args.config, args.out_dir)
    except ContractError as exc:
        return _error(exc.code, str(exc))
    except Exception as exc:  # noqa: BLE001 - report any internal failure with the contract's exit code
        return _error(EXIT_INTERNAL, f"{type(exc).__name__}: {exc}")
    print(json.dumps(envelope, indent=2, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
