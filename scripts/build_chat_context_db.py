"""Build a clean SQLite context database for Ask the Bylaw.

The dashboard/verifier emits many JSON files. That is good for auditability but
bad for chat: the LLM sees fragmented context unless we first join verified
rules, review router priority, review resolution, evidence packets, and source
chunks into a small read-only database.

This script writes ``chat_context.sqlite`` into each selected output directory.
It does not mutate verifier outputs and does not call any model.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_NAME = "chat_context.sqlite"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def items_from_json(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        items = value.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def by_rule_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("rule_id")): item for item in items if item.get("rule_id")}


def compact_json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, separators=(",", ":"))


def text_or_empty(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (list, dict)):
        return compact_json(value)
    return str(value)


def rule_sentence(rule: dict[str, Any]) -> str:
    obj = str(rule.get("rule_object") or "rule").replace("_", " ")
    ctype = str(rule.get("constraint_type") or "").lower()
    applies_to = str(rule.get("applies_to") or "").strip()
    value = str(rule.get("value") or "").strip()
    unit = str(rule.get("unit") or "").strip()
    condition = str(rule.get("condition") or rule.get("constraint_scope") or "").strip()
    prefix = "Maximum" if ctype == "maximum" else "Minimum" if ctype == "minimum" else obj.capitalize()
    amount = " ".join(part for part in (value, unit) if part).strip()
    sentence = f"{prefix} {obj}"
    if amount:
        sentence += f" is {amount}"
    if applies_to:
        sentence += f" for {applies_to}"
    if condition and condition.lower() not in applies_to.lower():
        sentence += f" when {condition}"
    return sentence + "."


def source_fields(rule: dict[str, Any], resolution: dict[str, Any] | None = None) -> dict[str, Any]:
    source = rule.get("source") if isinstance(rule.get("source"), dict) else {}
    resolution = resolution or {}
    return {
        "source_page": source.get("page") or source.get("source_page") or resolution.get("source_page"),
        "source_section": source.get("section") or source.get("source_section"),
        "source_evidence_id": source.get("evidence_id") or source.get("source_evidence_id") or resolution.get("source_evidence_id"),
        "evidence_text": (
            source.get("evidence_text")
            or source.get("evidence_quote")
            or source.get("source_text")
            or resolution.get("evidence_sentence")
            or ""
        ),
    }


def merged_rule(
    rule: dict[str, Any],
    *,
    bucket: str,
    router: dict[str, Any] | None,
    resolution: dict[str, Any] | None,
    assistant: dict[str, Any] | None,
) -> dict[str, Any]:
    router = router or {}
    resolution = resolution or {}
    assistant = assistant or {}
    source = source_fields(rule, resolution)
    merged = {
        **rule,
        "bucket": bucket,
        "candidate_sentence": router.get("candidate_sentence") or resolution.get("candidate_sentence") or rule_sentence(rule),
        "priority": router.get("priority") or router.get("triage_priority") or rule.get("triage_priority") or rule.get("review_priority"),
        "priority_rank": router.get("priority_rank") or router.get("review_rank") or rule.get("review_rank"),
        "review_category": router.get("review_category") or rule.get("review_category") or assistant.get("review_category"),
        "review_reason": rule.get("review_reason") or rule.get("blocking_reason") or router.get("blocking_reason") or router.get("action_reason"),
        "review_next_step": rule.get("review_next_step") or router.get("human_instruction") or resolution.get("human_next_step"),
        "where_to_find_it": router.get("where_to_find_it") or resolution.get("where_to_find_it"),
        **source,
    }
    return merged


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS metadata;
        DROP TABLE IF EXISTS rules;
        DROP TABLE IF EXISTS evidence_units;
        DROP TABLE IF EXISTS source_chunks;
        DROP TABLE IF EXISTS llm_facts;

        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE rules (
            rule_id TEXT PRIMARY KEY,
            bucket TEXT NOT NULL,
            status TEXT,
            rule_object TEXT,
            constraint_type TEXT,
            constraint_scope TEXT,
            applies_to TEXT,
            operator TEXT,
            value TEXT,
            unit TEXT,
            condition TEXT,
            exception TEXT,
            sentence TEXT NOT NULL,
            priority TEXT,
            priority_rank INTEGER,
            review_category TEXT,
            review_reason TEXT,
            review_next_step TEXT,
            support_gaps_json TEXT NOT NULL,
            source_page INTEGER,
            source_section TEXT,
            source_evidence_id TEXT,
            evidence_text TEXT,
            raw_json TEXT NOT NULL
        );

        CREATE INDEX idx_rules_bucket ON rules(bucket);
        CREATE INDEX idx_rules_object ON rules(rule_object);
        CREATE INDEX idx_rules_priority ON rules(priority, priority_rank);

        CREATE TABLE evidence_units (
            evidence_id TEXT PRIMARY KEY,
            page INTEGER,
            section TEXT,
            evidence_type TEXT,
            evidence_text TEXT,
            source_context TEXT,
            quality_score REAL,
            raw_json TEXT NOT NULL
        );

        CREATE TABLE source_chunks (
            chunk_id TEXT PRIMARY KEY,
            page INTEGER,
            section TEXT,
            text TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );

        CREATE TABLE llm_facts (
            fact_id TEXT PRIMARY KEY,
            rule_id TEXT,
            kind TEXT NOT NULL,
            bucket TEXT,
            topic TEXT,
            priority TEXT,
            source_page INTEGER,
            source_section TEXT,
            fact_text TEXT NOT NULL
        );

        CREATE INDEX idx_llm_facts_rule ON llm_facts(rule_id);
        CREATE INDEX idx_llm_facts_topic ON llm_facts(topic);
        """
    )
    try:
        conn.execute("CREATE VIRTUAL TABLE llm_facts_fts USING fts5(fact_id UNINDEXED, fact_text, topic)")
    except sqlite3.OperationalError:
        # FTS5 is present on normal Python builds, but the database is still useful
        # without it.
        pass


