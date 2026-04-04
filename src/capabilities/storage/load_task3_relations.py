#!/usr/bin/env python3
"""Load company relation edges for Task 3 graph preparation."""

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
DEFAULT_DB = "stock_event_mining"
DEFAULT_INPUT = ROOT / "output" / "seeds" / "company_relations_seed.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load task3 company relation edges.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    args = parse_args()
    rows = read_rows(Path(args.input).resolve())
    inserted = 0
    updated = 0
    skipped = 0

    with write_guard(
        db_name=args.db,
        required_tables=["companies", "company_relations"],
        lock_timeout_sec=args.lock_timeout_sec,
    ):
        with psycopg.connect(dsn_for(args.db), row_factory=psycopg.rows.dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM company_relations WHERE is_manual_override = TRUE")
                for row in rows:
                    cur.execute("SELECT id FROM companies WHERE ts_code = %s", (row["source_ts_code"],))
                    source = cur.fetchone()
                    cur.execute("SELECT id FROM companies WHERE ts_code = %s", (row["target_ts_code"],))
                    target = cur.fetchone()
                    if not source or not target:
                        skipped += 1
                        continue
                    source_id = source["id"]
                    target_id = target["id"]
                    direction = row.get("direction", "undirected")
                    if direction == "undirected" and source_id > target_id:
                        source_id, target_id = target_id, source_id
                    cur.execute(
                        """
                        INSERT INTO company_relations (
                            source_company_id, target_company_id, relation_type,
                            relation_strength, direction, evidence, is_manual_override
                        )
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb, TRUE)
                        ON CONFLICT (source_company_id, target_company_id, relation_type) DO UPDATE
                        SET relation_strength = EXCLUDED.relation_strength,
                            direction = EXCLUDED.direction,
                            evidence = EXCLUDED.evidence,
                            is_manual_override = TRUE,
                            updated_at = NOW()
                        """,
                        (
                            source_id,
                            target_id,
                            row["relation_type"],
                            row.get("relation_strength", "0.5000"),
                            direction,
                            json.dumps(
                                {
                                    "evidence_note": row.get("evidence_note", ""),
                                    "source_ts_code": row["source_ts_code"],
                                    "target_ts_code": row["target_ts_code"],
                                },
                                ensure_ascii=False,
                            ),
                        ),
                    )
                    if cur.rowcount == 1:
                        inserted += 1
                    else:
                        updated += 1
            conn.commit()
    print(
        f"Processed {len(rows)} relation rows into {args.db} "
        f"(inserted_or_updated={inserted + updated}, skipped={skipped})"
    )


if __name__ == "__main__":
    main()
