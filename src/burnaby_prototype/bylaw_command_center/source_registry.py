"""F1 source registry builder.

The registry is the first product artifact in F1. It reads the existing city
configuration and cached official-source provenance, verifies the local file
hash when possible, and emits a stable registry artifact for downstream document
intelligence, RAG, extraction, verification, dashboard, and chatbot layers.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import ARTIFACT_SCHEMA_VERSION, SourceDocument


def build_source_registry(
    *,
    city_key: str,
    run_id: str,
    root: Path,
    config_path: Path | None = None,
    source_pdf_path: Path | None = None,
    provenance_path: Path | None = None,
) -> dict[str, Any]:
    """Build an F1 source registry artifact for one city key."""
    config_path = config_path or root / "configs" / f"{city_key}.json"
    source_pdf_path = source_pdf_path or root / "data" / "bylaws" / city_key / "source.pdf"
    provenance_path = provenance_path or root / "data" / "bylaws" / city_key / "provenance.json"

    config = _read_json(config_path) if config_path.exists() else {}
    provenance = _read_json(provenance_path) if provenance_path.exists() else {}
    actual_sha = _sha256(source_pdf_path) if source_pdf_path.exists() else ""
    expected_sha = str(provenance.get("sha256") or "")
    source_url = str(config.get("source_url") or provenance.get("url") or "")
    provenance_url = str(provenance.get("url") or "")
    hash_verified = bool(actual_sha and expected_sha and actual_sha == expected_sha)
    url_matches = bool(source_url and provenance_url and source_url == provenance_url)
    status = _source_status(
        has_config=config_path.exists(),
        has_source_pdf=source_pdf_path.exists(),
        has_provenance=provenance_path.exists(),
        hash_verified=hash_verified,
        expected_sha=expected_sha,
        actual_sha=actual_sha,
    )
    document = SourceDocument(
        source_id=f"{city_key}:source",
        city=str(config.get("city") or city_key),
        title=str(config.get("source_document") or config.get("bylaw") or source_pdf_path.name),
        bylaw_version=str(config.get("bylaw") or config.get("source_document") or ""),
        source_url=source_url,
        sha256=expected_sha or actual_sha,
        fetched_at=str(provenance.get("fetched_at") or ""),
        local_path=_display_path(source_pdf_path, root),
        bytes=_to_int(provenance.get("bytes")),
        page_count=_to_int(provenance.get("page_count")),
        scoped_pages=_normalize_pages(provenance.get("pages")),
        pages_rationale=str(provenance.get("pages_rationale") or ""),
        target_concept=str(config.get("target_concept") or ""),
        hash_verified=hash_verified,
        status=status,
    )
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact": "source_registry.json",
        "city_key": city_key,
        "city": document.city,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_count": 1,
        "documents": [document.to_dict()],
        "validation": {
            "status": "pass" if status == "registered" and url_matches else "needs_attention",
            "config_path": _display_path(config_path, root),
            "source_pdf_path": _display_path(source_pdf_path, root),
            "provenance_path": _display_path(provenance_path, root),
            "source_pdf_exists": source_pdf_path.exists(),
            "provenance_exists": provenance_path.exists(),
            "expected_sha256": expected_sha,
            "actual_sha256": actual_sha,
            "sha256_matches": hash_verified,
            "source_url_matches_provenance": url_matches,
            "source_url": source_url,
            "provenance_url": provenance_url,
        },
    }


def write_source_registry(registry: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "source_registry.json"
    path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _source_status(
    *,
    has_config: bool,
    has_source_pdf: bool,
    has_provenance: bool,
    hash_verified: bool,
    expected_sha: str,
    actual_sha: str,
) -> str:
    if not has_config:
        return "config_missing"
    if not has_source_pdf:
        return "source_pdf_missing"
    if not has_provenance:
        return "provenance_missing"
    if not expected_sha:
        return "provenance_sha_missing"
    if expected_sha and actual_sha and not hash_verified:
        return "hash_mismatch"
    return "registered"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_pages(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