def insert_rule(conn: sqlite3.Connection, rule: dict[str, Any]) -> None:
    support_gaps = rule.get("support_gaps") or []
    priority_rank = rule.get("priority_rank")
    try:
        priority_rank_int = int(priority_rank) if priority_rank not in (None, "") else None
    except Exception:
        priority_rank_int = None
    conn.execute(
        """
        INSERT INTO rules VALUES (
            :rule_id, :bucket, :status, :rule_object, :constraint_type,
            :constraint_scope, :applies_to, :operator, :value, :unit,
            :condition, :exception, :sentence, :priority, :priority_rank,
            :review_category, :review_reason, :review_next_step,
            :support_gaps_json, :source_page, :source_section,
            :source_evidence_id, :evidence_text, :raw_json
        )
        """,
        {
            "rule_id": text_or_empty(rule.get("rule_id")),
            "bucket": text_or_empty(rule.get("bucket")),
            "status": text_or_empty(rule.get("verification_status") or rule.get("verification_decision")),
            "rule_object": text_or_empty(rule.get("rule_object")),
            "constraint_type": text_or_empty(rule.get("constraint_type")),
            "constraint_scope": text_or_empty(rule.get("constraint_scope")),
            "applies_to": text_or_empty(rule.get("applies_to")),
            "operator": text_or_empty(rule.get("operator")),
            "value": text_or_empty(rule.get("value")),
            "unit": text_or_empty(rule.get("unit")),
            "condition": text_or_empty(rule.get("condition")),
            "exception": text_or_empty(rule.get("exception")),
            "sentence": text_or_empty(rule.get("candidate_sentence") or rule_sentence(rule)),
            "priority": text_or_empty(rule.get("priority")),
            "priority_rank": priority_rank_int,
            "review_category": text_or_empty(rule.get("review_category")),
            "review_reason": text_or_empty(rule.get("review_reason")),
            "review_next_step": text_or_empty(rule.get("review_next_step")),
            "support_gaps_json": compact_json(support_gaps),
            "source_page": rule.get("source_page"),
            "source_section": text_or_empty(rule.get("source_section")),
            "source_evidence_id": text_or_empty(rule.get("source_evidence_id")),
            "evidence_text": text_or_empty(rule.get("evidence_text")),
            "raw_json": compact_json(rule),
        },
    )


def insert_llm_fact(conn: sqlite3.Connection, rule: dict[str, Any]) -> None:
    rule_id = text_or_empty(rule.get("rule_id"))
    bucket = text_or_empty(rule.get("bucket"))
    topic = text_or_empty(rule.get("rule_object"))
    priority = text_or_empty(rule.get("priority"))
    sentence = text_or_empty(rule.get("candidate_sentence") or rule_sentence(rule))
    reason = text_or_empty(rule.get("review_reason"))
    next_step = text_or_empty(rule.get("review_next_step"))
    source_bits = []
    if rule.get("source_section"):
        source_bits.append(f"section {rule.get('source_section')}")
    if rule.get("source_page") not in (None, ""):
        source_bits.append(f"page {rule.get('source_page')}")
    source_text = ", ".join(source_bits)
    parts = [f"{bucket.upper()} rule: {sentence}"]
    if priority:
        parts.append(f"Priority: {priority}; rank: {rule.get('priority_rank') or 'not ranked'}.")
    if reason:
        parts.append(f"Review reason: {reason}.")
    if next_step:
        parts.append(f"Reviewer next step: {next_step}.")
    if source_text:
        parts.append(f"Source: {source_text}.")
    if rule.get("evidence_text"):
        parts.append(f"Evidence: {rule.get('evidence_text')}")
    fact_text = " ".join(parts)
    fact_id = f"rule:{rule_id}"
    row = {
        "fact_id": fact_id,
        "rule_id": rule_id,
        "kind": "rule",
        "bucket": bucket,
        "topic": topic,
        "priority": priority,
        "source_page": rule.get("source_page"),
        "source_section": text_or_empty(rule.get("source_section")),
        "fact_text": fact_text,
    }
    conn.execute(
        """
        INSERT INTO llm_facts
        (fact_id, rule_id, kind, bucket, topic, priority, source_page, source_section, fact_text)
        VALUES (:fact_id, :rule_id, :kind, :bucket, :topic, :priority, :source_page, :source_section, :fact_text)
        """,
        row,
    )
    try:
        conn.execute(
            "INSERT INTO llm_facts_fts (fact_id, fact_text, topic) VALUES (?, ?, ?)",
            (fact_id, fact_text, topic),
        )
    except sqlite3.OperationalError:
        pass


