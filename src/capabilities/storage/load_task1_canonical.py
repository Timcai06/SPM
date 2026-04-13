#!/usr/bin/env python3
"""Load Task 1 canonical event outputs into PostgreSQL."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for, write_guard


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CANONICAL_EVENTS = ROOT / "output" / "canonical_events.csv"
DEFAULT_CANONICAL_MAP = ROOT / "output" / "event_canonical_map.csv"
DEFAULT_DB = "stock_event_mining"


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS int_canonical_events (
    id BIGSERIAL PRIMARY KEY,
    canonical_event_id TEXT NOT NULL UNIQUE,
    canonical_event_name TEXT NOT NULL,
    cluster_size INTEGER NOT NULL,
    date_start DATE NOT NULL,
    date_end DATE NOT NULL,
    event_subject_type TEXT NOT NULL,
    industry_type TEXT NOT NULL,
    impact_scope TEXT NOT NULL,
    representative_event_id TEXT NOT NULL,
    representative_source TEXT NOT NULL,
    max_heat_score INTEGER NOT NULL DEFAULT 0,
    max_intensity_score INTEGER NOT NULL DEFAULT 0,
    member_event_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    subject_entities JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_distribution JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_int_canonical_events_date_start
    ON int_canonical_events (date_start DESC);

CREATE INDEX IF NOT EXISTS idx_int_canonical_events_subject_type
    ON int_canonical_events (event_subject_type);

CREATE TABLE IF NOT EXISTS int_event_canonical_links (
    id BIGSERIAL PRIMARY KEY,
    structured_event_id BIGINT NOT NULL UNIQUE REFERENCES structured_events(id) ON DELETE CASCADE,
    canonical_event_id TEXT NOT NULL REFERENCES int_canonical_events(canonical_event_id) ON DELETE CASCADE,
    is_representative BOOLEAN NOT NULL DEFAULT FALSE,
    cluster_size INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_int_event_canonical_links_canonical_event
    ON int_event_canonical_links (canonical_event_id);
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load canonical event outputs into PostgreSQL.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--canonical-events", default=str(DEFAULT_CANONICAL_EVENTS))
    parser.add_argument("--canonical-map", default=str(DEFAULT_CANONICAL_MAP))
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def ensure_tables(db: str) -> None:
    with psycopg.connect(dsn_for(db)) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_SQL)
        conn.commit()


def to_int(value: str, default: int = 0) -> int:
    try:
        return int(float((value or "").strip()))
    except Exception:
        return default


def to_json(value: str, default: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return default
    try:
        json.loads(raw)
        return raw
    except Exception:
        return default


def load_canonical_events(cur: psycopg.Cursor, rows: list[dict[str, str]]) -> int:
    sql = """
    INSERT INTO int_canonical_events (
        canonical_event_id, canonical_event_name, cluster_size, date_start, date_end,
        event_subject_type, industry_type, impact_scope, representative_event_id,
        representative_source, max_heat_score, max_intensity_score,
        member_event_ids, subject_entities, source_distribution
    )
    VALUES (
        %(canonical_event_id)s, %(canonical_event_name)s, %(cluster_size)s, %(date_start)s, %(date_end)s,
        %(event_subject_type)s, %(industry_type)s, %(impact_scope)s, %(representative_event_id)s,
        %(representative_source)s, %(max_heat_score)s, %(max_intensity_score)s,
        %(member_event_ids)s::jsonb, %(subject_entities)s::jsonb, %(source_distribution)s::jsonb
    )
    ON CONFLICT (canonical_event_id) DO UPDATE
    SET canonical_event_name = EXCLUDED.canonical_event_name,
        cluster_size = EXCLUDED.cluster_size,
        date_start = EXCLUDED.date_start,
        date_end = EXCLUDED.date_end,
        event_subject_type = EXCLUDED.event_subject_type,
        industry_type = EXCLUDED.industry_type,
        impact_scope = EXCLUDED.impact_scope,
        representative_event_id = EXCLUDED.representative_event_id,
        representative_source = EXCLUDED.representative_source,
        max_heat_score = EXCLUDED.max_heat_score,
        max_intensity_score = EXCLUDED.max_intensity_score,
        member_event_ids = EXCLUDED.member_event_ids,
        subject_entities = EXCLUDED.subject_entities,
        source_distribution = EXCLUDED.source_distribution,
        updated_at = NOW();
    """
    payload = []
    for row in rows:
        payload.append(
            {
                "canonical_event_id": row["canonical_event_id"],
                "canonical_event_name": row["canonical_event_name"],
                "cluster_size": to_int(row.get("cluster_size", ""), 1),
                "date_start": row["date_start"],
                "date_end": row["date_end"],
                "event_subject_type": row["event_subject_type"],
                "industry_type": row["industry_type"],
                "impact_scope": row["impact_scope"],
                "representative_event_id": row["representative_event_id"],
                "representative_source": row["representative_source"],
                "max_heat_score": to_int(row.get("max_heat_score", ""), 0),
                "max_intensity_score": to_int(row.get("max_intensity_score", ""), 0),
                "member_event_ids": to_json(row.get("member_event_ids", ""), "[]"),
                "subject_entities": to_json(row.get("subject_entities", ""), "[]"),
                "source_distribution": to_json(row.get("source_distribution", ""), "{}"),
            }
        )
    cur.executemany(sql, payload)
    return len(payload)


def load_event_links(cur: psycopg.Cursor, rows: list[dict[str, str]]) -> int:
    cur.execute("SELECT id, event_id FROM structured_events")
    event_id_to_structured = {row[1]: row[0] for row in cur.fetchall()}

    cur.execute("DELETE FROM int_event_canonical_links")
    sql = """
    INSERT INTO int_event_canonical_links (
        structured_event_id, canonical_event_id, is_representative, cluster_size
    )
    VALUES (%(structured_event_id)s, %(canonical_event_id)s, %(is_representative)s, %(cluster_size)s)
    ON CONFLICT (structured_event_id) DO UPDATE
    SET canonical_event_id = EXCLUDED.canonical_event_id,
        is_representative = EXCLUDED.is_representative,
        cluster_size = EXCLUDED.cluster_size,
        updated_at = NOW();
    """
    payload = []
    for row in rows:
        structured_event_id = event_id_to_structured.get(row["event_id"])
        if not structured_event_id:
            continue
        payload.append(
            {
                "structured_event_id": structured_event_id,
                "canonical_event_id": row["canonical_event_id"],
                "is_representative": (row.get("is_representative", "").strip().lower() == "true"),
                "cluster_size": to_int(row.get("cluster_size", ""), 1),
            }
        )
    if payload:
        cur.executemany(sql, payload)
    return len(payload)


def run_loading_pipeline(db: str, canonical_event_rows: list[dict[str, str]] = None, canonical_link_rows: list[dict[str, str]] = None, lock_timeout_sec: int = 120, quiet: bool = False) -> None:
    """Orchestrate loading of canonical events."""
    if canonical_event_rows is None:
        canonical_event_rows = read_csv(DEFAULT_CANONICAL_EVENTS)
    if canonical_link_rows is None:
        canonical_link_rows = read_csv(DEFAULT_CANONICAL_MAP)
        
    ensure_tables(db)

    with write_guard(
        db_name=db,
        required_tables=["structured_events", "int_canonical_events", "int_event_canonical_links"],
        lock_timeout_sec=lock_timeout_sec,
    ) as conn:
        with conn.cursor() as cur:
            upserted = load_canonical_events(cur, canonical_event_rows)
            linked = load_event_links(cur, canonical_link_rows)
        conn.commit()

    if not quiet:
        print(f"Upserted {upserted} int_canonical_events into {db}")
        print(f"Loaded {linked} int_event_canonical_links into {db}")


def main() -> None:
    args = parse_args()
    run_loading_pipeline(
        db=args.db,
        lock_timeout_sec=args.lock_timeout_sec,
        quiet=args.quiet
    )


if __name__ == "__main__":
    main()