def build_chat_context_db(output_dir: Path, db_path: Path | None = None) -> Path:
    output_dir = Path(output_dir)
    db_path = Path(db_path or output_dir / DEFAULT_DB_NAME)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    verified = items_from_json(read_json(output_dir / "verified_rules.json", []))
    review = items_from_json(read_json(output_dir / "review_needed.json", []))
    rejected = items_from_json(read_json(output_dir / "rejected_rules.json", []))
    not_used = items_from_json(read_json(output_dir / "not_used.json", []))
    router = by_rule_id(items_from_json(read_json(output_dir / "review_router.json", {"items": []})))
    resolution = by_rule_id(items_from_json(read_json(output_dir / "review_resolution.json", {"items": []})))
    assistant = by_rule_id(items_from_json(read_json(output_dir / "review_assistant_packets.json", {"items": []})))
    evidence = items_from_json(read_json(output_dir / "evidence_units.json", []))
    rag_index = read_json(output_dir / "bylaw_rag_index.json", {})
    chunks = [chunk for chunk in rag_index.get("chunks", []) if isinstance(chunk, dict)] if isinstance(rag_index, dict) else []

    tmp_path = db_path.with_suffix(".tmp.sqlite")
    if tmp_path.exists():
        tmp_path.unlink()
    conn = sqlite3.connect(str(tmp_path))
    try:
        create_schema(conn)
        meta = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "output_dir": str(output_dir),
            "verified_count": str(len(verified)),
            "review_count": str(len(review)),
            "rejected_count": str(len(rejected)),
            "not_used_count": str(len(not_used)),
            "evidence_count": str(len(evidence)),
            "source_chunk_count": str(len(chunks)),
        }
        conn.executemany("INSERT INTO metadata(key, value) VALUES (?, ?)", meta.items())

        for bucket, rules in (
            ("verified", verified),
            ("review", review),
            ("rejected", rejected),
            ("not_used", not_used),
        ):
            for rule in rules:
                rid = str(rule.get("rule_id") or "")
                if not rid:
                    continue
                merged = merged_rule(
                    rule,
                    bucket=bucket,
                    router=router.get(rid),
                    resolution=resolution.get(rid),
                    assistant=assistant.get(rid),
                )
                insert_rule(conn, merged)
                insert_llm_fact(conn, merged)

        for item in evidence:
            evidence_id = text_or_empty(item.get("evidence_id"))
            if not evidence_id:
                continue
            conn.execute(
                """
                INSERT INTO evidence_units VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    item.get("page"),
                    text_or_empty(item.get("section")),
                    text_or_empty(item.get("evidence_type")),
                    text_or_empty(item.get("evidence_text")),
                    text_or_empty(item.get("source_context")),
                    item.get("evidence_quality_score"),
                    compact_json(item),
                ),
            )

        for chunk in chunks:
            chunk_id = text_or_empty(chunk.get("chunk_id"))
            if not chunk_id:
                continue
            conn.execute(
                "INSERT INTO source_chunks VALUES (?, ?, ?, ?, ?)",
                (
                    chunk_id,
                    chunk.get("page"),
                    text_or_empty(chunk.get("section")),
                    text_or_empty(chunk.get("text")),
                    compact_json(chunk),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    tmp_path.replace(db_path)
    return db_path


def discover_output_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_dir()
        and (path / "verified_rules.json").exists()
        and (path / "review_needed.json").exists()
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", action="append", default=[], help="Verifier output directory to build.")
    parser.add_argument("--outputs-root", action="append", default=[], help="Root to discover output directories under.")
    parser.add_argument("--all", action="store_true", help="Discover output dirs under the package and deploy outputs roots.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    targets = [Path(value) for value in args.output_dir]
    roots = [Path(value) for value in args.outputs_root]
    if args.all or (not targets and not roots):
        roots.extend(
            [
                ROOT / "outputs",
                ROOT.parent / "burnaby-verification-dashboard-deploy" / "outputs",
            ]
        )
    for root in roots:
        targets.extend(discover_output_dirs(root))
    unique_targets = []
    seen = set()
    for target in targets:
        resolved = target.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_targets.append(target)
    if not unique_targets:
        raise SystemExit("No output directories found.")
    for target in unique_targets:
        db_path = build_chat_context_db(target)
        print(f"wrote {db_path}")


if __name__ == "__main__":
    main()
